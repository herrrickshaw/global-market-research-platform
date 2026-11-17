#!/usr/bin/env python3
"""
hallmark quality gate integration for report synthesis.

Validates generated reports before publishing to catch:
  • Spelling & grammar errors
  • Contradictory statements
  • Missing data / placeholders
  • Malformed HTML/tables
  • Truncated content
  • Excessive repetition

Usage:
  from hallmark_report_integration import validate_and_publish_report

  result = validate_and_publish_report(
      html_content=html,
      report_name="Q2_Market_Analysis",
      expected_sections=["Introduction", "Analysis", "Conclusion"]
  )

  if result['publishable']:
      save_report(result['content'])
  else:
      log_violations(result['violations'])
      alert_team(result['summary'])
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import hallmark validator
sys.path.insert(0, str(Path(__file__).parent))
try:
    from hallmark_gate import HallmarkValidator, ValidationViolation
except ImportError:
    print("Error: hallmark_gate.py not found in scripts directory")
    sys.exit(1)


class ReportQualityGate:
    """Quality gate for report publication."""

    def __init__(self, strict_mode=False):
        """
        Args:
            strict_mode: If True, block on any errors. If False, warn on warnings.
        """
        self.validator = HallmarkValidator()
        self.strict_mode = strict_mode
        self.violations_log = Path("~/.ruflo/data/hallmark_violations.log").expanduser()

    def validate_report(
        self,
        html_content: str,
        report_name: str = "unnamed_report",
        expected_sections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate a generated HTML report before publication.

        Args:
            html_content: Full HTML report content
            report_name: Name for logging (e.g., "Q2_Market_Analysis")
            expected_sections: List of sections that should be present

        Returns:
            {
                "publishable": bool,
                "status": "published" | "warning" | "blocked",
                "violations": [ValidationViolation dict, ...],
                "severity_counts": {"error": N, "warning": N, "info": N},
                "summary": "Human-readable summary",
                "report_name": report_name,
                "timestamp": ISO datetime
            }
        """
        # Run validation
        result = self.validator.validate_report(
            html_content,
            expected_sections=expected_sections or ["Introduction", "Analysis", "Conclusion"]
        )

        # Determine publication status
        error_count = result["severity_counts"]["error"]
        warning_count = result["severity_counts"]["warning"]

        if self.strict_mode:
            publishable = error_count == 0
            status = "published" if publishable else "blocked"
        else:
            # Default mode: only block on errors, warn on warnings
            publishable = error_count == 0
            status = "published" if error_count == 0 and warning_count == 0 else \
                     "warning" if error_count == 0 else "blocked"

        # Build summary
        summary = self._build_summary(result, report_name)

        # Log violations
        self._log_violations(report_name, result, publishable)

        return {
            "publishable": publishable,
            "status": status,
            "violations": result["violations"],
            "severity_counts": result["severity_counts"],
            "summary": summary,
            "report_name": report_name,
            "timestamp": result["timestamp"],
        }

    def _build_summary(self, result: Dict[str, Any], report_name: str) -> str:
        """Build human-readable summary of violations."""
        error_count = result["severity_counts"]["error"]
        warning_count = result["severity_counts"]["warning"]
        info_count = result["severity_counts"]["info"]

        parts = [f"Report: {report_name}"]

        if error_count > 0:
            parts.append(f"🚫 {error_count} error{'s' if error_count != 1 else ''} (BLOCKED)")
        if warning_count > 0:
            parts.append(f"⚠️  {warning_count} warning{'s' if warning_count != 1 else ''} (CONTINUE WITH CAUTION)")
        if info_count > 0:
            parts.append(f"ℹ️  {info_count} info message{'s' if info_count != 1 else ''}")

        if error_count == 0 and warning_count == 0:
            parts.append("✅ PUBLISHED - All quality gates passed")

        return " | ".join(parts)

    def _log_violations(self, report_name: str, result: Dict[str, Any], publishable: bool) -> None:
        """Log validation results to disk."""
        if not result["violations"]:
            return  # No violations to log

        log_entry = {
            "timestamp": result["timestamp"],
            "report_name": report_name,
            "publishable": publishable,
            "violation_count": len(result["violations"]),
            "severity_counts": result["severity_counts"],
            "violations": result["violations"],
        }

        # Append to log file
        self.violations_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.violations_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def print_summary(self, result: Dict[str, Any]) -> None:
        """Print formatted summary for user."""
        print(f"\n{'='*70}")
        print(f"Quality Gate Report: {result['report_name']}")
        print(f"{'='*70}\n")

        # Status
        status_icon = "✅" if result["publishable"] else "❌"
        print(f"{status_icon} Status: {result['status'].upper()}")

        # Violation counts
        if result["severity_counts"]["error"] > 0:
            print(f"  🚫 Errors: {result['severity_counts']['error']}")
        if result["severity_counts"]["warning"] > 0:
            print(f"  ⚠️  Warnings: {result['severity_counts']['warning']}")
        if result["severity_counts"]["info"] > 0:
            print(f"  ℹ️  Info: {result['severity_counts']['info']}")

        # Violations
        if result["violations"]:
            print(f"\nViolations:")
            by_type = {}
            for v in result["violations"]:
                validator = v["validator"]
                if validator not in by_type:
                    by_type[validator] = []
                by_type[validator].append(v)

            for validator, violations in sorted(by_type.items()):
                print(f"\n  [{validator}]")
                for v in violations:
                    print(f"    • {v['message']}")

        print(f"\n{'='*70}\n")


def validate_and_publish_report(
    html_content: str,
    report_name: str = "unnamed_report",
    expected_sections: Optional[List[str]] = None,
    strict_mode: bool = False,
    on_warning: str = "continue"  # "continue", "block", "alert"
) -> Dict[str, Any]:
    """
    Convenience function: validate and optionally publish a report.

    Args:
        html_content: Full HTML report
        report_name: Name for logging
        expected_sections: Expected section headers
        strict_mode: If True, block on any error
        on_warning: What to do on warnings ("continue", "block", "alert")

    Returns:
        {
            "publishable": bool,
            "status": str,
            "content": html_content (unchanged),
            "violations": [...],
            "summary": str
        }
    """
    gate = ReportQualityGate(strict_mode=strict_mode)
    result = gate.validate_report(html_content, report_name, expected_sections)

    # Handle warnings per policy
    if on_warning == "block" and result["severity_counts"]["warning"] > 0:
        result["publishable"] = False
        result["status"] = "blocked"
    elif on_warning == "alert" and result["severity_counts"]["warning"] > 0:
        # Could send alert here (email, Slack, etc.)
        pass

    # Print summary
    gate.print_summary(result)

    # Add content to response
    result["content"] = html_content

    return result


def integrate_into_report_synthesizer():
    """
    Instructions for integrating hallmark into report_synthesizer.py:

    1. At the top of report_synthesizer.py, add:
       ```python
       import sys
       sys.path.insert(0, str(Path(__file__).parent.parent / ".ruflo" / "scripts"))
       from hallmark_report_integration import validate_and_publish_report
       ```

    2. In the synthesize_one() function, after generating HTML:
       ```python
       def synthesize_one(data_json, html_chart=None, formats=None):
           # ... existing code to generate html, docx, pptx ...

           # NEW: Validate HTML with hallmark
           result = validate_and_publish_report(
               html_content=html,
               report_name=f"report_{datetime.now().isoformat()}",
               expected_sections=["Purpose", "Data", "Methodology", "Retrieved"]
           )

           if not result['publishable']:
               # Option 1: Block publication
               raise Exception(f"Report failed quality gates: {result['summary']}")

               # Option 2: Warn but continue
               # log.warning(f"Report has quality issues: {result['summary']}")

           # Return validated content
           return html, docx, pptx
       ```

    3. (Optional) Create FastAPI validation endpoint:
       ```python
       from fastapi import APIRouter, HTTPException

       router = APIRouter(prefix='/api/validate', tags=['validation'])

       @router.post('/report-html')
       async def validate_report_html(html: str):
           result = validate_and_publish_report(html)
           return {
               "valid": result['publishable'],
               "status": result['status'],
               "violations": result['violations'],
               "severity": result['severity_counts']
           }
       ```

    4. (Optional) Add React frontend hook:
       ```javascript
       // frontend/src/hooks/useReportValidation.js
       export const useReportValidation = async (html) => {
           const response = await fetch('/api/validate/report-html', {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify({ html })
           });
           return response.json();
       };
       ```
    """
    pass


if __name__ == "__main__":
    # Test with sample HTML
    test_html = """
    <html>
    <body>
    <h1>Market Analysis Report</h1>
    <p>This report analizes market trends for Q2 2026.</p>
    <table>
    <tr><th>Index</th><th>Value</th></tr>
    <tr><td>NIFTY50</td><td>24,500</td></tr>
    </table>
    <p>The data is 100% complete.</p>
    </body>
    </html>
    """

    print("Testing hallmark report validation...")
    result = validate_and_publish_report(test_html, "Test_Report")

    print(f"\nResult: {result['status']}")
    print(f"Publishable: {result['publishable']}")
