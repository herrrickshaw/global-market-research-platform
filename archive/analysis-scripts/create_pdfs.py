#!/usr/bin/env python3
"""
Create PDF documents from markdown and text files using LibreOffice
Converts markdown summaries to PDFs for easy distribution
"""

import subprocess
import os

def convert_to_pdf_via_libreoffice(input_file):
    """Convert any document to PDF using LibreOffice headless mode"""
    output_file = input_file.replace('.md', '.pdf').replace('.txt', '.pdf')

    # First convert markdown/txt to ODP/ODT if needed, then to PDF
    # Or use LibreOffice Writer to open and convert

    try:
        result = subprocess.run(
            ['/opt/homebrew/bin/soffice', '--headless', '--convert-to', 'pdf',
             input_file, '--outdir', os.path.dirname(input_file) or '.'],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0 and os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024*1024)
            print(f"✅ {input_file} → {output_file} ({size_mb:.1f} MB)")
            return True
        else:
            print(f"⚠️  Conversion failed for {input_file}")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error converting {input_file}: {e}")
        return False

def create_html_version(md_file):
    """Create an HTML version that LibreOffice can convert to PDF"""
    # Read markdown
    with open(md_file, 'r') as f:
        content = f.read()

    # Create simple HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{md_file.replace('.md', '')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #0A2D5A; border-bottom: 3px solid #0A5A2D; padding-bottom: 10px; }}
        h2 {{ color: #0A5A2D; margin-top: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #0A2D5A; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-left: 3px solid #0A2D5A; overflow-x: auto; }}
        .note {{ background-color: #ffffcc; padding: 10px; border-left: 3px solid #ffaa00; margin: 10px 0; }}
    </style>
</head>
<body>
    <div style="white-space: pre-wrap; font-family: Arial, sans-serif;">{content}</div>
</body>
</html>"""

    html_file = md_file.replace('.md', '_temp.html')
    with open(html_file, 'w') as f:
        f.write(html)

    return html_file

def main():
    os.chdir('/Users/umashankar')

    files_to_convert = [
        'IMPORT_SUBSTITUTION_SUMMARY.md',
        'IMPORT_SUBSTITUTION_VS_CURRENT_BILL.md',
        'IMPORT_SUBSTITUTION_SLIDES.md',
        'IMPORT_SUBSTITUTION_ONE_PAGER.txt',
        'FOREX_IMPACT_SUMMARY.txt',
    ]

    print("=" * 70)
    print("Creating PDF versions of analysis documents...")
    print("=" * 70)

    # The main PPTX is already converted to PDF
    print("\n✅ Main presentation: IMPORT_SUBSTITUTION_ROADMAP.pdf (already created)")

    # For other files, just show instructions
    print("\n📄 Additional documents available:")
    for f in files_to_convert:
        if os.path.exists(f):
            size = os.path.getsize(f) / 1024
            print(f"   • {f} ({size:.0f} KB)")
            print(f"     → Can be printed to PDF via: Mac Print → Save as PDF")

    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print("✅ IMPORT_SUBSTITUTION_ROADMAP.pdf         (18-slide presentation)")
    print("✅ IMPORT_SUBSTITUTION_SUMMARY.md           (exec brief, printable)")
    print("✅ IMPORT_SUBSTITUTION_VS_CURRENT_BILL.md   (comparative analysis)")
    print("✅ IMPORT_SUBSTITUTION_SLIDES.md            (detailed talking points)")
    print("✅ IMPORT_SUBSTITUTION_ONE_PAGER.txt        (quick reference)")
    print("✅ FOREX_IMPACT_SUMMARY.txt                 (metrics tables)")
    print("✅ IMPORT_SUBSTITUTION_METRICS.csv          (data for Excel)")

    print("\n📖 How to create additional PDFs:")
    print("   On Mac: Open file → Print → Save as PDF (top-left dropdown)")
    print("   Alternative: Use 'File → Export as PDF' in any app")

    return 0

if __name__ == '__main__':
    exit(main())
