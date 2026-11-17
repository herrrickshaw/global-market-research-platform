#!/usr/bin/env python3
"""
Example: How to integrate hallmark_gate into your report_synthesizer.py

This shows the integration pattern. Drop this into your report pipeline
after HTML/DOCX/PPTX generation to validate before publishing.
"""

import json
import sys
from pathlib import Path

# Import hallmark validator
sys.path.insert(0, str(Path(__file__).parent))
from hallmark_gate import HallmarkValidator


def synthesize_report_with_quality_gate(data: dict, format: str = "html") -> dict:
    """
    Example: Report generation with hallmark validation gate.

    Args:
        data: Report data (JSON structure)
        format: Output format (html, docx, pptx)

    Returns:
        {
            "report": <content>,
            "format": format,
            "validation": <hallmark report>,
            "status": "published" | "blocked" | "warning"
        }
    """
    validator = HallmarkValidator()

    # Step 1: Generate report (existing code)
    report_content = generate_report_html(data)  # Your existing function

    # Step 2: Validate with hallmark
    expected_sections = ["Introduction", "Analysis", "Methodology", "Conclusion"]
    validation_result = validator.validate_report(report_content, expected_sections)

    # Step 3: Decide whether to publish
    status = "blocked" if not validation_result["passed"] else \
             "warning" if validation_result["severity_counts"]["warning"] > 0 else \
             "published"

    # Step 4: Log violations
    if validation_result["violations"]:
        log_violations(validation_result["violations"], report_content)

    return {
        "report": report_content,
        "format": format,
        "validation": validation_result,
        "status": status,
    }


def log_violations(violations: list, report_snippet: str) -> None:
    """Log validation violations for review/debugging."""
    log_entry = {
        "timestamp": violations[0]["timestamp"] if violations else None,
        "violation_count": len(violations),
        "violations": violations,
        "report_preview": report_snippet[:200],  # First 200 chars
    }

    # Append to hallmark violations log
    log_path = Path("~/.ruflo/data/hallmark_violations.log").expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Print for immediate feedback
    print(f"\n⚠ Quality Gate Alert: {len(violations)} violations found")
    print(f"  Errors: {sum(1 for v in violations if v['severity'] == 'error')}")
    print(f"  Warnings: {sum(1 for v in violations if v['severity'] == 'warning')}")
    print(f"  Info: {sum(1 for v in violations if v['severity'] == 'info')}")


# ─ Integration points ────────────────────────────────────────────────────────

def integrate_into_report_synthesizer():
    """
    Pseudo-code showing where to add hallmark in report_synthesizer.py:

    # Inside report_synthesizer.py, after synthesize_one():

    def synthesize_one(data_json, html_chart=None):
        # ... existing synthesis code ...
        html_content = build_html(data_json)
        docx_content = build_docx(data_json)
        pptx_content = build_pptx(data_json)

        # NEW: Validate with hallmark
        validator = HallmarkValidator()

        html_validation = validator.validate_report(html_content)
        if not html_validation["passed"]:
            log.warning(f"HTML validation failed: {html_validation['severity_counts']}")
            # Option 1: Block publication
            raise ReportValidationError(f"Report failed quality gates")
            # Option 2: Warn but continue
            # log.warning("Proceeding with warnings")

        # If validation passed, return report
        return html_content, docx_content, pptx_content
    """
    pass


# ─ React frontend integration ────────────────────────────────────────────────

def create_hallmark_validation_endpoint():
    """
    Pseudo-code showing FastAPI endpoint to validate UI before rendering.

    # In backend/routers/validate.py:

    from fastapi import APIRouter
    from hallmark_gate import HallmarkValidator

    router = APIRouter()

    @router.post("/api/validate/report-html")
    async def validate_report_html(html: str, expected_sections: List[str] = None):
        validator = HallmarkValidator()
        result = validator.validate_report(html, expected_sections)
        return {
            "valid": result["passed"],
            "violations": result["violations"],
            "severity": result["severity_counts"]
        }

    # Frontend (React) can then call this before rendering:
    # POST /api/validate/report-html with the generated HTML
    # If validation fails, show warnings to user
    """
    pass


# ─ Example: Table validation ─────────────────────────────────────────────────

def validate_results_table(table_html: str) -> dict:
    """Validate a results table specifically."""
    validator = HallmarkValidator()

    # Extract just the table portion
    violations = []
    violations.extend(validator._check_table_structure(table_html))
    violations.extend(validator._check_numbers_consistency(table_html))
    violations.extend(validator._check_missing_data(table_html))

    return {
        "passed": len([v for v in violations if v.severity == "error"]) == 0,
        "violations": [v.to_dict() for v in violations],
    }


if __name__ == "__main__":
    # Test: Validate a sample report
    sample_data = {
        "title": "Q2 2026 Market Analysis",
        "data": {
            "nifty50": 24500,
            "sensex": 80000,
            "growth_pct": 5.2,
        }
    }

    # Simulated report generation
    def generate_report_html(data):
        return f"""
        <html>
        <body>
        <h1>{data['title']}</h1>
        <p>Growth: {data['data']['growth_pct']}%</p>
        <table>
        <tr><th>Index</th><th>Value</th></tr>
        <tr><td>NIFTY50</td><td>{data['data']['nifty50']:,}</td></tr>
        <tr><td>Sensex</td><td>{data['data']['sensex']:,}</td></tr>
        </table>
        </body>
        </html>
        """

    # Test the integration
    result = synthesize_report_with_quality_gate(sample_data, format="html")

    print("Report Validation Result:")
    print(f"Status: {result['status']}")
    print(f"Valid: {result['validation']['passed']}")
    print(f"Violations: {result['validation']['severity_counts']}")

    if result['validation']['violations']:
        print("\nDetailed violations:")
        for v in result['validation']['violations']:
            print(f"  [{v['severity'].upper()}] {v['validator']}: {v['message']}")
