#!/usr/bin/env python3
"""
Tenders on Time scraper for ethanol, biogas, SAF, lubricants and other commodities.
Reads credentials from ~/.config/market-secrets/credentials.env
Stores results in DuckDB.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import re

import duckdb
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Commodities to search for
COMMODITIES = [
    'ethanol',
    'biogas',
    'SAF',  # Sustainable Aviation Fuel
    'lubricants',
    'diesel',
    'petrol',
    'crude oil',
    'natural gas',
    'LPG',
]

# Credentials file
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
        raise ValueError("TENDERS_ON_TIME_USERNAME or TENDERS_ON_TIME_PASSWORD not found in credentials file")

    return username, password


def setup_database():
    """Initialize DuckDB with tender schema."""
    conn = duckdb.connect(str(DB_FILE))

    # Create tenders table if it doesn't exist
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


def scrape_tenders(username: str, password: str, session: requests.Session) -> List[Dict]:
    """
    Scrape tenders from Tenders on Time.

    Note: This is a template - actual URL structure may differ.
    Adjust based on the site's actual search/API endpoints.
    """
    base_url = "https://www.tenderontime.com"
    tenders = []

    try:
        # Step 1: Login
        logger.info("Attempting to login to Tenders on Time...")
        login_url = urljoin(base_url, "/login")

        # First, get the login page to extract any CSRF tokens if needed
        login_page = session.get(login_url, timeout=10)
        login_page.raise_for_status()

        # Prepare login payload
        login_data = {
            'email': username,
            'password': password,
        }

        # Attempt login
        response = session.post(
            urljoin(base_url, "/api/login"),
            json=login_data,
            timeout=10
        )

        if response.status_code != 200:
            # Try alternate login path
            response = session.post(
                urljoin(base_url, "/user/login"),
                data=login_data,
                timeout=10
            )

        if response.status_code in [200, 302]:
            logger.info("✓ Login successful")
        else:
            logger.warning(f"⚠ Login returned status {response.status_code}. Continuing with search...")

        # Step 2: Search for commodities
        logger.info(f"Searching for {len(COMMODITIES)} commodities...")

        for commodity in COMMODITIES:
            logger.info(f"  Searching: {commodity}")

            # Adjust search URL based on actual site structure
            search_params = {
                'keyword': commodity,
                'industry': commodity,
                'sort': 'date',
                'order': 'desc'
            }

            # Try different search endpoints
            search_urls = [
                urljoin(base_url, "/search"),
                urljoin(base_url, "/api/tenders/search"),
                urljoin(base_url, "/tenders/search"),
            ]

            search_response = None
            for search_url in search_urls:
                try:
                    search_response = session.get(search_url, params=search_params, timeout=10)
                    if search_response.status_code == 200:
                        logger.info(f"    ✓ Found via {search_url}")
                        break
                except Exception as e:
                    logger.debug(f"    Failed {search_url}: {e}")
                    continue

            if not search_response or search_response.status_code != 200:
                logger.warning(f"    Could not fetch tenders for {commodity}")
                continue

            # Parse results
            try:
                if 'application/json' in search_response.headers.get('content-type', ''):
                    # API response
                    data = search_response.json()
                    results = data.get('tenders', data.get('results', []))
                else:
                    # HTML response
                    soup = BeautifulSoup(search_response.text, 'html.parser')
                    results = parse_html_tenders(soup)

                for result in results:
                    tender = {
                        'tender_id': result.get('id') or result.get('tender_id') or str(time.time()),
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

                logger.info(f"    Found {len(results)} tenders")

            except Exception as e:
                logger.error(f"    Error parsing results for {commodity}: {e}")
                continue

            time.sleep(1)  # Be respectful to the server

        return tenders

    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return []


def parse_html_tenders(soup: BeautifulSoup) -> List[Dict]:
    """Parse HTML tender listings (site-specific)."""
    tenders = []

    # Common HTML patterns - adjust based on actual site structure
    tender_rows = soup.find_all(['tr', 'div'], class_=re.compile(r'tender|row|item', re.I))

    for row in tender_rows[:50]:  # Limit to avoid excessive parsing
        try:
            tender = {}

            # Try common field selectors
            title_elem = row.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name', re.I))
            if title_elem:
                tender['title'] = title_elem.get_text(strip=True)
                link = title_elem.get('href')
                if link:
                    tender['url'] = link

            # Date fields
            date_elem = row.find(['span', 'td'], class_=re.compile(r'date|deadline', re.I))
            if date_elem:
                tender['deadline'] = date_elem.get_text(strip=True)

            # Organization
            org_elem = row.find(['span', 'td'], class_=re.compile(r'org|buyer|issuer', re.I))
            if org_elem:
                tender['organization'] = org_elem.get_text(strip=True)

            if tender.get('title'):
                tenders.append(tender)

        except Exception as e:
            logger.debug(f"Error parsing tender row: {e}")
            continue

    return tenders


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Try to parse various date formats."""
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # Try common formats
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

    logger.debug(f"Could not parse date: {date_str}")
    return date_str


def save_tenders(conn: duckdb.DuckDatabaseConnection, tenders: List[Dict]):
    """Save tenders to DuckDB."""
    if not tenders:
        logger.warning("No tenders to save")
        return

    logger.info(f"Saving {len(tenders)} tenders to {DB_FILE}...")

    for tender in tenders:
        try:
            # Handle duplicate tenders (upsert)
            conn.execute("""
                DELETE FROM tenders WHERE tender_id = ?
            """, [tender['tender_id']])

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
            logger.error(f"Error saving tender {tender.get('tender_id')}: {e}")

    conn.commit()
    logger.info(f"✓ Saved {len(tenders)} tenders")


def main():
    """Main scraper workflow."""
    logger.info("=" * 60)
    logger.info("Tenders on Time Scraper")
    logger.info("=" * 60)

    try:
        # Load credentials
        logger.info("Loading credentials...")
        username, password = load_credentials()
        logger.info(f"✓ Loaded credentials for {username}")

        # Setup database
        logger.info(f"Setting up database at {DB_FILE}...")
        conn = setup_database()
        logger.info("✓ Database ready")

        # Create session
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        # Scrape tenders
        logger.info("Starting tender scrape...")
        tenders = scrape_tenders(username, password, session)

        # Save results
        if tenders:
            save_tenders(conn, tenders)

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Scrape Summary")
        logger.info("=" * 60)
        result = conn.execute("SELECT commodity, COUNT(*) as count FROM tenders GROUP BY commodity ORDER BY count DESC").fetchall()
        for commodity, count in result:
            logger.info(f"  {commodity}: {count} tenders")

        total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
        logger.info(f"\nTotal tenders: {total}")
        logger.info(f"Database: {DB_FILE}")

        conn.close()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
