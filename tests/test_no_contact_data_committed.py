"""
No personal contact data may become a tracked file.

A LinkedIn connections export — and anything derived by joining it to job
matches — carries names, employers, titles and email addresses for thousands of
real people who never agreed to appear in a repository. The repo is a public
artefact; their data is not.

This is not hypothetical. reports/network_targets.csv was committed once, from a
fixture run, because the module's default output directory happened to be
tracked. The fixture was invented, so nothing real was exposed — but the path
was the hazard and the next run would not have been a fixture.

These tests fail on the SHAPE of contact data rather than on any particular
file, so a new module writing somewhere new is caught too.

Run:
    python -m pytest tests/test_no_contact_data_committed.py -v
"""

import os
import subprocess

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Column headers unique to a LinkedIn export or to something built from one.
CONTACT_SIGNATURES = [
    "First Name,Last Name",
    "Connected On",
    "example_contact",
    "linkedin.com/in/",
]


def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


# The one place contact-shaped data is allowed: test fixtures, which must be
# fabricated. The exemption is a directory, not a wildcard, and
# test_fixtures_use_only_reserved_example_domains constrains what may live in
# it — so a real export cannot be smuggled in by renaming it to a fixture.
FIXTURE_DIR = "job_search/tests/fixtures/"


def _is_exempt(path: str) -> bool:
    if path.endswith("test_no_contact_data_committed.py"):
        return True          # this file names the signatures it hunts for
    if path.endswith(".md"):
        return True          # prose describing the hazard is not the hazard
    if path.startswith(FIXTURE_DIR):
        return True          # fabricated, and constrained by the test below
    if path.endswith(".py"):
        return True          # a column name in source is not a person's data
    return False


def test_no_tracked_file_carries_a_contact_export_signature():
    hits = []
    for sig in CONTACT_SIGNATURES:
        r = subprocess.run(["git", "grep", "-lIF", sig], cwd=ROOT,
                           capture_output=True, text=True)
        hits += [(sig, f) for f in r.stdout.splitlines() if not _is_exempt(f)]
    assert not hits, f"contact-data signature in tracked files: {hits}"


def test_no_connections_export_is_tracked_outside_fixtures():
    bad = [f for f in _tracked_files()
           if os.path.basename(f).lower().startswith("connections")
           and f.lower().endswith((".csv", ".zip", ".json"))
           and not f.startswith(FIXTURE_DIR)]
    assert not bad, f"a connections export is tracked: {bad}"


def test_fixtures_use_only_reserved_example_domains():
    """Fixtures may look like an export but must not contain a reachable
    person. RFC 2606 reserves example.com/net/org precisely for this."""
    import re

    fixtures = [f for f in _tracked_files()
                if f.startswith(FIXTURE_DIR) and f.endswith(".csv")]
    assert fixtures, "the fixture exemption exists but no fixtures were found"
    email = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    allowed = {"example.com", "example.net", "example.org"}
    for f in fixtures:
        with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
            for domain in email.findall(fh.read()):
                assert domain.lower() in allowed, (
                    f"{f} contains a real-looking email domain: {domain}")


def test_no_network_target_output_is_tracked():
    bad = [f for f in _tracked_files()
           if "network_targets" in f or "network_report" in f]
    assert not bad, f"network output is tracked: {bad}"


def test_gitignore_covers_the_root_reports_directory_too():
    """job_search/.gitignore ignores its own reports/; the root one is separate
    and is where the leak actually happened."""
    with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
        ign = fh.read()
    for pattern in ("Connections.csv", "network_targets.csv"):
        assert pattern in ign, f"{pattern} is not ignored at the repo root"


def test_git_check_ignore_actually_rejects_a_contact_file():
    """Assert on behaviour, not on the text of the ignore file."""
    for path in ("reports/network_targets.csv", "Connections.csv",
                 "data/Connections.csv"):
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
        assert r.returncode == 0, f"{path} would still be committable"
