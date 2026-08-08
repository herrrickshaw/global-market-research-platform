#!/usr/bin/env python3
"""
Tenders on Time scraper - Selenium version for JavaScript-heavy sites.
Use this if the requests-based scraper doesn't work.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import time

import duckdb
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COMMODITIES = ['ethanol', 'biogas', 'SAF', 'lubricants', 'diesel', 'petrol', 'crude oil', 'natural gas', 'LPG']
CREDS_FILE = Path.home() / '.config' / 'market-secrets' / 'credentials.env'
DB_FILE = Path.home() / 'tenders_data.duckdb'


def load_credentials() -> tuple:
    """Load credentials from .env file."""
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
        raise ValueError("Credentials not found")

    return username, password


def setup_database():
    """Initialize DuckDB."""
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


def scrape_with_selenium(username: str, password: str) -> List[Dict]:
    """Scrape using Selenium for JavaScript-rendered content."""
    tenders = []

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # chrome_options.add_argument('--headless')  # Comment out to see browser

    driver = webdriver.Chrome(options=chrome_options)

    try:
        base_url = "https://www.tenderontime.com"
        logger.info(f"Opening {base_url}...")
        driver.get(base_url)

        # Wait for page to load
        time.sleep(3)

        # Try to find and fill login form
        try:
            logger.info("Attempting login...")

            # Look for email/username field
            email_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[name*='email'], input[name*='user']")
            if email_inputs:
                email_inputs[0].send_keys(username)
                logger.info("  ✓ Entered username")

            # Look for password field
            pwd_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if pwd_inputs:
                pwd_inputs[0].send_keys(password)
                logger.info("  ✓ Entered password")

            # Look for submit button
            buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button:contains('Login'), input[type='submit']")
            if buttons:
                buttons[0].click()
                logger.info("  ✓ Clicked login")

            # Wait for login to complete
            time.sleep(5)

        except Exception as e:
            logger.warning(f"Login attempt failed: {e}. Continuing with public access...")

        # Search for each commodity
        for commodity in COMMODITIES:
            logger.info(f"Searching for: {commodity}")

            try:
                # Try to find and use search box
                search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='search'], input[placeholder*='Search'], input[name*='search']")
                if search_inputs:
                    search_inputs[0].clear()
                    search_inputs[0].send_keys(commodity)
                    time.sleep(1)

                    # Find and click search button
                    search_buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], .search-btn")
                    if search_buttons:
                        search_buttons[0].click()
                        time.sleep(3)

                # Parse results from page source
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Look for tender rows/items
                tender_items = soup.find_all(['tr', 'div'], class_=lambda x: x and 'tender' in x.lower())

                for item in tender_items[:20]:  # Limit per search
                    tender = extract_tender_from_element(item, commodity)
                    if tender and tender.get('title'):
                        tenders.append(tender)

                logger.info(f"  Found {len([t for t in tenders if t.get('commodity') == commodity])} for {commodity}")

            except Exception as e:
                logger.error(f"Error searching {commodity}: {e}")

            time.sleep(2)

    finally:
        driver.quit()
        logger.info("Browser closed")

    return tenders


def extract_tender_from_element(element, commodity: str) -> Optional[Dict]:
    """Extract tender data from HTML element."""
    try:
        tender = {'commodity': commodity}

        # Title
        title_elem = element.find(['h2', 'h3', 'a'])
        if title_elem:
            tender['title'] = title_elem.get_text(strip=True)
            link = title_elem.get('href')
            if link:
                tender['tender_url'] = link

        # Description
        desc = element.get_text(strip=True)
        tender['description'] = desc[:500] if desc else ''

        # ID
        tender['tender_id'] = f"{commodity}_{int(time.time() * 1000)}"

        return tender if tender.get('title') else None

    except Exception as e:
        logger.debug(f"Error extracting tender: {e}")
        return None


def save_tenders(conn: duckdb.DuckDatabaseConnection, tenders: List[Dict]):
    """Save tenders to database."""
    if not tenders:
        logger.warning("No tenders to save")
        return

    logger.info(f"Saving {len(tenders)} tenders...")

    for tender in tenders:
        try:
            conn.execute("DELETE FROM tenders WHERE tender_id = ?", [tender['tender_id']])
            conn.execute("""
                INSERT INTO tenders (
                    tender_id, title, commodity, description, tender_url,
                    organization, tender_type, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                tender['tender_id'],
                tender.get('title', 'N/A'),
                tender.get('commodity', ''),
                tender.get('description', ''),
                tender.get('tender_url', ''),
                tender.get('organization', ''),
                tender.get('tender_type', 'Open'),
                json.dumps(tender),
            ])
        except Exception as e:
            logger.error(f"Error saving tender: {e}")

    conn.commit()
    logger.info(f"✓ Saved {len(tenders)} tenders")


def main():
    logger.info("=" * 60)
    logger.info("Tenders on Time Scraper (Selenium)")
    logger.info("=" * 60)

    try:
        username, password = load_credentials()
        logger.info(f"✓ Loaded credentials for {username}")

        conn = setup_database()
        logger.info("✓ Database ready")

        tenders = scrape_with_selenium(username, password)

        if tenders:
            save_tenders(conn, tenders)

        # Summary
        result = conn.execute("SELECT commodity, COUNT(*) as count FROM tenders GROUP BY commodity").fetchall()
        logger.info("\nResults by commodity:")
        for commodity, count in result:
            logger.info(f"  {commodity}: {count}")

        conn.close()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
