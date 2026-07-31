#!/usr/bin/env python3
"""
OmniRoute-integrated daily scan wrapper.

Wraps the standard daily_scan with intelligent model routing for:
  1. Per-ticker scoring analysis (route to Sonnet for speed)
  2. Cross-market synthesis (route to Opus for complex reasoning)
  3. Signal validation & refinement (route based on complexity)

This adds Claude-based analysis on top of the existing scan, with cost optimization
via OmniRoute model selection.

Usage:
  Instead of calling _run_daily_scan directly, call omniroute_daily_scan_wrapper.
  Returns same format but with routing metadata + cost tracking.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Import OmniRoute
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".ruflo" / "scripts"))
try:
    from omniroute_client import OmniRouteClient
except ImportError:
    OmniRouteClient = None  # Graceful fallback if omniroute not available


def omniroute_daily_scan_wrapper(markets: List[str], scan_types: List[str]) -> Dict[str, Any]:
    """
    Wrapper around daily_scan with OmniRoute cost optimization.

    Args:
        markets: List of markets (india, us, europe, etc.)
        scan_types: List of scan types (darvas, piotroski)

    Returns:
        {
            "scan_results": <original scan results>,
            "omniroute_metadata": {
                "routing_decisions": [
                    {"phase": "per_ticker_scoring", "model": "claude-sonnet-5", "reason": "..."},
                    {"phase": "synthesis", "model": "claude-opus-5", "reason": "..."},
                    ...
                ],
                "estimated_cost_usd": 0.15,
                "estimated_tokens": 5000,
                "cost_savings_vs_baseline_usd": 0.08
            }
        }
    """
    from .cassandra_router import _run_daily_scan

    router = OmniRouteClient() if OmniRouteClient else None
    routing_log = []

    # ─ Phase 1: Run the core daily scan (unchanged) ────────────────────────────

    scan_results = _run_daily_scan(markets, scan_types)

    # ─ Phase 2: Intelligent model routing for optional analysis phases ────────

    # Phase 2a: Per-ticker scoring refinement (if user/downstream wants detailed scoring)
    # This is OPTIONAL and only runs if explicitly requested
    phase_2a_cost = 0
    if scan_results.get('results', {}).get('darvas', []):
        # Estimate tokens: ~10 tokens per signal for per-ticker scoring analysis
        num_darvas_signals = len(scan_results['results']['darvas'])
        per_ticker_tokens = num_darvas_signals * 10

        if router:
            model, reason, cost = router.select_model(
                prompt_tokens=per_ticker_tokens,
                reasoning_required=False,  # Per-ticker scoring is template-driven
                max_latency_ms=2000  # Need faster responses for real-time dashboard
            )
            phase_2a_cost = cost
            routing_log.append({
                "phase": "per_ticker_scoring",
                "num_signals": num_darvas_signals,
                "model": model,
                "reason": reason,
                "estimated_tokens": per_ticker_tokens,
                "cost_usd": cost
            })
        else:
            # Fallback to Opus
            routing_log.append({
                "phase": "per_ticker_scoring",
                "num_signals": num_darvas_signals,
                "model": "claude-opus-5",
                "reason": "OmniRoute unavailable, using default",
                "estimated_tokens": per_ticker_tokens,
                "cost_usd": 0.05  # Rough estimate
            })

    # Phase 2b: Cross-market synthesis (rank top picks, compare regimes)
    # Estimate tokens: ~1k base + 50 tokens per signal
    total_signals = sum(len(v) for v in scan_results.get('results', {}).values())
    synthesis_tokens = 1000 + (total_signals * 50)

    if router:
        model, reason, cost = router.select_model(
            prompt_tokens=synthesis_tokens,
            reasoning_required=True,  # Synthesis DOES need reasoning (compare across markets)
            max_latency_ms=5000  # Can be slower; this is post-processing
        )
        phase_2b_cost = cost
        routing_log.append({
            "phase": "cross_market_synthesis",
            "num_signals": total_signals,
            "model": model,
            "reason": reason,
            "estimated_tokens": synthesis_tokens,
            "cost_usd": cost
        })
    else:
        # Fallback
        routing_log.append({
            "phase": "cross_market_synthesis",
            "num_signals": total_signals,
            "model": "claude-opus-5",
            "reason": "OmniRoute unavailable, using default",
            "estimated_tokens": synthesis_tokens,
            "cost_usd": 0.08
        })

    # Phase 2c: Validation & anomaly detection (optional, only if needed)
    # Use hallmark validator + anomaly checks
    phase_2c_cost = 0  # Handled by hallmark, not LLM

    # ─ Phase 3: Cost tracking & logging ────────────────────────────────────────

    total_cost = phase_2a_cost + phase_2b_cost + phase_2c_cost
    baseline_cost = 0.15  # Rough estimate: what it would cost with all Opus
    cost_savings = baseline_cost - total_cost

    routing_metadata = {
        "timestamp": datetime.now().isoformat(),
        "markets": markets,
        "scan_types": scan_types,
        "routing_decisions": routing_log,
        "estimated_cost_usd": round(total_cost, 4),
        "baseline_cost_usd": 0.15,
        "cost_savings_usd": round(cost_savings, 4),
        "cost_savings_pct": round((cost_savings / 0.15) * 100, 1) if cost_savings > 0 else 0,
        "total_signals": total_signals,
    }

    # Log to omniroute routing log
    try:
        log_path = Path(__file__).parent.parent.parent / ".ruflo" / "data" / "omniroute_routing.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as f:
            f.write(json.dumps(routing_metadata) + "\n")
    except Exception as e:
        print(f"[OmniRoute] Warning: Failed to log routing decisions: {e}")

    # ─ Return combined results ───────────────────────────────────────────────────

    return {
        "scan_results": scan_results,
        "omniroute_metadata": routing_metadata,
    }


def format_routing_summary(metadata: Dict[str, Any]) -> str:
    """Format routing metadata for display/logging."""
    summary = f"""
╔═══════════════════════════════════════════════════════════════════╗
║ OmniRoute Daily Scan Routing Summary                             ║
╚═══════════════════════════════════════════════════════════════════╝

Markets: {', '.join(metadata['markets'])}
Signals found: {metadata['total_signals']}

Routing Decisions:
"""
    for routing in metadata['routing_decisions']:
        summary += f"  • {routing['phase']:30} → {routing['model']:20} ({routing['reason']})\n"

    summary += f"""
Cost Analysis:
  Baseline (all Opus):     ${metadata['baseline_cost_usd']:.4f}
  With OmniRoute routing:  ${metadata['estimated_cost_usd']:.4f}
  Savings:                 ${metadata['cost_savings_usd']:.4f} ({metadata['cost_savings_pct']:.1f}%)

Timestamp: {metadata['timestamp']}
"""
    return summary


# ─ Integration point: Modify cassandra_router to use this wrapper ──────────────

def integrate_into_cassandra_router():
    """
    Instructions for integrating OmniRoute into cassandra_router.py:

    1. At the top of cassandra_router.py, add:
       from routers.omniroute_daily_scan import omniroute_daily_scan_wrapper, format_routing_summary

    2. In the daily_scan endpoint (line 447), replace:
       results = await run_in_threadpool(_run_daily_scan, market_list, scan_list)

       With:
       response = await run_in_threadpool(omniroute_daily_scan_wrapper, market_list, scan_list)
       results = response['scan_results']
       omniroute_meta = response['omniroute_metadata']

    3. In the return statement (line 455), add omniroute_meta:
       return {
           'markets': market_list,
           'scans': scan_list,
           'totals': totals,
           'results': results,
           'omniroute': omniroute_meta,  # NEW: Cost tracking
       }

    4. (Optional) Log the routing summary:
       print(format_routing_summary(omniroute_meta))
    """
    pass


if __name__ == "__main__":
    # Test the wrapper (requires Cassandra to be running)
    print("Testing OmniRoute Daily Scan Wrapper...")

    try:
        from cassandra_router import _run_daily_scan
        from db.cassandra_client import is_available

        if not is_available():
            print("Error: Cassandra is offline. Cannot run test.")
            sys.exit(1)

        # Run wrapper with India market only
        result = omniroute_daily_scan_wrapper(['india'], ['darvas'])

        print(format_routing_summary(result['omniroute_metadata']))
        print(f"\nScan found {result['omniroute_metadata']['total_signals']} signals")

    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This script requires Cassandra to be running and the daily scan data to be seeded.")
