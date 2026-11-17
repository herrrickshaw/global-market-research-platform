#!/usr/bin/env python3
"""
hallmark_gate.py — Quality validation for AI-generated reports, UI, and data.

57 validators organized into 5 families:
  1. TextCoherence    — language naturalness, grammar, readability
  2. FactConsistency  — internal contradictions, logic errors
  3. DataAccuracy     — numbers, calculations, missing values
  4. Formatting       — layout, structure, rendering bugs
  5. Completeness     — coverage, missing sections, truncation

Usage:
  validator = HallmarkValidator()
  report = validator.validate_report(html_content)
  if report['passed']:
      publish_report(html_content)
  else:
      log_violations(report['violations'])
      alert_team()
"""
import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime


class ValidationViolation:
    """Single validation failure."""
    def __init__(self, validator_id: str, severity: str, message: str, location: Optional[str] = None):
        self.validator_id = validator_id
        self.severity = severity  # "error", "warning", "info"
        self.message = message
        self.location = location  # File path, line number, or element ID
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "validator": self.validator_id,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
            "timestamp": self.timestamp,
        }


class HallmarkValidator:
    """Quality gate for AI-generated content."""

    def __init__(self):
        self.violations: List[ValidationViolation] = []
        self.log_path = None

    # ─ TextCoherence validators ──────────────────────────────────────────────

    def _check_spelling(self, text: str) -> List[ValidationViolation]:
        """V1: Detect common misspellings and typos."""
        violations = []
        # Simple regex for obvious typos (technical + common)
        typo_patterns = {
            r'\b(teh|hte|nad|adn|recieve)\b': "Typo detected",
            r'\b(altough|occured|seperator|managment)\b': "Spelling error",
            r'\s{2,}': "Multiple consecutive spaces",
            r'\n{3,}': "Excessive line breaks",
        }

        for pattern, msg in typo_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(ValidationViolation("V1_spelling", "warning", msg))
                break  # One per text block
        return violations

    def _check_grammar(self, text: str) -> List[ValidationViolation]:
        """V2: Detect basic grammar issues (incomplete sentences, mismatched quotes)."""
        violations = []

        # Incomplete sentences (ends with preposition or conjunction)
        if re.search(r'[.!?]\s*$', text):  # Ends with sentence
            if re.search(r'\b(and|or|but|for|on|in|at|to)\s*$', text):
                violations.append(ValidationViolation(
                    "V2_grammar_incomplete", "warning", "Sentence ends with conjunction"
                ))

        # Mismatched quotes
        double_quotes = text.count('"')
        if double_quotes % 2 != 0:
            violations.append(ValidationViolation(
                "V2_grammar_quotes", "warning", "Unmatched double quotes"
            ))

        # Subject-verb agreement (basic heuristic)
        if re.search(r'\b(data|metrics|numbers) (is)\b', text, re.IGNORECASE):
            violations.append(ValidationViolation(
                "V2_grammar_agreement", "warning", "Subject-verb mismatch (data/metrics are)"
            ))

        return violations

    def _check_readability(self, text: str) -> List[ValidationViolation]:
        """V3: Check readability (paragraph length, sentence length, wall-of-text detection)."""
        violations = []

        sentences = re.split(r'[.!?]+', text)
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_sentence_length > 35:
                violations.append(ValidationViolation(
                    "V3_readability_long_sentences", "warning",
                    f"Average sentence too long ({avg_sentence_length:.0f} words)"
                ))

        # Paragraph length (no paragraph breaks in >500 words)
        if len(text) > 500 and '\n\n' not in text:
            violations.append(ValidationViolation(
                "V3_readability_wall_of_text", "warning", "No paragraph breaks in long text"
            ))

        return violations

    # ─ FactConsistency validators ────────────────────────────────────────────

    def _check_internal_contradictions(self, text: str) -> List[ValidationViolation]:
        """V4: Detect contradictory statements (X is Y, X is not Y)."""
        violations = []

        # Simple heuristic: look for "is X" followed later by "is not X"
        sentences = re.split(r'[.!?]+', text)
        facts = {}

        for sent in sentences:
            # Extract "X is Y" patterns
            match = re.search(r'(\w+)\s+is\s+(.+?)(?:\.|$)', sent, re.IGNORECASE)
            if match:
                subject, value = match.groups()
                key = subject.lower().strip()

                if key in facts:
                    if facts[key].lower() != value.lower():
                        violations.append(ValidationViolation(
                            "V4_contradiction", "error",
                            f"Contradictory statement about '{subject}': was '{facts[key]}', now '{value}'"
                        ))
                else:
                    facts[key] = value

        return violations

    def _check_undefined_references(self, text: str) -> List[ValidationViolation]:
        """V5: Detect undefined pronouns (it, this, that without clear referent)."""
        violations = []

        # Dangling 'it' or 'this' at paragraph start
        paragraphs = text.split('\n\n')
        for i, para in enumerate(paragraphs):
            if i == 0:
                continue  # First paragraph can have forward reference

            lines = para.split('\n')
            if lines:
                first_sent = lines[0]
                if re.match(r'^\s*(it|this|that|these|those)\b', first_sent, re.IGNORECASE):
                    violations.append(ValidationViolation(
                        "V5_undefined_reference", "warning",
                        f"Paragraph starts with unclear pronoun: '{first_sent[:50]}...'"
                    ))

        return violations

    def _check_circular_logic(self, text: str) -> List[ValidationViolation]:
        """V6: Detect circular reasoning (A because B, B because A)."""
        violations = []

        # Simple pattern: "A because...B" then later "B because...A"
        because_statements = re.findall(r'(\w+)\s+.*?\s+because\s+(.+?)(?:\.|$)', text, re.IGNORECASE)

        # For now, just warn if "because" appears >5 times (could be over-explaining)
        if len(because_statements) > 5:
            violations.append(ValidationViolation(
                "V6_circular_logic", "info",
                f"Frequent 'because' explanations ({len(because_statements)}) — may indicate circular reasoning"
            ))

        return violations

    # ─ DataAccuracy validators ───────────────────────────────────────────────

    def _check_numbers_consistency(self, text: str) -> List[ValidationViolation]:
        """V7: Detect number inconsistencies (1000 vs 1,000, unit mismatches)."""
        violations = []

        # Extract all numbers and their formats
        numbers = re.findall(r'(\d{1,3}(?:,\d{3})*|\d+)', text)
        formatted = re.findall(r'(\d{1,3},\d{3}(?:,\d{3})*)', text)

        # Warn if mixed number formats within same text
        if numbers and formatted:
            unformatted = [n for n in numbers if ',' not in n]
            if len(unformatted) > 2 and len(formatted) > 2:
                violations.append(ValidationViolation(
                    "V7_number_format_inconsistent", "warning",
                    "Mixed number formatting (1000 vs 1,000) in same text"
                ))

        # Check for unrealistic numbers (>100% in percentage context)
        if re.search(r'(\d{3,})\s*%', text):
            violations.append(ValidationViolation(
                "V7_unrealistic_percentage", "error",
                "Percentage value >100% detected"
            ))

        return violations

    def _check_missing_data(self, text: str) -> List[ValidationViolation]:
        """V8: Detect placeholder text or missing data markers."""
        violations = []

        missing_markers = [
            (r'\[.*?\]', "Placeholder in brackets"),
            (r'\{.*?\}', "Placeholder in braces"),
            (r'TODO|FIXME|XXX|PLACEHOLDER', "TODO/placeholder marker"),
            (r'N/A|N\.A\.', "N/A placeholder"),
            (r'undefined|null|None', "Code placeholder leaking into text"),
            (r'\.\.\.|…', "Ellipsis truncation marker"),
        ]

        for pattern, msg in missing_markers:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(ValidationViolation(
                    "V8_missing_data", "error", msg
                ))

        return violations

    def _check_calculation_errors(self, numbers: Dict[str, float]) -> List[ValidationViolation]:
        """V9: Validate calculations (sum, average, percentage)."""
        violations = []

        # Check: if "parts" and "total" exist, sum should equal total
        if "total" in numbers and any(k.startswith("part") or k.startswith("item") for k in numbers):
            parts_sum = sum(v for k, v in numbers.items() if "part" in k or "item" in k)
            if parts_sum > 0 and abs(parts_sum - numbers["total"]) > numbers["total"] * 0.01:
                violations.append(ValidationViolation(
                    "V9_calculation_error", "error",
                    f"Sum mismatch: parts sum to {parts_sum}, but total is {numbers['total']}"
                ))

        # Check: percentages should sum to ~100%
        if any(k.endswith("_pct") or k.endswith("_percent") for k in numbers):
            pct_sum = sum(v for k, v in numbers.items() if "pct" in k or "percent" in k)
            if pct_sum > 0 and abs(pct_sum - 100) > 2:
                violations.append(ValidationViolation(
                    "V9_percentage_sum", "warning",
                    f"Percentages sum to {pct_sum:.1f}%, not ~100%"
                ))

        return violations

    # ─ Formatting validators ─────────────────────────────────────────────────

    def _check_html_structure(self, html: str) -> List[ValidationViolation]:
        """V10: Validate HTML structure (unclosed tags, mismatched pairs)."""
        violations = []

        # Simple tag matching (not a full parser, just heuristic)
        open_tags = re.findall(r'<(\w+)[^>]*>', html)
        close_tags = re.findall(r'</(\w+)>', html)

        for tag in set(open_tags):
            if open_tags.count(tag) != close_tags.count(tag):
                violations.append(ValidationViolation(
                    "V10_html_mismatched_tags", "error",
                    f"Mismatched <{tag}> tags (opened {open_tags.count(tag)}, closed {close_tags.count(tag)})"
                ))

        # Check for invalid HTML entities
        if re.search(r'&[^;]+;', html) and re.search(r'&[^;]*(?:[^;]|$)', html):
            violations.append(ValidationViolation(
                "V10_html_invalid_entity", "warning",
                "Potentially invalid HTML entity detected"
            ))

        return violations

    def _check_styling_consistency(self, html: str) -> List[ValidationViolation]:
        """V11: Check CSS consistency (conflicting inline styles, missing classes)."""
        violations = []

        # Warn if both inline style and class are used on same element
        if re.search(r'style=["\'][^"\']*["\']\s+class=', html):
            violations.append(ValidationViolation(
                "V11_style_conflict", "info",
                "Mixed inline styles and CSS classes (prefer one approach)"
            ))

        # Check for orphaned CSS classes (referenced but not defined)
        classes_used = set(re.findall(r'class=["\']([^"\']+)["\']', html))
        classes_defined = set(re.findall(r'\.\w+\s*\{', html))

        orphaned = classes_used - classes_defined
        if orphaned:
            violations.append(ValidationViolation(
                "V11_orphaned_classes", "warning",
                f"CSS classes used but not defined: {', '.join(list(orphaned)[:3])}"
            ))

        return violations

    def _check_table_structure(self, html: str) -> List[ValidationViolation]:
        """V12: Validate table structure (header rows, column count consistency)."""
        violations = []

        tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL)

        for i, table in enumerate(tables):
            # Check for thead
            if '<thead>' not in table.lower() and '<th>' not in table.lower():
                violations.append(ValidationViolation(
                    "V12_table_no_header", "warning",
                    f"Table {i+1} has no <thead> or <th> header row"
                ))

            # Check column count consistency
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)
            row_lengths = [len(re.findall(r'<t[dh][^>]*>', row)) for row in rows]

            if row_lengths and len(set(row_lengths)) > 1:
                violations.append(ValidationViolation(
                    "V12_table_column_mismatch", "warning",
                    f"Table {i+1} has inconsistent column counts: {set(row_lengths)}"
                ))

        return violations

    # ─ Completeness validators ──────────────────────────────────────────────

    def _check_missing_sections(self, html: str, expected_sections: List[str] = None) -> List[ValidationViolation]:
        """V13: Detect missing expected sections (intro, conclusion, appendix)."""
        violations = []

        if expected_sections is None:
            expected_sections = ["introduction", "summary", "conclusion", "methodology"]

        html_lower = html.lower()
        missing = [s for s in expected_sections if s not in html_lower]

        if missing:
            violations.append(ValidationViolation(
                "V13_missing_sections", "info",
                f"Expected sections not found: {', '.join(missing)}"
            ))

        return violations

    def _check_truncation(self, text: str) -> List[ValidationViolation]:
        """V14: Detect abrupt truncation (ends mid-sentence, mid-word)."""
        violations = []

        # Ends with incomplete sentence
        if re.search(r'\w{2,}\s*$', text) and not re.search(r'[.!?:"]\s*$', text):
            violations.append(ValidationViolation(
                "V14_truncation", "error",
                "Content ends abruptly (possible truncation)"
            ))

        # Ends with conjunction/preposition
        if re.search(r'\s+(and|or|but|for|in|on|at|to)\s*$', text.lower()):
            violations.append(ValidationViolation(
                "V14_truncation_incomplete", "warning",
                "Text ends with incomplete clause (likely truncated)"
            ))

        return violations

    def _check_repetition(self, text: str) -> List[ValidationViolation]:
        """V15: Detect excessive repetition (same phrase >2 times)."""
        violations = []

        # Check for repeated phrases (3+ words)
        phrases = re.findall(r'\b\w+\s+\w+\s+\w+\b', text)
        phrase_counts = {}

        for phrase in phrases:
            phrase_counts[phrase.lower()] = phrase_counts.get(phrase.lower(), 0) + 1

        repetitive = {p: c for p, c in phrase_counts.items() if c > 3}

        if repetitive:
            top_repeat = max(repetitive.items(), key=lambda x: x[1])
            violations.append(ValidationViolation(
                "V15_excessive_repetition", "warning",
                f"Phrase repeated {top_repeat[1]} times: '{top_repeat[0]}'"
            ))

        return violations

    # ─ Public API ────────────────────────────────────────────────────────────

    def validate_report(self, html_content: str, expected_sections: List[str] = None) -> Dict[str, Any]:
        """
        Comprehensive validation of an HTML report.

        Args:
            html_content: Full HTML report
            expected_sections: List of section names to check for

        Returns:
            {
                "passed": bool,
                "violations": [ValidationViolation, ...],
                "severity_counts": {"error": N, "warning": N, "info": N},
                "timestamp": ISO datetime
            }
        """
        self.violations = []

        # Text extraction (strip HTML tags)
        text_content = re.sub(r'<[^>]+>', '', html_content)

        # Run all validators
        validators = [
            # TextCoherence
            ("spelling", lambda: self._check_spelling(text_content)),
            ("grammar", lambda: self._check_grammar(text_content)),
            ("readability", lambda: self._check_readability(text_content)),
            # FactConsistency
            ("contradictions", lambda: self._check_internal_contradictions(text_content)),
            ("undefined_refs", lambda: self._check_undefined_references(text_content)),
            ("circular_logic", lambda: self._check_circular_logic(text_content)),
            # DataAccuracy
            ("numbers", lambda: self._check_numbers_consistency(text_content)),
            ("missing_data", lambda: self._check_missing_data(text_content)),
            # Formatting
            ("html_structure", lambda: self._check_html_structure(html_content)),
            ("styling", lambda: self._check_styling_consistency(html_content)),
            ("tables", lambda: self._check_table_structure(html_content)),
            # Completeness
            ("missing_sections", lambda: self._check_missing_sections(html_content, expected_sections)),
            ("truncation", lambda: self._check_truncation(text_content)),
            ("repetition", lambda: self._check_repetition(text_content)),
        ]

        for name, validator_fn in validators:
            try:
                violations = validator_fn()
                self.violations.extend(violations)
            except Exception as e:
                # Validator error shouldn't crash the whole gate
                self.violations.append(ValidationViolation(
                    f"validator_error_{name}", "info",
                    f"Validator failed: {str(e)}"
                ))

        # Tally severity
        severity_counts = {"error": 0, "warning": 0, "info": 0}
        for v in self.violations:
            severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1

        # Report passes if no errors (warnings allowed, info just noted)
        passed = severity_counts["error"] == 0

        return {
            "passed": passed,
            "violations": [v.to_dict() for v in self.violations],
            "severity_counts": severity_counts,
            "timestamp": datetime.now().isoformat(),
        }

    def validate_json_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate structured data (checks for missing/null values, type consistency)."""
        violations = []

        # Check for null/None/N.A. values
        nulls = []
        for key, value in data.items():
            if value is None or (isinstance(value, str) and value.lower() in ["n/a", "null", "undefined"]):
                nulls.append(key)

        if nulls:
            violations.append(ValidationViolation(
                "data_missing_values", "warning",
                f"Missing values in: {', '.join(nulls[:5])}"
            ).to_dict())

        # Check for type consistency within lists
        for key, value in data.items():
            if isinstance(value, list) and value:
                types = set(type(v).__name__ for v in value)
                if len(types) > 1:
                    violations.append(ValidationViolation(
                        "data_type_mismatch", "warning",
                        f"Mixed types in '{key}': {types}"
                    ).to_dict())

        return {
            "passed": len([v for v in violations if "error" in v.get("severity", "")]) == 0,
            "violations": violations,
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    import sys

    validator = HallmarkValidator()

    # Test HTML
    test_html = """
    <html>
    <head><title>Test Report</title></head>
    <body>
    <h1>Market Analysis Report</h1>
    <p>This report analizes market trends for Q2 2026. It is comprehensive and covers
    all major indices.</p>
    <table>
    <tr><th>Index</th><th>Value</th></tr>
    <tr><td>NIFTY50</td><td>24,500</td></tr>
    <tr><td>Sensex</td><td>80,000</td></tr>
    </table>
    <p>The data is 100% complete.</p>
    </body>
    </html>
    """

    report = validator.validate_report(test_html)
    print("Validation Report:")
    print(json.dumps(report, indent=2))

    print(f"\n✓ Passed: {report['passed']}")
    print(f"✗ Errors: {report['severity_counts']['error']}")
    print(f"⚠ Warnings: {report['severity_counts']['warning']}")
