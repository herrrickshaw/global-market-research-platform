#!/usr/bin/env python3
"""
Generate Professional PDF Dashboard from Quarterly Tracking Data
Purpose: Create formatted PDF report from CSV tracking files
Author: Ministry of Chemicals & Petrochemicals (DCPC)
Usage: python3 generate_dashboard_pdf.py --quarter Q2 --fy FY27
"""

import pandas as pd
from datetime import datetime
import sys

def generate_pdf_with_reportlab():
    """Generate PDF using ReportLab (requires: pip install reportlab)"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from datetime import datetime

        # Create PDF
        pdf_file = f"QUARTERLY_DASHBOARD_{datetime.now().strftime('%Y%m%d')}_REPORTLAB.pdf"
        doc = SimpleDocTemplate(pdf_file, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0a2d5a'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#0a2d5a'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )

        # Title
        story.append(Paragraph("Chemical Import Substitution Strategy", title_style))
        story.append(Paragraph("Quarterly Tracking Dashboard (Q2 FY27)", styles['Normal']))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # Load CSVs
        try:
            capex_df = pd.read_csv('CAPEX_TRACKING_QUARTERLY.csv')
            dgft_df = pd.read_csv('DGFT_ANTIDUMPING_TRACKING.csv')
            kpi_df = pd.read_csv('KPI_QUARTERLY_TRACKING.csv')
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return False

        # Section 1: Capex Projects
        story.append(Paragraph("1. CAPEX PROJECT EXECUTION TRACKING", heading_style))

        capex_data = [['Project', 'Budget (₹Cr)', 'Progress', 'Status', 'Risk']]
        active_projects = capex_df[capex_df['Project'] != 'TOTAL']
        for _, row in active_projects.iterrows():
            capex_data.append([
                row['Project'],
                f"₹{row['Capex_Budget_INR_Cr']:,}",
                f"{row['Q2_FY27_Progress_Pct']}%",
                row['Status'],
                row['Risk_Level']
            ])

        capex_table = Table(capex_data, colWidths=[2.5*inch, 1.2*inch, 0.8*inch, 1.2*inch, 1*inch])
        capex_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a2d5a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(capex_table)
        story.append(Spacer(1, 0.2*inch))

        # Section 2: DGFT Tracking
        story.append(Paragraph("2. DGFT ANTI-DUMPING INVESTIGATION TRACKING", heading_style))

        dgft_data = [['Chemical', 'HSN', 'Expected Decision', 'Duty Rate', 'FY30 Impact', 'Status']]
        for _, row in dgft_df[dgft_df['Chemical'] != 'Total Duty Upside'].iterrows():
            dgft_data.append([
                row['Chemical'],
                str(row['HSN_Code']) if pd.notna(row['HSN_Code']) else 'TBD',
                str(row['Expected_Decision_Date'])[:10] if pd.notna(row['Expected_Decision_Date']) else 'TBD',
                f"{row['Expected_Duty_Rate_Pct']}%" if pd.notna(row['Expected_Duty_Rate_Pct']) else 'TBD',
                f"${row['FY30_Savings_Impact_USDbillion_Low']:.2f}-{row['FY30_Savings_Impact_USDbillion_High']:.2f}bn",
                row['Current_Status']
            ])

        dgft_table = Table(dgft_data, colWidths=[1.5*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.5*inch, 1*inch])
        dgft_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a5a2d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightcyan]),
        ]))
        story.append(dgft_table)
        story.append(Spacer(1, 0.2*inch))

        # Section 3: Critical Alerts
        story.append(Paragraph("3. CRITICAL ALERTS & ACTIONS", heading_style))

        alerts = [
            ("🔴 CRITICAL: DGFT TPA/Dyes Duty Decisions",
             "Expected Aug-Sep 2026 (imminent). Decisions will add $430-640mn to FY30 savings. "
             "Delay beyond Sep 2026 = FY28 implementation, reducing FY30 impact."),
            ("🔴 CRITICAL: BPCL AP EC Not Filed",
             "Environmental Clearance must be filed by Aug 31, 2026. Delay = 6-12 month commissioning slip to FY29."),
            ("⚠️ HIGH: BHAVYA Parks Land Acquisition",
             "Pace below target (60-70% vs. 90% target for Q3). FY28-29 operationalization at risk."),
            ("🟡 MEDIUM: RIL O2C EPC Contract Award",
             "On-track for Q1-FY28 (Jan 2027). Monitor bid evaluation; geopolitical risks to EPC sourcing."),
        ]

        for alert_title, alert_text in alerts:
            story.append(Paragraph(f"<b>{alert_title}</b>", styles['Normal']))
            story.append(Paragraph(alert_text, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        story.append(PageBreak())

        # Section 4: FY30 Savings Scenarios
        story.append(Paragraph("4. FY30 SAVINGS SCENARIOS", heading_style))

        scenarios = [
            ("Base Case (Capex Only)", "$8.3bn",
             "All capex on-track; no anti-dumping duties approved; PLI uptake at 50%"),
            ("At-Risk Case (Capex Delays)", "$7.2bn",
             "BPCL AP delayed to FY29; RIL O2C to FY31; TPA/Dyes duty pushed to FY28"),
            ("Optimistic Case (All On-Track + Duties)", "$9.8bn",
             "Capex delivered FY27-30; TPA/Dyes duties approved by Sep 2026; QCO/ANTU cases approved"),
        ]

        scenario_data = [['Scenario', 'FY30 Savings', 'Assumptions']]
        for scenario, savings, assumptions in scenarios:
            scenario_data.append([scenario, savings, assumptions])

        scenario_table = Table(scenario_data, colWidths=[2.5*inch, 1.2*inch, 2.8*inch])
        scenario_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a2d5a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightyellow]),
        ]))
        story.append(scenario_table)
        story.append(Spacer(1, 0.2*inch))

        # Section 5: KPI Summary
        story.append(Paragraph("5. QUARTERLY KPI SUMMARY (Q2 FY27)", heading_style))

        kpi_q2 = kpi_df[kpi_df['Quarter'] == 2]
        kpi_data = [['KPI', 'Target', 'Actual', 'Variance', 'RAG']]
        for _, row in kpi_q2.head(10).iterrows():
            kpi_data.append([
                row['KPI_Name'][:40],
                str(row['Target_Value'])[:20],
                str(row['Actual_Value'])[:20],
                f"{row['Variance_Pct']:+.0f}%" if pd.notna(row['Variance_Pct']) else 'N/A',
                row['RAG']
            ])

        kpi_table = Table(kpi_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1*inch, 0.8*inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a5a2d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 0.2*inch))

        # Section 6: Next Actions
        story.append(Paragraph("6. NEXT QUARTER ACTIONS (Q3 FY27: Oct-Dec 2026)", heading_style))

        actions = [
            "✅ Monitor DGFT portal DAILY for TPA/Dyes duty notifications (target: Aug 31, 2026)",
            "✅ BPCL to file EC application by Aug 31; track approval timeline (Oct-Nov forecast)",
            "✅ Accelerate BHAVYA Parks land acquisition; target 90% completion by Q3 end",
            "✅ RIL O2C EPC bid evaluation; ensure contract award by Q1-FY28 (Jan 2027)",
            "✅ Verify QCO/ANTU DGFT cases; HSN codes and case status via portal audit",
            "✅ Quarterly KPI refresh; update capex progress % and savings scenarios",
        ]

        for action in actions:
            story.append(Paragraph(action, styles['Normal']))

        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("_" * 80, styles['Normal']))
        story.append(Paragraph(
            "Chemical Import Substitution Strategy | Quarterly Dashboard | Q2 FY27 (Aug 2026)<br/>"
            "Ministry of Chemicals & Petrochemicals (DCPC) | Next Update: Oct 1, 2026",
            styles['Normal']
        ))

        # Build PDF
        doc.build(story)
        print(f"✅ Professional PDF generated: {pdf_file} (using ReportLab)")
        return True

    except ImportError:
        print("⚠️ ReportLab not installed. Install with: pip install reportlab")
        return False

def main():
    """Generate dashboard PDF"""
    print("📄 Generating Dashboard PDF...\n")

    # Try ReportLab first (better formatting)
    success = generate_pdf_with_reportlab()

    if not success:
        print("\n💡 Tip: Install reportlab for professional PDF formatting:")
        print("   pip install reportlab")
        print("\n   Alternatively, use LibreOffice conversion:")
        print("   soffice --headless --convert-to pdf QUARTERLY_TRACKING_DASHBOARD.html")

if __name__ == '__main__':
    main()
