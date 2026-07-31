"""
REST endpoints for content validation using hallmark quality gates.

Exposes hallmark validators via FastAPI for:
  - Real-time HTML report validation
  - Violations tracking and trending
  - Validator health/availability status
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Optional
import sys
from pathlib import Path
import json
from datetime import date

# Import hallmark
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".ruflo" / "scripts"))
try:
    from hallmark_report_integration import validate_and_publish_report, ReportQualityGate
    HALLMARK_AVAILABLE = True
except ImportError:
    HALLMARK_AVAILABLE = False

router = APIRouter(prefix='/api/validate', tags=['validation'])


# ─ Request/Response Models ────────────────────────────────────────────────
class ValidationRequest(BaseModel):
    html: str
    report_name: str = "unnamed"
    expected_sections: Optional[List[str]] = None


class ValidationResponse(BaseModel):
    publishable: bool
    status: str
    violations: List[dict]
    severity_counts: dict
    summary: str


@router.post('/report-html', response_model=ValidationResponse)
async def validate_report_html(request: ValidationRequest):
    """
    Validate a generated HTML report using hallmark quality gates.

    Body:
        {
            "html": str (required, min 100 chars),
            "report_name": str (default: "unnamed"),
            "expected_sections": [str] (optional)
        }

    Returns:
        {
            "publishable": bool,
            "status": "published" | "warning" | "blocked",
            "violations": [...],
            "severity_counts": {"error": int, "warning": int, "info": int},
            "summary": str
        }
    """
    if not HALLMARK_AVAILABLE:
        raise HTTPException(503, "hallmark validators unavailable")

    if not request.html or len(request.html) < 100:
        raise HTTPException(400, "HTML content required (min 100 chars)")

    try:
        result = await run_in_threadpool(
            validate_and_publish_report,
            request.html,
            request.report_name,
            request.expected_sections or ["Introduction", "Analysis", "Conclusion"],
            False,  # strict_mode=False
            "continue"  # on_warning
        )

        return {
            "publishable": result['publishable'],
            "status": result['status'],
            "violations": result['violations'],
            "severity_counts": result['severity_counts'],
            "summary": result['summary']
        }
    except Exception as e:
        raise HTTPException(500, f"Validation failed: {str(e)}")


@router.get('/violations/today')
async def get_today_violations():
    """
    Get all quality violations from today's reports.

    Useful for monitoring report quality trends and identifying patterns.

    Returns:
        {
            "violations": [
                {
                    "timestamp": "2026-07-31T08:02:03.822447",
                    "report_name": str,
                    "publishable": bool,
                    "violation_count": int,
                    "severity_counts": {"error": int, "warning": int, "info": int},
                    "violations": [...]
                },
                ...
            ],
            "count": int (total violations today),
            "total_errors": int,
            "total_warnings": int
        }
    """
    violations_log = Path("~/.ruflo/data/hallmark_violations.log").expanduser()

    if not violations_log.exists():
        return {
            "violations": [],
            "count": 0,
            "total_errors": 0,
            "total_warnings": 0
        }

    today = date.today().isoformat()
    today_violations = []

    try:
        with open(violations_log) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", "").startswith(today):
                        today_violations.append(entry)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines
    except Exception as e:
        raise HTTPException(500, f"Failed to read violations log: {str(e)}")

    total_errors = sum(
        v.get("severity_counts", {}).get("error", 0)
        for v in today_violations
    )
    total_warnings = sum(
        v.get("severity_counts", {}).get("warning", 0)
        for v in today_violations
    )

    return {
        "violations": today_violations,
        "count": len(today_violations),
        "total_errors": total_errors,
        "total_warnings": total_warnings
    }


@router.get('/violations/summary')
async def get_violations_summary(days: int = 7):
    """
    Get summary statistics of violations over the past N days.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        {
            "total_reports_validated": int,
            "reports_publishable": int,
            "reports_blocked": int,
            "error_count": int,
            "warning_count": int,
            "info_count": int,
            "error_rate": float (percentage),
            "most_common_violations": [
                {"validator": str, "count": int}
            ]
        }
    """
    violations_log = Path("~/.ruflo/data/hallmark_violations.log").expanduser()

    if not violations_log.exists():
        return {
            "total_reports_validated": 0,
            "reports_publishable": 0,
            "reports_blocked": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "error_rate": 0.0,
            "most_common_violations": []
        }

    from datetime import datetime, timedelta

    cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
    total_reports = 0
    publishable_reports = 0
    violation_counts = {}

    try:
        with open(violations_log) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", "").startswith(cutoff_date) or \
                       entry.get("timestamp", "") > cutoff_date:
                        total_reports += 1
                        if entry.get("publishable"):
                            publishable_reports += 1

                        # Count violations by type
                        for violation in entry.get("violations", []):
                            validator = violation.get("validator", "unknown")
                            violation_counts[validator] = violation_counts.get(validator, 0) + 1
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        raise HTTPException(500, f"Failed to read violations log: {str(e)}")

    # Sort most common violations
    most_common = sorted(
        [{"validator": k, "count": v} for k, v in violation_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]

    error_rate = (100.0 * (total_reports - publishable_reports) / total_reports) \
        if total_reports > 0 else 0.0

    return {
        "total_reports_validated": total_reports,
        "reports_publishable": publishable_reports,
        "reports_blocked": total_reports - publishable_reports,
        "error_count": sum(v.get("severity_counts", {}).get("error", 0)
                          for v in [json.loads(l) for l in open(violations_log)
                                   if l.strip() and l.startswith(cutoff_date)]),
        "warning_count": sum(v.get("severity_counts", {}).get("warning", 0)
                            for v in [json.loads(l) for l in open(violations_log)
                                     if l.strip() and l.startswith(cutoff_date)]),
        "info_count": sum(v.get("severity_counts", {}).get("info", 0)
                         for v in [json.loads(l) for l in open(violations_log)
                                  if l.strip() and l.startswith(cutoff_date)]),
        "error_rate": error_rate,
        "most_common_violations": most_common
    }


@router.get('/status')
async def validation_status():
    """
    Get hallmark validator health and availability.

    Returns:
        {
            "status": "healthy" | "unavailable",
            "validators_available": int,
            "violations_log": str (path),
            "violations_today": int,
            "timestamp": str (ISO datetime)
        }
    """
    if not HALLMARK_AVAILABLE:
        raise HTTPException(503, "hallmark validators unavailable")

    violations_log = Path("~/.ruflo/data/hallmark_violations.log").expanduser()
    violations_today = 0

    if violations_log.exists():
        today = date.today().isoformat()
        try:
            with open(violations_log) as f:
                for line in f:
                    if line.strip() and line.startswith(today):
                        violations_today += 1
        except Exception:
            pass

    from datetime import datetime

    return {
        "status": "healthy",
        "validators_available": 15,
        "violations_log": str(violations_log),
        "violations_today": violations_today,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get('/validators/list')
async def list_validators():
    """
    List all available hallmark validators and their descriptions.

    Returns:
        {
            "validators": [
                {
                    "id": "V1_spelling",
                    "family": "TextCoherence",
                    "description": str,
                    "severity": "error" | "warning" | "info"
                },
                ...
            ]
        }
    """
    if not HALLMARK_AVAILABLE:
        raise HTTPException(503, "hallmark validators unavailable")

    # Try to get validator list from hallmark_gate
    try:
        from hallmark_gate import HallmarkValidator
        validator = HallmarkValidator()
        # Return a simplified list of validators
        validators_info = [
            {
                "id": "V1_spelling",
                "family": "TextCoherence",
                "description": "Check for spelling errors and typos",
                "severity": "warning"
            },
            {
                "id": "V2_grammar",
                "family": "TextCoherence",
                "description": "Check for grammar issues and malformed quotes",
                "severity": "warning"
            },
            {
                "id": "V3_readability",
                "family": "TextCoherence",
                "description": "Check readability metrics (Flesch-Kincaid)",
                "severity": "info"
            },
            {
                "id": "V4_contradictions",
                "family": "FactConsistency",
                "description": "Detect contradictory statements",
                "severity": "error"
            },
            {
                "id": "V5_undefined_refs",
                "family": "FactConsistency",
                "description": "Find undefined references",
                "severity": "error"
            },
            {
                "id": "V6_circular_logic",
                "family": "FactConsistency",
                "description": "Detect circular logic patterns",
                "severity": "error"
            },
            {
                "id": "V7_number_format",
                "family": "DataAccuracy",
                "description": "Validate number formatting",
                "severity": "warning"
            },
            {
                "id": "V8_missing_data",
                "family": "DataAccuracy",
                "description": "Detect missing data and placeholders",
                "severity": "error"
            },
            {
                "id": "V9_calculations",
                "family": "DataAccuracy",
                "description": "Check calculation accuracy",
                "severity": "error"
            },
            {
                "id": "V10_html_structure",
                "family": "Formatting",
                "description": "Validate HTML structure",
                "severity": "error"
            },
            {
                "id": "V11_css_consistency",
                "family": "Formatting",
                "description": "Check CSS consistency",
                "severity": "warning"
            },
            {
                "id": "V12_table_structure",
                "family": "Formatting",
                "description": "Validate table structure",
                "severity": "error"
            },
            {
                "id": "V13_missing_sections",
                "family": "Completeness",
                "description": "Check for missing expected sections",
                "severity": "error"
            },
            {
                "id": "V14_truncation",
                "family": "Completeness",
                "description": "Detect truncated content",
                "severity": "warning"
            },
            {
                "id": "V15_repetition",
                "family": "Completeness",
                "description": "Check for excessive repetition",
                "severity": "info"
            },
        ]

        return {"validators": validators_info}
    except Exception as e:
        raise HTTPException(500, f"Failed to list validators: {str(e)}")
