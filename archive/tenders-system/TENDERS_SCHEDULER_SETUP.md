# Tender Scraper Daily Scheduler Setup

Automated daily tender scraping for ethanol, biogas, SAF, lubricants and other commodities.

## Current Status

✅ **Active Schedule:** Daily at **6:00 AM**  
✅ **Job Label:** `com.market.tenders.scraper`  
✅ **Log Location:** `~/logs/tenders_scraper.log`  
✅ **Database:** `~/tenders_data.duckdb`

## Components

### 1. Shell Wrapper Script
**File:** `~/scripts/run_tenders_scraper.sh`

- Creates virtual environment if needed
- Installs dependencies from `tenders_requirements.txt`
- Runs `tenders_scraper_v2.py`
- Logs output to `~/logs/tenders_scraper.log`

### 2. LaunchD Configuration
**File:** `~/Library/LaunchAgents/com.market.tenders.scraper.plist`

- Scheduled to run daily at **6:00 AM**
- Automatically loaded on system startup
- Logs both stdout and stderr to `~/logs/`

## Managing the Job

### View Status
```bash
launchctl list | grep tenders
# Output: PID  Status  Label
#         9262  0      com.market.tenders.scraper
```

### Unload (Disable Scheduling)
```bash
launchctl unload ~/Library/LaunchAgents/com.market.tenders.scraper.plist
```

### Reload (After Changes)
```bash
launchctl unload ~/Library/LaunchAgents/com.market.tenders.scraper.plist
launchctl load ~/Library/LaunchAgents/com.market.tenders.scraper.plist
```

### Run Manually (Now)
```bash
~/scripts/run_tenders_scraper.sh
```

### View Logs
```bash
# Current run log
tail -f ~/logs/tenders_scraper.log

# Error log
tail -f ~/logs/tenders_scraper_error.log

# Last 50 lines
tail -50 ~/logs/tenders_scraper.log
```

## Changing Schedule

Edit `~/Library/LaunchAgents/com.market.tenders.scraper.plist` and modify the `StartCalendarInterval` section:

### Daily at 8:00 AM
```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

### Multiple Times Per Day (6 AM & 2 PM)
```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <dict>
        <key>Hour</key>
        <integer>14</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</array>
```

### Every 6 Hours
```bash
# Use StartInterval instead (seconds)
<key>StartInterval</key>
<integer>21600</integer>  <!-- 6 hours = 6*60*60 seconds -->
```

After editing, reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.market.tenders.scraper.plist
launchctl load ~/Library/LaunchAgents/com.market.tenders.scraper.plist
```

## Troubleshooting

### Job Not Running

1. **Check if loaded:**
   ```bash
   launchctl list | grep tenders
   ```
   If no output, the job isn't loaded. Reload it:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.market.tenders.scraper.plist
   ```

2. **Check logs for errors:**
   ```bash
   tail -20 ~/logs/tenders_scraper_error.log
   ```

3. **Test script manually:**
   ```bash
   ~/scripts/run_tenders_scraper.sh
   ```

### Permissions Issues

Ensure the script is executable:
```bash
chmod +x ~/scripts/run_tenders_scraper.sh
```

### Venv or Dependencies Missing

The script auto-creates the venv on first run. If issues persist:
```bash
rm -rf ~/.venvs/tenders
~/scripts/run_tenders_scraper.sh
```

### Log Directory Missing

Ensure logs directory exists:
```bash
mkdir -p ~/logs
```

## Database Queries

After scheduler runs, query results:

```bash
# All ethanol tenders
duckdb -c "SELECT title, deadline FROM tenders WHERE commodity='ethanol'" ~/tenders_data.duckdb

# Tenders closing within 7 days
duckdb -c "SELECT commodity, title, deadline FROM tenders WHERE CAST(deadline AS DATE) - CURRENT_DATE <= 7 ORDER BY deadline ASC" ~/tenders_data.duckdb

# Count by commodity
duckdb -c "SELECT commodity, COUNT(*) FROM tenders GROUP BY commodity ORDER BY COUNT(*) DESC" ~/tenders_data.duckdb

# Export to CSV
duckdb -c "COPY tenders TO 'tenders_export.csv' (FORMAT CSV, HEADER)" ~/tenders_data.duckdb
```

## System Integration

### Check System Load

Scheduler runs at 6 AM — check if this conflicts with other jobs:
```bash
launchctl list | head -20
```

### Disable Temporarily

```bash
launchctl unload ~/Library/LaunchAgents/com.market.tenders.scraper.plist
```

Re-enable later:
```bash
launchctl load ~/Library/LaunchAgents/com.market.tenders.scraper.plist
```

## Virtual Environment Details

- **Location:** `~/.venvs/tenders`
- **Created automatically** on first run
- **Packages installed:** requests, beautifulsoup4, duckdb, selenium, numpy, pandas
- **Python version:** 3.9+ (auto-detected)

## Credentials

Scraper reads credentials from:
```bash
~/.config/market-secrets/credentials.env
```

Required keys:
- `TENDERS_ON_TIME_USERNAME`
- `TENDERS_ON_TIME_PASSWORD`

Ensure file has mode `600`:
```bash
chmod 600 ~/.config/market-secrets/credentials.env
```

## Monitoring

To monitor upcoming runs:
```bash
# Watch system log for launchd entries
log stream --predicate 'process == "launchd"' --level debug
```

Or check for job execution in system events:
```bash
# View recent runs
defaults read ~/Library/Preferences/com.apple.launchd.plist
```

## Next Steps

1. ✅ Scheduler installed and loaded
2. Monitor first run tomorrow at 6 AM
3. Check `~/logs/tenders_scraper.log` after first run
4. Query `~/tenders_data.duckdb` for results
5. Adjust schedule if needed

---

**Last Updated:** 2026-07-31  
**Job Status:** Active  
**Schedule:** Daily 6:00 AM
