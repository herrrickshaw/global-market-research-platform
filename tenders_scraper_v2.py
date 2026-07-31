#!/usr/bin/env python3
"""
Tenders on Time Scraper v2 - Fixed version with SSL handling and fallback testing
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import re

import duckdb
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import time
import urllib3

# Disable SSL warnings for problematic certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

COMMODITIES = [
    'ethanol',
    'biogas',
    'SAF',
    'lubricants',
    'diesel',
    'petrol',
    'crude oil',
    'natural gas',
    'LPG',
]

CREDS_FILE = Path.home() / '.config' / 'market-secrets' / 'credentials.env'
DB_FILE = Path.home() / 'tenders_data.duckdb'


def load_credentials() -> tuple:
    """Load Tenders on Time credentials from .env file."""
    if not CREDS_FILE.exists():
        raise FileNotFoundError(f"Credentials file not found: {CREDS_FILE}")

    creds = {}
    with open(CREDS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                creds[key.strip()] = val.strip()

    username = creds.get('TENDERS_ON_TIME_USERNAME')
    password = creds.get('TENDERS_ON_TIME_PASSWORD')

    if not username or not password:
        raise ValueError("TENDERS_ON_TIME_USERNAME or TENDERS_ON_TIME_PASSWORD not found")

    return username, password


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


def scrape_tenders(username: str, password: str) -> List[Dict]:
    """
    Scrape tenders from Tenders on Time (last 3 months).

    Searches for tenders issued in the past 90 days to capture reopened tenders.
    Includes SSL handling and detailed error logging.
    """
    from datetime import timedelta

    tenders = []
    base_url = "https://www.tenderontime.com"

    # Calculate date range (last 3 months)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    date_range = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    logger.info(f"Searching for tenders issued: {date_range}")

    # Create session with retries and SSL handling
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    try:
        logger.info("Attempting to access Tenders on Time...")

        # Try different endpoints
        endpoints = [
            '/login',
            '/user/login',
            '/api/login',
            '/',
        ]

        login_success = False

        for endpoint in endpoints:
            try:
                url = urljoin(base_url, endpoint)
                logger.info(f"  Trying {url}...")

                # Try with SSL verification disabled if needed
                response = session.get(url, timeout=10, verify=True)

                if response.status_code in [200, 302]:
                    logger.info(f"    ✓ Accessible")

                    if endpoint in ['/login', '/user/login']:
                        # Try to login
                        logger.info("    Attempting login...")
                        login_data = {
                            'email': username,
                            'password': password,
                        }

                        login_response = session.post(
                            url,
                            data=login_data,
                            timeout=10,
                            verify=True
                        )

                        if login_response.status_code in [200, 302]:
                            logger.info("    ✓ Login successful")
                            login_success = True
                            break

            except requests.exceptions.SSLError as e:
                logger.warning(f"    SSL Error: {e}")
                # Try without SSL verification
                try:
                    logger.info(f"    Retrying without SSL verification...")
                    response = session.get(url, timeout=10, verify=False)
                    if response.status_code in [200, 302]:
                        logger.info(f"    ✓ Accessible (SSL verification disabled)")
                        login_success = True
                        break
                except Exception as e2:
                    logger.warning(f"    Also failed without SSL: {e2}")
                    continue

            except Exception as e:
                logger.warning(f"    Failed: {e}")
                continue

        if not login_success:
            logger.warning("⚠ Could not login. Searching with public access...")

        # Search for commodities
        logger.info(f"\nSearching for {len(COMMODITIES)} commodities...")

        for commodity in COMMODITIES:
            logger.info(f"  {commodity}...")

            try:
                # Multiple search endpoint attempts with date range
                search_paths = [
                    f"/search?keyword={quote(commodity)}&from_date={start_date.strftime('%Y-%m-%d')}&to_date={end_date.strftime('%Y-%m-%d')}",
                    f"/tenders/search?query={quote(commodity)}&issued_date_from={start_date.strftime('%d-%m-%Y')}&issued_date_to={end_date.strftime('%d-%m-%Y')}",
                    f"/api/tenders/search?keyword={quote(commodity)}&from_date={start_date.strftime('%Y-%m-%d')}&to_date={end_date.strftime('%Y-%m-%d')}",
                    f"/search?keyword={quote(commodity)}",
                    f"/tenders/search?query={quote(commodity)}",
                    f"/api/tenders/search?keyword={quote(commodity)}",
                ]

                for search_path in search_paths:
                    try:
                        url = urljoin(base_url, search_path)
                        response = session.get(url, timeout=10, verify=False)

                        if response.status_code == 200:
                            logger.info(f"    ✓ Found via {search_path}")

                            # Parse results
                            if 'application/json' in response.headers.get('content-type', ''):
                                data = response.json()
                                results = data.get('tenders', data.get('results', []))
                            else:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                results = parse_html_tenders(soup)

                            for result in results:
                                tender = {
                                    'tender_id': result.get('id') or result.get('tender_id') or f"{commodity}_{int(time.time()*1000)}",
                                    'title': result.get('title') or result.get('name', 'N/A'),
                                    'commodity': commodity,
                                    'description': result.get('description', ''),
                                    'tender_url': result.get('url') or result.get('link', ''),
                                    'issued_date': parse_date(result.get('issued_date') or result.get('date')),
                                    'deadline': parse_date(result.get('deadline') or result.get('closing_date')),
                                    'organization': result.get('organization') or result.get('buyer', ''),
                                    'tender_type': result.get('type') or result.get('tender_type', 'Open'),
                                    'estimated_value': result.get('value') or result.get('estimated_value', ''),
                                    'raw_json': json.dumps(result),
                                }
                                tenders.append(tender)

                            logger.info(f"      {len(results)} tenders found")
                            break

                    except Exception as e:
                        logger.debug(f"    {search_path}: {e}")
                        continue

            except Exception as e:
                logger.error(f"  Error searching {commodity}: {e}")

            time.sleep(1)

        logger.info(f"\n✓ Total tenders collected: {len(tenders)}")
        return tenders

    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return []


def parse_html_tenders(soup: BeautifulSoup) -> List[Dict]:
    """Parse HTML tender listings."""
    tenders = []

    tender_rows = soup.find_all(['tr', 'div'], class_=re.compile(r'tender|row|item', re.I))

    for row in tender_rows[:50]:
        try:
            tender = {}

            title_elem = row.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|link', re.I))
            if title_elem:
                tender['title'] = title_elem.get_text(strip=True)
                link = title_elem.get('href')
                if link:
                    tender['url'] = link

            date_elem = row.find(['span', 'td'], class_=re.compile(r'date|deadline|closing', re.I))
            if date_elem:
                tender['deadline'] = date_elem.get_text(strip=True)

            org_elem = row.find(['span', 'td'], class_=re.compile(r'org|buyer|issuer|ministry', re.I))
            if org_elem:
                tender['organization'] = org_elem.get_text(strip=True)

            if tender.get('title'):
                tenders.append(tender)

        except Exception as e:
            logger.debug(f"Parse error: {e}")

    return tenders


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse various date formats."""
    if not date_str:
        return None

    date_str = str(date_str).strip()
    formats = [
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%Y/%m/%d',
        '%d %b %Y',
        '%d %B %Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return date_str


def save_tenders(conn, tenders: List[Dict]):
    """Save tenders to DuckDB."""
    if not tenders:
        logger.warning("No tenders to save")
        return

    logger.info(f"Saving {len(tenders)} tenders to {DB_FILE}...")

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
                tender['issued_date'],
                tender['deadline'],
                tender['organization'],
                tender['tender_type'],
                tender['estimated_value'],
                tender['raw_json'],
            ])
        except Exception as e:
            logger.error(f"Error saving tender: {e}")

    conn.commit()
    logger.info(f"✓ Saved {len(tenders)} tenders")


def main():
    logger.info("=" * 70)
    logger.info("Tenders on Time Scraper v2 (SSL-Fixed)")
    logger.info("=" * 70)

    try:
        # Load credentials
        logger.info("Loading credentials...")
        username, password = load_credentials()
        logger.info(f"✓ Loaded credentials for {username}")

        # Setup database
        logger.info(f"Setting up database at {DB_FILE}...")
        conn = setup_database()
        logger.info("✓ Database ready")

        # Scrape tenders
        logger.info("Starting tender scrape...\n")
        tenders = scrape_tenders(username, password)

        # Save results
        if tenders:
            save_tenders(conn, tenders)
        else:
            logger.warning("⚠ No tenders scraped. This could be due to:")
            logger.warning("  1. Site connectivity issues (SSL/network)")
            logger.warning("  2. Site structure has changed")
            logger.warning("  3. Login credentials invalid")
            logger.warning("  4. No tenders match search terms")
            logger.warning("\nTry:")
            logger.warning("  - Verify login manually at the site")
            logger.warning("  - Check site URL hasn't changed")
            logger.warning("  - Use Selenium version for JavaScript-heavy content")

        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("Summary")
        logger.info("=" * 70)

        result = conn.execute("""
            SELECT commodity, COUNT(*) as count
            FROM tenders
            GROUP BY commodity
            ORDER BY count DESC
        """).fetchall()

        if result:
            for commodity, count in result:
                logger.info(f"  {commodity}: {count} tenders")

            total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
            logger.info(f"\nTotal tenders: {total}")
        else:
            logger.info("No tenders in database")

        logger.info(f"Database: {DB_FILE}")

        # Show sample query
        logger.info("\n" + "=" * 70)
        logger.info("Query Examples")
        logger.info("=" * 70)
        logger.info("duckdb -c \"SELECT commodity, COUNT(*) FROM tenders GROUP BY commodity\" ~/tenders_data.duckdb")
        logger.info("duckdb -c \"SELECT title, deadline FROM tenders WHERE deadline > CURRENT_DATE LIMIT 10\" ~/tenders_data.duckdb")

        conn.close()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
