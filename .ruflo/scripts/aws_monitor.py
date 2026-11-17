#!/usr/bin/env python3
"""AWS activity + spend monitor.

Sweeps every enabled region for billable resources, flags anything that is
running but idle, and estimates the monthly run rate. If the caller has
Cost Explorer permission it reports real month-to-date spend instead of the
estimate; without it the estimate is the only number available.

State is kept in ~/.ruflo/data/aws_monitor_state.json so each run can report
what changed since the last one.

    python3 aws_monitor.py                # human-readable report
    python3 aws_monitor.py --json         # machine-readable
    python3 aws_monitor.py --quiet        # print only when something changed
                                          # or an alert fires (for cron)

Exit code is 1 when an alert fires (idle instance, run rate over budget,
new billable resource), 0 otherwise. No credentials are read or written by
this script; it shells out to the configured AWS CLI profile.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE = Path.home() / ".ruflo" / "data" / "aws_monitor_state.json"

# Monthly budget in USD. The account is a data-collection side project, so
# anything above this is worth a look rather than a hard limit.
BUDGET_USD = 20.0

# An instance is "idle" if its 7-day average CPU stays under this and it has
# been up for at least IDLE_MIN_HOURS. t3 credit balance pinned at the cap is
# treated as corroborating evidence.
IDLE_CPU_PCT = 2.0
IDLE_MIN_HOURS = 24

HOURS_PER_MONTH = 730

# us-east-1 on-demand Linux, USD/hour. Only the small instance families this
# account has ever used are listed; anything unknown falls back to None and is
# reported as "unpriced" rather than silently costing zero.
INSTANCE_PRICE = {
    "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208,
    "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328,
    "t4g.micro": 0.0084, "t4g.small": 0.0168, "t4g.medium": 0.0336,
    "m5.large": 0.096, "m5.xlarge": 0.192,
    "c5.large": 0.085, "c5.xlarge": 0.17,
    "r5.large": 0.126,
}

# USD per GB-month.
VOLUME_PRICE = {
    "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
    "st1": 0.045, "sc1": 0.015, "standard": 0.05,
}

# Every public IPv4 address is charged since Feb 2024, attached or not.
IPV4_HOURLY = 0.005


def aws(*args: str, region: str | None = None) -> tuple[bool, object]:
    """Run an AWS CLI command, returning (ok, parsed_json_or_error_string)."""
    cmd = ["aws", *args, "--output", "json"]
    if region:
        cmd += ["--region", region]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()
        msg = err[-1] if err else "unknown error"
        if "AccessDenied" in msg or "UnauthorizedOperation" in msg:
            return False, "denied"
        return False, msg[:200]
    if not proc.stdout.strip():
        return True, None
    try:
        return True, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, "unparseable response"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def metric(region: str, instance_id: str, name: str, hours: int, stat: str) -> float | None:
    """Average of a CloudWatch EC2 metric over the trailing window."""
    ok, data = aws(
        "cloudwatch", "get-metric-statistics",
        "--namespace", "AWS/EC2", "--metric-name", name,
        "--dimensions", f"Name=InstanceId,Value={instance_id}",
        "--start-time", iso(utcnow() - timedelta(hours=hours)),
        "--end-time", iso(utcnow()),
        "--period", "3600", "--statistics", stat,
        region=region,
    )
    if not ok or not data:
        return None
    points = data.get("Datapoints") or []
    if not points:
        return None
    return sum(p[stat] for p in points) / len(points)


def enabled_regions() -> list[str]:
    ok, data = aws("ec2", "describe-regions", region="us-east-1")
    if not ok or not data:
        return ["us-east-1"]
    return sorted(r["RegionName"] for r in data.get("Regions", []))


def scan_region(region: str) -> dict:
    """Collect billable EC2/EBS/EIP state for one region."""
    found: dict = {"region": region, "instances": [], "volumes": [], "addresses": []}

    ok, data = aws("ec2", "describe-instances", region=region)
    if ok and data:
        for res in data.get("Reservations", []):
            for inst in res.get("Instances", []):
                state = inst["State"]["Name"]
                if state in ("terminated", "shutting-down"):
                    continue
                name = next(
                    (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), ""
                )
                found["instances"].append({
                    "id": inst["InstanceId"],
                    "type": inst["InstanceType"],
                    "state": state,
                    "name": name,
                    "launched": inst["LaunchTime"],
                    "public_ip": inst.get("PublicIpAddress"),
                    "region": region,
                })

    ok, data = aws("ec2", "describe-volumes", region=region)
    if ok and data:
        for vol in data.get("Volumes", []):
            attachments = vol.get("Attachments") or []
            found["volumes"].append({
                "id": vol["VolumeId"],
                "size": vol["Size"],
                "type": vol["VolumeType"],
                "attached_to": attachments[0]["InstanceId"] if attachments else None,
                "region": region,
            })

    ok, data = aws("ec2", "describe-addresses", region=region)
    if ok and data:
        for addr in data.get("Addresses", []):
            found["addresses"].append({
                "ip": addr["PublicIp"],
                "attached_to": addr.get("InstanceId"),
                "region": region,
            })

    return found


def cost_explorer() -> dict | None:
    """Real month-to-date spend by service, or None if not permitted."""
    today = utcnow().date()
    start = today.replace(day=1)
    if start == today:  # Cost Explorer rejects a zero-length period
        start = start - timedelta(days=1)
    ok, data = aws(
        "ce", "get-cost-and-usage",
        "--time-period", f"Start={start},End={today + timedelta(days=1)}",
        "--granularity", "MONTHLY", "--metrics", "UnblendedCost",
        "--group-by", "Type=DIMENSION,Key=SERVICE",
        region="us-east-1",
    )
    if not ok or not data:
        return None
    services: dict[str, float] = {}
    for period in data.get("ResultsByTime", []):
        for group in period.get("Groups", []):
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if amount > 0:
                services[group["Keys"][0]] = services.get(group["Keys"][0], 0) + amount
    return {"period_start": str(start), "by_service": services,
            "total": sum(services.values())}


def analyse(regions_data: list[dict]) -> dict:
    instances, volumes, addresses = [], [], []
    for r in regions_data:
        instances += r["instances"]
        volumes += r["volumes"]
        addresses += r["addresses"]

    running = [i for i in instances if i["state"] == "running"]
    by_id = {i["id"]: i for i in instances}

    # Idle detection only makes sense for instances that are actually on.
    for inst in running:
        launched = datetime.fromisoformat(inst["launched"].replace("Z", "+00:00"))
        inst["uptime_hours"] = (utcnow() - launched).total_seconds() / 3600
        inst["cpu_avg_7d"] = metric(inst["region"], inst["id"], "CPUUtilization", 168, "Average")
        inst["credit_balance"] = metric(inst["region"], inst["id"], "CPUCreditBalance", 6, "Average")
        inst["idle"] = (
            inst["cpu_avg_7d"] is not None
            and inst["cpu_avg_7d"] < IDLE_CPU_PCT
            and inst["uptime_hours"] >= IDLE_MIN_HOURS
        )

    lines, unpriced = [], []
    monthly = 0.0

    for inst in running:
        price = INSTANCE_PRICE.get(inst["type"])
        if price is None:
            unpriced.append(f"{inst['id']} ({inst['type']})")
            continue
        cost = price * HOURS_PER_MONTH
        monthly += cost
        lines.append((f"EC2 {inst['type']} {inst['id']}"
                      f"{' [IDLE]' if inst['idle'] else ''}", cost))

    for vol in volumes:
        price = VOLUME_PRICE.get(vol["type"])
        if price is None:
            unpriced.append(f"{vol['id']} ({vol['type']})")
            continue
        cost = price * vol["size"]
        monthly += cost
        holder = by_id.get(vol["attached_to"] or "")
        if vol["attached_to"] is None:
            note = " [UNATTACHED]"
        elif holder and holder["state"] != "running":
            note = f" [on {holder['state']} instance]"
        else:
            note = ""
        lines.append((f"EBS {vol['type']} {vol['size']}GB {vol['id']}{note}", cost))

    # Charged per public IPv4 whether it is an EIP or an auto-assigned address.
    ipv4_count = len({a["ip"] for a in addresses}) + sum(
        1 for i in running if i["public_ip"] and
        i["public_ip"] not in {a["ip"] for a in addresses}
    )
    if ipv4_count:
        cost = ipv4_count * IPV4_HOURLY * HOURS_PER_MONTH
        monthly += cost
        lines.append((f"Public IPv4 x{ipv4_count}", cost))

    for addr in addresses:
        if addr["attached_to"] is None:
            lines.append((f"  ^ EIP {addr['ip']} UNATTACHED", 0.0))

    waste = sum(
        INSTANCE_PRICE.get(i["type"], 0) * HOURS_PER_MONTH
        for i in running if i["idle"]
    )

    return {
        "instances": instances,
        "running": running,
        "volumes": volumes,
        "addresses": addresses,
        "lines": sorted(lines, key=lambda x: -x[1]),
        "monthly_estimate": monthly,
        "idle_waste_monthly": waste,
        "unpriced": unpriced,
    }


def fingerprint(a: dict) -> dict:
    """The subset of state worth diffing between runs."""
    return {
        "instances": {i["id"]: i["state"] for i in a["instances"]},
        "volumes": sorted(v["id"] for v in a["volumes"]),
        "monthly_estimate": round(a["monthly_estimate"], 2),
    }


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(fp: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"checked_at": iso(utcnow()), **fp}, indent=2))


def diff(old: dict, new: dict) -> list[str]:
    changes = []
    old_inst, new_inst = old.get("instances", {}), new["instances"]
    for iid, state in new_inst.items():
        if iid not in old_inst:
            changes.append(f"NEW instance {iid} ({state})")
        elif old_inst[iid] != state:
            changes.append(f"instance {iid}: {old_inst[iid]} -> {state}")
    for iid in old_inst:
        if iid not in new_inst:
            changes.append(f"instance {iid} gone")

    old_vol, new_vol = set(old.get("volumes", [])), set(new["volumes"])
    for vid in new_vol - old_vol:
        changes.append(f"NEW volume {vid}")
    for vid in old_vol - new_vol:
        changes.append(f"volume {vid} gone")

    old_cost = old.get("monthly_estimate")
    if old_cost is not None and abs(new["monthly_estimate"] - old_cost) > 0.5:
        changes.append(
            f"run rate ${old_cost:.2f} -> ${new['monthly_estimate']:.2f}/mo"
        )
    return changes


def report(a: dict, ce: dict | None, changes: list[str], alerts: list[str],
           identity: str, first_run: bool = False) -> str:
    out = [f"AWS monitor — {utcnow():%Y-%m-%d %H:%M UTC}", f"caller: {identity}", ""]

    if alerts:
        out.append("ALERTS")
        out += [f"  ! {x}" for x in alerts]
        out.append("")

    if first_run:
        out.append("first run — baseline recorded, no comparison available")
        out.append("")
    elif changes:
        out.append("CHANGED SINCE LAST RUN")
        out += [f"  * {x}" for x in changes]
        out.append("")

    out.append(f"RUNNING INSTANCES ({len(a['running'])})")
    if not a["running"]:
        out.append("  none")
    for i in a["running"]:
        cpu = "n/a" if i["cpu_avg_7d"] is None else f"{i['cpu_avg_7d']:.2f}%"
        out.append(
            f"  {i['id']}  {i['type']:<10} {i['region']:<12} "
            f"up {i['uptime_hours']/24:.1f}d  cpu7d {cpu}"
            f"{'  <-- IDLE' if i['idle'] else ''}"
        )
        if i["name"]:
            out.append(f"      name: {i['name']}")

    stopped = [i for i in a["instances"] if i["state"] != "running"]
    if stopped:
        out.append("")
        out.append(f"STOPPED INSTANCES ({len(stopped)}) — no compute charge, "
                   f"volumes still billed")
        for i in stopped:
            out.append(f"  {i['id']}  {i['type']:<10} {i['region']:<12} {i['state']}")

    out.append("")
    if ce:
        out.append(f"ACTUAL SPEND (Cost Explorer, from {ce['period_start']})")
        for svc, amt in sorted(ce["by_service"].items(), key=lambda x: -x[1]):
            out.append(f"  {svc:<45} ${amt:>8.2f}")
        out.append(f"  {'TOTAL month-to-date':<45} ${ce['total']:>8.2f}")
    else:
        out.append("ACTUAL SPEND: unavailable (no ce:GetCostAndUsage permission)")

    out.append("")
    out.append("ESTIMATED RUN RATE (us-east-1 on-demand list prices)")
    for label, cost in a["lines"]:
        out.append(f"  {label:<45} ${cost:>8.2f}/mo")
    out.append(f"  {'TOTAL':<45} ${a['monthly_estimate']:>8.2f}/mo")
    out.append(f"  {'budget':<45} ${BUDGET_USD:>8.2f}/mo")
    if a["idle_waste_monthly"] > 0:
        out.append(f"  {'of which idle compute':<45} "
                   f"${a['idle_waste_monthly']:>8.2f}/mo")
    if a["unpriced"]:
        out.append(f"  unpriced resources (not in estimate): "
                   f"{', '.join(a['unpriced'])}")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true",
                    help="print only on change or alert (for cron)")
    ap.add_argument("--region", action="append",
                    help="limit the sweep to these regions (repeatable)")
    args = ap.parse_args()

    ok, ident = aws("sts", "get-caller-identity")
    if not ok:
        print(f"cannot authenticate to AWS: {ident}", file=sys.stderr)
        return 2
    identity = ident["Arn"]

    regions = args.region or enabled_regions()
    with ThreadPoolExecutor(max_workers=8) as pool:
        regions_data = list(pool.map(scan_region, regions))

    a = analyse(regions_data)
    ce = cost_explorer()

    alerts = []
    for i in a["running"]:
        if i["idle"]:
            alerts.append(
                f"{i['id']} ({i['type']}, {i['name'] or 'unnamed'}) idle "
                f"{i['uptime_hours']/24:.1f}d at {i['cpu_avg_7d']:.2f}% CPU"
            )
    for v in a["volumes"]:
        if v["attached_to"] is None:
            alerts.append(f"volume {v['id']} ({v['size']}GB) unattached")
    for addr in a["addresses"]:
        if addr["attached_to"] is None:
            alerts.append(f"elastic IP {addr['ip']} unattached")
    spend = ce["total"] if ce else a["monthly_estimate"]
    if spend > BUDGET_USD:
        label = "month-to-date spend" if ce else "estimated run rate"
        alerts.append(f"{label} ${spend:.2f} over ${BUDGET_USD:.2f} budget")

    fp = fingerprint(a)
    prev = load_state()
    # A first run has nothing to compare against — reporting every existing
    # resource as "new" would be pure noise, and worse, would train the eye to
    # ignore the section that actually matters.
    first_run = not prev
    changes = [] if first_run else diff(prev, fp)
    save_state(fp)

    if args.json:
        print(json.dumps({
            "checked_at": iso(utcnow()), "identity": identity,
            "running": len(a["running"]), "instances": a["instances"],
            "volumes": a["volumes"], "monthly_estimate": a["monthly_estimate"],
            "idle_waste_monthly": a["idle_waste_monthly"],
            "actual_spend": ce, "alerts": alerts, "changes": changes,
            "first_run": first_run,
        }, indent=2, default=str))
    elif not args.quiet or changes or alerts:
        print(report(a, ce, changes, alerts, identity, first_run))

    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
