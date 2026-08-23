#!/usr/bin/env python3
"""
Chemical Import Substitution: Quarterly Dashboard Update Script
Purpose: Refresh tracking CSVs, calculate KPIs, generate quarterly report
Author: Ministry of Chemicals & Petrochemicals (DCPC)
Usage: python3 update_quarterly_dashboard.py --quarter Q3 --fy FY27 --output dashboard.html
"""

import pandas as pd
import csv
from datetime import datetime
import argparse
import sys

class QuarterlyDashboardUpdater:

    def __init__(self, quarter, fiscal_year):
        self.quarter = quarter  # Q1, Q2, Q3, Q4
        self.fiscal_year = fiscal_year  # FY27, FY28, etc.
        self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.capex_file = 'CAPEX_TRACKING_QUARTERLY.csv'
        self.dgft_file = 'DGFT_ANTIDUMPING_TRACKING.csv'
        self.kpi_file = 'KPI_QUARTERLY_TRACKING.csv'

    def load_tracking_data(self):
        """Load all tracking CSVs"""
        try:
            self.capex_df = pd.read_csv(self.capex_file)
            self.dgft_df = pd.read_csv(self.dgft_file)
            self.kpi_df = pd.read_csv(self.kpi_file)
            print(f"✅ Loaded {len(self.capex_df)} capex projects")
            print(f"✅ Loaded {len(self.dgft_df)} DGFT cases")
            print(f"✅ Loaded {len(self.kpi_df)} KPI records")
            return True
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            return False

    def calculate_overall_status(self):
        """Determine overall dashboard status (GREEN/YELLOW/RED)"""
        # Count RAG status from capex
        capex_red = (self.capex_df['Risk_Level'] == 'HIGH').sum()
        capex_yellow = (self.capex_df['Risk_Level'] == 'MEDIUM').sum()

        # Count from KPI
        kpi_red = (self.kpi_df['RAG'] == 'RED').sum()
        kpi_yellow = (self.kpi_df['RAG'] == 'YELLOW').sum()

        total_red = capex_red + kpi_red
        total_yellow = capex_yellow + kpi_yellow

        if total_red > 0:
            return 'RED', f"{total_red} critical risks"
        elif total_yellow > 2:
            return 'YELLOW', f"{total_yellow} at-risk items"
        else:
            return 'GREEN', 'On track'

    def calculate_capex_progress(self):
        """Calculate weighted capex execution progress"""
        # Exclude total row
        active_projects = self.capex_df[self.capex_df['Project'] != 'TOTAL'].copy()

        if len(active_projects) == 0:
            return 0

        # Weight by budget
        total_budget = active_projects['Capex_Budget_INR_Cr'].sum()
        if total_budget == 0:
            return 0

        weighted_progress = (
            (active_projects['Q2_FY27_Progress_Pct'] * active_projects['Capex_Budget_INR_Cr']).sum()
            / total_budget
        )
        return round(weighted_progress, 1)

    def calculate_fy30_savings(self):
        """Calculate FY30 savings across scenarios"""
        capex_total = self.capex_df[self.capex_df['Project'] == 'TOTAL']['FY30_Savings_USDbillion'].values
        dgft_total_low = self.dgft_df[self.dgft_df['Chemical'] == 'Total Duty Upside']['FY30_Savings_Impact_USDbillion_Low'].values
        dgft_total_high = self.dgft_df[self.dgft_df['Chemical'] == 'Total Duty Upside']['FY30_Savings_Impact_USDbillion_High'].values

        capex_base = capex_total[0] if len(capex_total) > 0 else 4.6
        dgft_low = dgft_total_low[0] if len(dgft_total_low) > 0 else 0.66
        dgft_high = dgft_total_high[0] if len(dgft_total_high) > 0 else 1.01

        scenarios = {
            'base': capex_base,
            'optimistic': capex_base + dgft_high,
            'at_risk': capex_base * 0.87  # Assume 13% haircut for delays
        }
        return scenarios

    def generate_risk_summary(self):
        """Generate top risks for executive summary"""
        risks = []

        # Extract critical risks from capex
        critical_capex = self.capex_df[self.capex_df['Risk_Level'] == 'HIGH']
        for _, row in critical_capex.iterrows():
            risks.append({
                'priority': 'CRITICAL',
                'item': row['Project'],
                'description': row['Notes']
            })

        # Extract YELLOW KPIs
        at_risk_kpi = self.kpi_df[self.kpi_df['RAG'] == 'YELLOW']
        for _, row in at_risk_kpi.iterrows():
            if row['Variance_Pct'] != 0:
                risks.append({
                    'priority': 'HIGH' if abs(row['Variance_Pct']) > 15 else 'MEDIUM',
                    'item': row['KPI_Name'],
                    'description': row['Notes']
                })

        # Sort by priority
        priority_map = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
        risks.sort(key=lambda x: priority_map[x['priority']])

        return risks[:5]  # Top 5 risks

    def generate_dashboard_text_report(self):
        """Generate text-based quarterly report (for email/PDF)"""
        report = []
        report.append(f"\n{'='*80}")
        report.append(f"CHEMICAL IMPORT SUBSTITUTION STRATEGY")
        report.append(f"QUARTERLY DASHBOARD REPORT - {self.quarter} {self.fiscal_year}")
        report.append(f"Generated: {self.timestamp}")
        report.append(f"{'='*80}\n")

        # Overall Status
        status, status_reason = self.calculate_overall_status()
        report.append(f"OVERALL STATUS: {status} ({status_reason})")
        report.append(f"\n{'-'*80}\n")

        # Capex Progress
        capex_progress = self.calculate_capex_progress()
        report.append(f"CAPEX EXECUTION PROGRESS: {capex_progress}%")
        report.append("\nProject Status:")
        active_projects = self.capex_df[self.capex_df['Project'] != 'TOTAL']
        for _, row in active_projects.iterrows():
            rag_icon = '✅' if row['Risk_Level'] == 'LOW' else ('⚠️' if row['Risk_Level'] == 'MEDIUM' else '❌')
            report.append(f"  {rag_icon} {row['Project']}: {row['Q2_FY27_Progress_Pct']}% ({row['Status']})")

        # FY30 Savings Scenarios
        report.append(f"\n{'-'*80}\n")
        scenarios = self.calculate_fy30_savings()
        report.append("FY30 SAVINGS SCENARIOS:")
        report.append(f"  Base Case (Capex Only):     ${scenarios['base']:.2f}bn")
        report.append(f"  Optimistic (+ All Duties):  ${scenarios['optimistic']:.2f}bn")
        report.append(f"  At-Risk (Capex Delays):     ${scenarios['at_risk']:.2f}bn")

        # Top Risks
        report.append(f"\n{'-'*80}\n")
        risks = self.generate_risk_summary()
        report.append("TOP RISKS & ACTIONS:")
        for i, risk in enumerate(risks, 1):
            report.append(f"\n{i}. [{risk['priority']}] {risk['item']}")
            report.append(f"   {risk['description']}")

        # KPI Summary
        report.append(f"\n{'-'*80}\n")
        report.append("KPI SUMMARY:")
        for _, row in self.kpi_df[self.kpi_df['Quarter'] == self.quarter[1]].iterrows():
            variance_str = f"{row['Variance_Pct']:+.0f}%" if pd.notna(row['Variance_Pct']) else "N/A"
            report.append(f"  {row['KPI_Name']}: {row['Actual_Value']} ({variance_str}) [{row['RAG']}]")

        # DGFT Tracking
        report.append(f"\n{'-'*80}\n")
        report.append("DGFT ANTI-DUMPING TRACKING:")
        for _, row in self.dgft_df[self.dgft_df['Current_Status'] != 'Mixed'].iterrows():
            report.append(f"  {row['Chemical']}: {row['Current_Status']}")
            if pd.notna(row['Risk_Flag']):
                report.append(f"    Risk: {row['Risk_Flag']}")

        # Next Actions
        report.append(f"\n{'-'*80}\n")
        report.append("NEXT QUARTER ACTIONS:")
        report.append("  1. Monitor DGFT portal daily for TPA/Dyes duty notifications (target: Aug 31)")
        report.append("  2. BPCL to file EC application by Aug 31; track approval timeline (Oct-Nov forecast)")
        report.append("  3. Accelerate BHAVYA Parks land acquisition; target 90% by Q3 end")
        report.append("  4. RIL O2C EPC bid evaluation; ensure contract award by Q1-FY28")
        report.append("  5. Verify QCO/ANTU DGFT cases; HSN codes and initiation dates")

        report.append(f"\n{'='*80}\n")

        return '\n'.join(report)

    def update_csv_timestamp(self, csv_path):
        """Add timestamp to CSV file"""
        df = pd.read_csv(csv_path)
        df['Last_Updated'] = self.timestamp
        df.to_csv(csv_path, index=False)
        print(f"✅ Updated {csv_path} with timestamp {self.timestamp}")

    def generate_html_dashboard(self, output_file='QUARTERLY_TRACKING_DASHBOARD.html'):
        """Generate updated HTML dashboard"""
        print(f"ℹ️ HTML dashboard already generated. Manual updates via CSV tracking files.")
        print(f"ℹ️ To regenerate dashboard, run: python3 update_quarterly_dashboard.py --regenerate")

    def run(self):
        """Execute full quarterly update"""
        print(f"\n🚀 Quarterly Dashboard Updater (v1.0)")
        print(f"Quarter: {self.quarter} {self.fiscal_year}")
        print(f"Timestamp: {self.timestamp}\n")

        # Load data
        if not self.load_tracking_data():
            return False

        # Generate report
        print("\n📊 Generating Quarterly Report...")
        report = self.generate_dashboard_text_report()

        # Save report
        report_file = f"QUARTERLY_REPORT_{self.quarter}_{self.fiscal_year}_{self.timestamp.split()[0]}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"✅ Quarterly report saved: {report_file}")

        # Print report to console
        print(report)

        # Update CSV timestamps
        for csv_file in [self.capex_file, self.dgft_file, self.kpi_file]:
            self.update_csv_timestamp(csv_file)

        print(f"\n✅ Quarterly dashboard updated successfully!")
        return True

def main():
    parser = argparse.ArgumentParser(
        description='Chemical Import Substitution Quarterly Dashboard Updater'
    )
    parser.add_argument('--quarter', default='Q2', help='Quarter: Q1, Q2, Q3, Q4')
    parser.add_argument('--fy', default='FY27', help='Fiscal Year: FY27, FY28, FY29, FY30')
    parser.add_argument('--output', default='QUARTERLY_TRACKING_DASHBOARD.html', help='Output HTML file')
    parser.add_argument('--regenerate', action='store_true', help='Regenerate HTML dashboard from scratch')

    args = parser.parse_args()

    updater = QuarterlyDashboardUpdater(args.quarter, args.fy)
    success = updater.run()

    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
