#!/usr/bin/env python3
"""
create_test_edinet_xbrl.py — Create test XBRL ZIP for pipeline validation.

Generates realistic XBRL stubs for a few TSE companies so you can test the
full process (parse → Postgres → archive) without waiting for real EDINET files.

Usage:
  python3 create_test_edinet_xbrl.py --dest /tmp
  bash scripts/edinet_process_and_archive.sh  # Will process test files
"""

import io
import sys
import zipfile
from pathlib import Path


def create_sample_xbrl(tse_code: str, company_name: str, fiscal_period: str) -> str:
    """Create a sample XBRL document for a TSE company."""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:jppfs="http://disclosure.edinet-fsa.go.jp/jppfs/tse-acedjpfr-20240101"
      xmlns:jpfr="http://disclosure.edinet-fsa.go.jp/jpfr/tse-acedjpfr-20240101"
      xmlns:jpdei="http://disclosure.edinet-fsa.go.jp/jpdei/tse-acedjpfr-20240101">

  <!-- Company Context -->
  <jpdei:EntityCode>{tse_code}</jpdei:EntityCode>
  <jpdei:CompanyName>{company_name}</jpdei:CompanyName>
  <jpdei:FiscalPeriod>{fiscal_period}</jpdei:FiscalPeriod>
  <jpdei:FilingDate>2024-11-15</jpdei:FilingDate>

  <!-- Income Statement (Quarterly/Annual) -->
  <jpfr:NetSalesJFY>1234567890000</jpfr:NetSalesJFY>
  <jpfr:CostOfSalesJFY>617283945000</jpfr:CostOfSalesJFY>
  <jpfr:OperatingIncomeJFY>308641972500</jpfr:OperatingIncomeJFY>
  <jpfr:NetIncomeJFY>246913578000</jpfr:NetIncomeJFY>

  <!-- Balance Sheet -->
  <jppfs:TotalAssetsJFY>4938271605000</jppfs:TotalAssetsJFY>
  <jppfs:TotalLiabilitiesJFY>1975308642000</jppfs:TotalLiabilitiesJFY>
  <jppfs:ShareholdersEquityJFY>2962962963000</jppfs:ShareholdersEquityJFY>

  <!-- Cash Flow -->
  <jpfr:OperatingCashFlowJFY>308641972500</jpfr:OperatingCashFlowJFY>
  <jpfr:InvestmentCashFlowJFY>-123456789000</jpfr:InvestmentCashFlowJFY>
  <jpfr:FreeCashFlowJFY>185185183500</jpfr:FreeCashFlowJFY>

  <!-- Derived Metrics (will be computed from above) -->
  <jpfr:ReturnOnEquityJFY>0.0833</jpfr:ReturnOnEquityJFY>
  <jpfr:ReturnOnAssetsJFY>0.0500</jpfr:ReturnOnAssetsJFY>
  <jpfr:DebtToEquityJFY>0.6667</jpfr:DebtToEquityJFY>

</xbrl>
"""


def create_test_zip(dest: Path, period: str = "FY2024Q3"):
    """Create test XBRL ZIP with a few sample companies."""

    # Sample TSE companies for testing
    companies = [
        ("8001", "Toyota Motor Corp"),
        ("7203", "Honda Motor Co"),
        ("6098", "Nippon Steel Corp"),
    ]

    filename = f"EDINET_XBRL_2024Q3_TEST.zip"
    filepath = dest / filename

    print(f"[INFO] Creating test XBRL ZIP: {filename}")
    print(f"  Period: {period}")
    print(f"  Companies: {len(companies)}")
    print()

    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for tse_code, company_name in companies:
            # Create XBRL content
            xbrl_content = create_sample_xbrl(tse_code, company_name, period)

            # Filename format: XXXXXXXX_jp_FY2024Q3_tse-xxx_DATE_01.xbrl
            xbrl_filename = f"{tse_code}_jp_{period}_tse-acedjpfr_2024-11-15_01.xbrl"

            # Add to ZIP
            zf.writestr(xbrl_filename, xbrl_content)
            print(f"  ✓ Added: {xbrl_filename}")

    size_kb = filepath.stat().st_size / 1024
    print()
    print(f"✓ Created: {filepath}")
    print(f"  Size: {size_kb:.1f} KB")
    print()
    print("Next steps:")
    print(f"  python edinet_xbrl_historical_fetcher.py --from-file {filepath}")
    print(f"  bash scripts/edinet_process_and_archive.sh")

    return filepath


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=str, default="/tmp",
                        help="Destination directory")
    parser.add_argument("--period", type=str, default="FY2024Q3",
                        help="Fiscal period (FY2024Q3, FY2024Q2, etc.)")

    args = parser.parse_args()

    dest = Path(args.dest)
    if not dest.exists():
        print(f"✗ Directory not found: {dest}")
        sys.exit(1)

    create_test_zip(dest, args.period)


if __name__ == "__main__":
    main()
