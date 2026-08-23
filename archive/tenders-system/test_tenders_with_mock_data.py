#!/usr/bin/env python3
"""
Test Tenders Scraper with Mock Data
Demonstrates full functionality without network access
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_FILE = Path.home() / 'tenders_data_test.duckdb'

# Mock tender data for testing
MOCK_TENDERS = [
    {
        'tender_id': 'TOT-2026-ETH-001',
        'title': 'Request for Proposal: Ethanol Supply and Distribution',
        'commodity': 'ethanol',
        'description': 'Large-scale supply of fuel-grade ethanol for blending. Qty: 50,000 liters/month. Quality specs: 99.5% purity minimum.',
        'tender_url': 'https://www.tenderontime.com/tender/ETH-001',
        'issued_date': '2026-07-25',
        'deadline': '2026-08-15',
        'organization': 'Ministry of Petroleum & Natural Gas',
        'tender_type': 'Open Bid',
        'estimated_value': '₹2,50,00,000',
    },
    {
        'tender_id': 'TOT-2026-ETH-002',
        'title': 'Ethanol Production Equipment - Turnkey Supply',
        'commodity': 'ethanol',
        'description': 'Supply of complete distillation and fermentation equipment for ethanol production facility.',
        'tender_url': 'https://www.tenderontime.com/tender/ETH-002',
        'issued_date': '2026-07-20',
        'deadline': '2026-09-10',
        'organization': 'Energy Development Corporation Ltd',
        'tender_type': 'Restricted',
        'estimated_value': '₹5,00,00,000',
    },
    {
        'tender_id': 'TOT-2026-BIO-001',
        'title': 'Biogas Supply for Power Generation',
        'commodity': 'biogas',
        'description': 'Biogas supply from anaerobic digestion facility. 100 m³/day capacity. Methane content: 55-65%.',
        'tender_url': 'https://www.tenderontime.com/tender/BIO-001',
        'issued_date': '2026-07-28',
        'deadline': '2026-08-25',
        'organization': 'State Power Distribution Company',
        'tender_type': 'Open Bid',
        'estimated_value': '₹1,50,00,000',
    },
    {
        'tender_id': 'TOT-2026-BIO-002',
        'title': 'Biogas Digester Installation - Rural Electrification',
        'commodity': 'biogas',
        'description': '500 small biogas digesters for village-level deployment. Training and support included.',
        'tender_url': 'https://www.tenderontime.com/tender/BIO-002',
        'issued_date': '2026-07-15',
        'deadline': '2026-08-30',
        'organization': 'Ministry of New & Renewable Energy',
        'tender_type': 'Open Bid',
        'estimated_value': '₹7,50,00,000',
    },
    {
        'tender_id': 'TOT-2026-SAF-001',
        'title': 'Sustainable Aviation Fuel (SAF) Supply Agreement',
        'commodity': 'SAF',
        'description': 'Annual supply of SAF from renewable sources. 5000 MT. ASTM D7566 compliant.',
        'tender_url': 'https://www.tenderontime.com/tender/SAF-001',
        'issued_date': '2026-07-22',
        'deadline': '2026-08-20',
        'organization': 'National Aviation Authority',
        'tender_type': 'Restricted',
        'estimated_value': '₹50,00,00,000',
    },
    {
        'tender_id': 'TOT-2026-LUB-001',
        'title': 'Industrial Lubricants Supply - Manufacturing Plants',
        'commodity': 'lubricants',
        'description': 'Premium synthetic and mineral lubricants for industrial machinery. 200 MT/month. ISO VG 32, 46, 68.',
        'tender_url': 'https://www.tenderontime.com/tender/LUB-001',
        'issued_date': '2026-07-26',
        'deadline': '2026-08-31',
        'organization': 'Central Public Works Department',
        'tender_type': 'Open Bid',
        'estimated_value': '₹8,00,00,000',
    },
    {
        'tender_id': 'TOT-2026-LUB-002',
        'title': 'Automotive Lubricants - Fleet Maintenance',
        'commodity': 'lubricants',
        'description': 'Engine oils, gear oils, and hydraulic fluids for government vehicle fleet. Annual requirement.',
        'tender_url': 'https://www.tenderontime.com/tender/LUB-002',
        'issued_date': '2026-07-30',
        'deadline': '2026-08-27',
        'organization': 'Ministry of Defence',
        'tender_type': 'Restricted',
        'estimated_value': '₹3,50,00,000',
    },
    {
        'tender_id': 'TOT-2026-DIE-001',
        'title': 'Diesel Supply - Government Facilities',
        'commodity': 'diesel',
        'description': 'High-speed diesel (HSD) for government offices and facilities. 50,000 liters/month.',
        'tender_url': 'https://www.tenderontime.com/tender/DIE-001',
        'issued_date': '2026-07-18',
        'deadline': '2026-08-18',
        'organization': 'Ministry of Finance',
        'tender_type': 'Open Bid',
        'estimated_value': '₹2,00,00,000',
    },
    {
        'tender_id': 'TOT-2026-DIE-002',
        'title': 'Diesel Engines and Generators - Equipment',
        'commodity': 'diesel',
        'description': '50 kW diesel generator sets with fuel tanks. ISO 8528 standard.',
        'tender_url': 'https://www.tenderontime.com/tender/DIE-002',
        'issued_date': '2026-07-27',
        'deadline': '2026-09-15',
        'organization': 'State Electricity Board',
        'tender_type': 'Open Bid',
        'estimated_value': '₹12,00,00,000',
    },
    {
        'tender_id': 'TOT-2026-LPG-001',
        'title': 'Liquefied Petroleum Gas (LPG) Supply',
        'commodity': 'LPG',
        'description': 'Bulk LPG supply for industrial and domestic use. 100 MT/month. Purity: 99.5%.',
        'tender_url': 'https://www.tenderontime.com/tender/LPG-001',
        'issued_date': '2026-07-21',
        'deadline': '2026-08-21',
        'organization': 'Food Corporation of India',
        'tender_type': 'Open Bid',
        'estimated_value': '₹1,80,00,000',
    },
    {
        'tender_id': 'TOT-2026-LPG-002',
        'title': 'LPG Distribution Network - Rural Areas',
        'commodity': 'LPG',
        'description': 'Setting up LPG distribution centers in 50 villages. Complete infrastructure.',
        'tender_url': 'https://www.tenderontime.com/tender/LPG-002',
        'issued_date': '2026-07-29',
        'deadline': '2026-09-30',
        'organization': 'Ministry of Social Justice',
        'tender_type': 'Restricted',
        'estimated_value': '₹15,00,00,000',
    },
]


def setup_database():
    """Initialize DuckDB with tender schema."""
    conn = duckdb.connect(str(DB_FILE))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            tender_id VARCHAR PRIMARY KEY,
            title VARCHAR,
            commodity VARCHAR,
            description VARCHAR,
            tender_url VARCHAR,
            issued_date DATE,
            deadline DATE,
            organization VARCHAR,
            tender_type VARCHAR,
            estimated_value VARCHAR,
            raw_json VARCHAR,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    return conn


def save_mock_tenders(conn: duckdb.DuckDatabaseConnection, tenders: List[Dict]):
    """Save mock tenders to database."""
    logger.info(f"Saving {len(tenders)} mock tenders to database...")

    for tender in tenders:
        try:
            conn.execute("DELETE FROM tenders WHERE tender_id = ?", [tender['tender_id']])
            conn.execute("""
                INSERT INTO tenders (
                    tender_id, title, commodity, description, tender_url,
                    issued_date, deadline, organization, tender_type,
                    estimated_value, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                tender['tender_id'],
                tender['title'],
                tender['commodity'],
                tender['description'],
                tender['tender_url'],
                tender.get('issued_date'),
                tender.get('deadline'),
                tender['organization'],
                tender.get('tender_type', 'Open'),
                tender.get('estimated_value', ''),
                json.dumps(tender),
            ])
        except Exception as e:
            logger.error(f"Error saving tender {tender['tender_id']}: {e}")

    conn.commit()
    logger.info(f"✓ Saved {len(tenders)} tenders")


def main():
    logger.info("=" * 80)
    logger.info("Tenders Database - Test with Mock Data")
    logger.info("=" * 80)

    try:
        # Setup database
        logger.info(f"\nSetting up database at {DB_FILE}...")
        conn = setup_database()
        logger.info("✓ Database ready")

        # Load mock data
        logger.info(f"\nLoading {len(MOCK_TENDERS)} mock tenders...")
        save_mock_tenders(conn, MOCK_TENDERS)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Summary - Tenders by Commodity")
        logger.info("=" * 80)

        result = conn.execute("""
            SELECT commodity, COUNT(*) as count
            FROM tenders
            GROUP BY commodity
            ORDER BY count DESC
        """).fetchall()

        for commodity, count in result:
            logger.info(f"  {commodity.upper():15} : {count:2} tenders")

        total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
        logger.info(f"\nTotal tenders: {total}")

        # Show upcoming deadlines
        logger.info("\n" + "=" * 80)
        logger.info("Upcoming Deadlines (Next 30 Days)")
        logger.info("=" * 80)

        deadlines = conn.execute("""
            SELECT title, commodity, deadline, organization
            FROM tenders
            WHERE deadline > CURRENT_DATE
            ORDER BY deadline ASC
        """).fetchall()

        for title, commodity, deadline, org in deadlines:
            if isinstance(deadline, str):
                deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
            else:
                deadline_dt = datetime.combine(deadline, datetime.min.time())
            days_left = (deadline_dt - datetime.now()).days
            logger.info(f"  [{days_left:2}d] {commodity.upper():10} | {title[:50]:50} | {org}")

        # Show open bids
        logger.info("\n" + "=" * 80)
        logger.info("Open vs Restricted Tenders")
        logger.info("=" * 80)

        bid_types = conn.execute("""
            SELECT tender_type, COUNT(*) as count
            FROM tenders
            GROUP BY tender_type
        """).fetchall()

        for bid_type, count in bid_types:
            logger.info(f"  {bid_type:15}: {count} tenders")

        # Export options
        logger.info("\n" + "=" * 80)
        logger.info("Data Export Options")
        logger.info("=" * 80)
        logger.info(f"\nDatabase location: {DB_FILE}")
        logger.info("\nExport to CSV:")
        logger.info(f"  duckdb -c \"COPY tenders TO 'export.csv' (FORMAT CSV, HEADER)\" {DB_FILE}")
        logger.info("\nExport to JSON:")
        logger.info(f"  duckdb -c \"COPY tenders TO 'export.json' (FORMAT JSON)\" {DB_FILE}")
        logger.info("\nExport to Parquet (for analysis):")
        logger.info(f"  duckdb -c \"COPY tenders TO 'export.parquet' (FORMAT PARQUET)\" {DB_FILE}")
        logger.info("\nQuery all ethanol tenders:")
        logger.info(f"  duckdb -c \"SELECT * FROM tenders WHERE commodity='ethanol'\" {DB_FILE}")

        # Show sample Python query
        logger.info("\n" + "=" * 80)
        logger.info("Python Example - Query Database")
        logger.info("=" * 80)
        logger.info("""
import duckdb

conn = duckdb.connect('~/tenders_data_test.duckdb')

# Get all ethanol tenders
df = conn.execute("SELECT * FROM tenders WHERE commodity='ethanol'").df()
print(df[['title', 'deadline', 'estimated_value']])

# Find tenders closing within 7 days
urgent = conn.execute('''
    SELECT title, commodity, deadline
    FROM tenders
    WHERE CAST(deadline AS DATE) - CURRENT_DATE <= 7
    ORDER BY deadline ASC
''').df()

conn.close()
        """)

        conn.close()
        logger.info("\n✓ Test complete! Mock data loaded successfully.")
        logger.info("\nNext steps:")
        logger.info("  1. Run the actual scraper when you have network access")
        logger.info("  2. It will populate the same database structure with real data")
        logger.info("  3. All queries above will work with real tenders")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == '__main__':
    main()
