# Tenders on Time Scraper

Automated scraper to extract tender data for ethanol, biogas, SAF, lubricants, and other commodities from Tenders on Time.

## Setup

### 1. Install Dependencies

```bash
pip install -r tenders_requirements.txt
```

### 2. Verify Credentials File

Make sure your credentials are in `~/.config/market-secrets/credentials.env`:

```bash
# Check the file exists and has correct permissions
ls -la ~/.config/market-secrets/credentials.env

# Should show: -rw------- (mode 600)
```

### 3. Run the Scraper

**Option A: Basic Scraper (requests-based)**

```bash
python tenders_scraper.py
```

This works for most sites. Output: `~/tenders_data.duckdb`

**Option B: Selenium Scraper (for JavaScript-heavy sites)**

```bash
python tenders_scraper_selenium.py
```

Use this if Option A doesn't return results. Requires Chrome/Chromium installed.

## Output

Results are stored in **DuckDB** at `~/tenders_data.duckdb` with schema:

| Column | Type | Description |
|--------|------|-------------|
| `tender_id` | VARCHAR | Unique identifier |
| `title` | VARCHAR | Tender title |
| `commodity` | VARCHAR | Commodity type (ethanol, biogas, etc.) |
| `description` | VARCHAR | Full tender description |
| `tender_url` | VARCHAR | Link to tender |
| `issued_date` | DATE | When tender was issued |
| `deadline` | DATE | Tender closing date |
| `organization` | VARCHAR | Buyer/organization |
| `tender_type` | VARCHAR | Open/restricted/limited |
| `estimated_value` | VARCHAR | Tender value |
| `raw_json` | VARCHAR | Full JSON response |
| `scraped_at` | TIMESTAMP | When scraped |

## Querying Results

```python
import duckdb

conn = duckdb.connect('~/tenders_data.duckdb')

# All tenders by commodity
conn.execute("SELECT commodity, COUNT(*) FROM tenders GROUP BY commodity").show()

# Upcoming deadlines
conn.execute("""
    SELECT title, commodity, deadline, organization
    FROM tenders
    WHERE deadline > CURRENT_DATE
    ORDER BY deadline ASC
    LIMIT 20
""").show()

# Export to CSV
conn.execute("COPY tenders TO 'tenders_export.csv' (FORMAT CSV, HEADER)").show()

conn.close()
```

## Troubleshooting

### Issue: Login fails or returns empty results

**Try Selenium version:**
```bash
python tenders_scraper_selenium.py
```

### Issue: No tenders found

1. Check credentials in `~/.config/market-secrets/credentials.env`
2. Try logging in manually at https://www.tenderontime.com to verify access
3. Check if site URL has changed
4. Look at script logs for specific errors

### Issue: "Credentials file not found"

Make sure the file exists:
```bash
mkdir -p ~/.config/market-secrets
cat ~/.config/market-secrets/credentials.env
```

### Issue: Selenium can't find Chrome

Install Chrome or Chromium:
```bash
# macOS
brew install --cask google-chrome

# Linux
sudo apt-get install chromium-browser
```

## Customization

### Add More Commodities

Edit `COMMODITIES` list in the script:

```python
COMMODITIES = [
    'ethanol',
    'biogas',
    'SAF',
    'lubricants',
    'copper',  # Add more
    'aluminum',
    'plastic pellets',
]
```

### Change Search URL

If the site URL has changed, edit:

```python
base_url = "https://www.tenderontime.com"  # Update this
```

### Export to Different Formats

```bash
# DuckDB → CSV
duckdb -c "COPY (SELECT * FROM tenders) TO 'export.csv' (FORMAT CSV, HEADER)" ~/tenders_data.duckdb

# DuckDB → JSON
duckdb -c "COPY (SELECT * FROM tenders) TO 'export.json' (FORMAT JSON)" ~/tenders_data.duckdb

# DuckDB → Parquet
duckdb -c "COPY (SELECT * FROM tenders) TO 'export.parquet' (FORMAT PARQUET)" ~/tenders_data.duckdb
```

## Scheduling (Optional)

### macOS (launchd)

Create `~/Library/LaunchAgents/com.market.tenders.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.market.tenders</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/umashankar/tenders_scraper.py</string>
    </array>
    <key>StartInterval</key>
    <integer>86400</integer>  <!-- Every 24 hours -->
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.market.tenders.plist
```

### Linux (cron)

```bash
# Run daily at 6 AM
0 6 * * * /usr/bin/python3 /home/user/tenders_scraper.py
```

## Performance

- **Requests-based**: ~30-60 seconds per 10 commodities
- **Selenium-based**: ~2-5 minutes (slower due to browser overhead)

For daily runs, use the requests-based version. Switch to Selenium only if needed.

## Security Notes

- ✅ Credentials loaded from `.env` file (mode 600)
- ✅ No credentials hardcoded in script
- ✅ DuckDB stored locally
- ⚠️ Change password after sharing it in chat/email
- ⚠️ Never commit credentials file to git

## Support

If the scraper breaks, it's likely due to site structure changes. Check:

1. Is the site still at `tenderontime.com`?
2. Did the login form change?
3. Are search results in a different HTML structure?

Adjust the parsing code in `parse_html_tenders()` or use Selenium for more robust extraction.
