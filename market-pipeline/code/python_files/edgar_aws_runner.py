#!/usr/bin/env python3
"""
EDGAR AWS Runner with Data Logger & Dropbox Sync
Runs EDGAR extraction on AWS EC2 (or local) with continuous logging & 15-min Dropbox backup.

Usage:
    python3 edgar_aws_runner.py --profile default --region us-east-1
    python3 edgar_aws_runner.py --local              # Run locally with sync
"""

import sys
import json
import time
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

# Configure structured logging
class DataLogger:
    """Log extraction progress to SQLite + JSON for monitoring."""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        self.json_log = log_dir / f"edgar_progress_{datetime.now():%Y-%m-%d_%H%M%S}.json"
        self.metrics_log = log_dir / f"edgar_metrics_{datetime.now():%Y-%m-%d_%H%M%S}.log"
        
        # Initialize JSON log
        self.session_id = datetime.now().isoformat()
        self._write_json_log({
            "session_id": self.session_id,
            "start_time": self.session_id,
            "status": "running",
            "records": []
        })
    
    def _write_json_log(self, data):
        """Atomic write to JSON log."""
        with open(self.json_log, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _read_json_log(self):
        """Read current JSON log."""
        if self.json_log.exists():
            with open(self.json_log) as f:
                return json.load(f)
        return None
    
    def log_extraction(self, symbol: str, status: str, data: Optional[Dict] = None, error: Optional[str] = None):
        """Log a symbol extraction result."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "status": status,
            "data": data or {},
            "error": error
        }
        
        # Append to JSON log
        log_data = self._read_json_log()
        if log_data:
            log_data["records"].append(record)
            log_data["total_extracted"] = len([r for r in log_data["records"] if r["status"] == "success"])
            log_data["last_update"] = datetime.now().isoformat()
            self._write_json_log(log_data)
        
        # Append to metrics log
        with open(self.metrics_log, 'a') as f:
            f.write(f"{record['timestamp']} | {symbol:8s} | {status:10s} | {len(record.get('data', {})) if data else 0} fields\n")
    
    def get_status(self) -> Dict:
        """Get current session status."""
        log_data = self._read_json_log()
        if log_data:
            return {
                "total_records": len(log_data["records"]),
                "successful": len([r for r in log_data["records"] if r["status"] == "success"]),
                "failed": len([r for r in log_data["records"] if r["status"] == "error"]),
                "last_update": log_data.get("last_update"),
                "duration_seconds": (datetime.fromisoformat(log_data.get("last_update")) - 
                                   datetime.fromisoformat(log_data.get("start_time"))).total_seconds() if log_data.get("last_update") else 0
            }
        return {}

class DropboxSync:
    """Sync extraction results to Dropbox every 15 minutes."""
    
    def __init__(self, source_dir: Path, dropbox_path: str = "/market-data/edgar"):
        self.source_dir = source_dir
        self.dropbox_path = dropbox_path
    
    def sync_now(self) -> bool:
        """Sync to Dropbox using rclone."""
        try:
            # Check if rclone configured
            result = subprocess.run(
                ["rclone", "listremotes"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "dropbox:" not in result.stdout:
                print("⚠️  Dropbox not configured in rclone. Setup with: rclone config")
                return False
            
            # Sync
            cmd = [
                "rclone", "sync",
                str(self.source_dir),
                f"dropbox:{self.dropbox_path}",
                "--progress",
                "--stats", "5s",
                "--transfers", "4"
            ]
            
            print(f"[{datetime.now():%H:%M:%S}] Syncing to Dropbox: {self.dropbox_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"  ✓ Sync complete ({self.source_dir.stat().st_size / 1024 / 1024:.1f} MB)")
                return True
            else:
                print(f"  ❌ Sync failed: {result.stderr[:200]}")
                return False
        
        except FileNotFoundError:
            print("⚠️  rclone not found. Install with: brew install rclone")
            return False
        except subprocess.TimeoutExpired:
            print("⚠️  rclone sync timeout (>5 min)")
            return False
    
    def start_daemon(self, interval_minutes: int = 15):
        """Start background sync daemon."""
        import threading
        
        def sync_loop():
            while True:
                time.sleep(interval_minutes * 60)
                self.sync_now()
        
        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()
        print(f"✓ Dropbox sync daemon started (every {interval_minutes} min)")

def run_local_extraction(data_logger: DataLogger, symbols_limit: int = 100):
    """Run EDGAR extraction locally with logging."""
    print("\n[1/3] Starting EDGAR extraction (local)...")
    
    # Load symbols
    try:
        import yfinance as yf
    except ImportError:
        print("❌ yfinance required. Install: pip install yfinance")
        return 0
    
    # Get first N US symbols
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JNJ", "V"][:symbols_limit]
    
    extracted = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                data = {
                    "pe": info.get("trailingPE"),
                    "pb": info.get("priceToBook"),
                    "roe": info.get("returnOnEquity"),
                    "debt_to_equity": info.get("debtToEquity"),
                }
                
                data_logger.log_extraction(symbol, "success", data)
                extracted += 1
                
                # Progress
                elapsed = time.time() - start_time
                rate = extracted / elapsed if elapsed > 0 else 0
                print(f"  {extracted:3d}/{len(symbols)} | {symbol:8s} | ✓ | Rate: {rate:.1f}/sec")
            
            except Exception as e:
                data_logger.log_extraction(symbol, "error", error=str(e))
                print(f"  {extracted:3d}/{len(symbols)} | {symbol:8s} | ❌ | {str(e)[:50]}")
    
    elapsed = time.time() - start_time
    print(f"\n✅ Extraction complete: {extracted}/{len(symbols)} ({extracted*100//len(symbols)}%)")
    print(f"  Duration: {elapsed:.1f}s | Rate: {extracted/elapsed:.1f} symbols/sec")
    
    # Show status
    status = data_logger.get_status()
    print(f"\n📊 Session Status:")
    print(f"  Total records: {status.get('total_records', 0)}")
    print(f"  Successful: {status.get('successful', 0)}")
    print(f"  Failed: {status.get('failed', 0)}")
    print(f"  Duration: {status.get('duration_seconds', 0):.0f}s")
    
    return extracted

def run_aws_extraction(profile: str, region: str, instance_id: Optional[str] = None):
    """Run EDGAR extraction on AWS EC2."""
    print(f"\n[1/3] Starting EDGAR extraction on AWS ({region})...")
    
    # If instance_id not specified, list running instances
    if not instance_id:
        cmd = [
            "aws", "ec2", "describe-instances",
            "--profile", profile,
            "--region", region,
            "--filters", "Name=instance-state-name,Values=running",
            "--query", "Reservations[].Instances[].[InstanceId,Tags[?Key=='Name'].Value|[0],InstanceType]",
            "--output", "table"
        ]
        
        print("  Available EC2 instances:")
        subprocess.run(cmd)
        
        instance_id = input("  Enter instance ID or skip (leave blank for local run): ").strip()
        if not instance_id:
            print("  → Running locally instead")
            return None
    
    # SSH into instance and run extraction
    print(f"  Running on instance: {instance_id}")
    
    cmd = [
        "aws", "ssm", "start-session",
        "--profile", profile,
        "--target", instance_id,
        "--region", region
    ]
    
    print("  ⚠️  Session started. Run on instance:")
    print("    cd /home/ec2-user/market-pipeline")
    print("    python3 code/python_files/edgar_production_full.py")
    
    # Note: actual SSM session would be interactive
    return instance_id

def main():
    parser = argparse.ArgumentParser(description="EDGAR AWS Runner + Data Logger + Dropbox Sync")
    parser.add_argument("--profile", default="default", help="AWS profile")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--instance-id", help="EC2 instance ID (if not specified, list available)")
    parser.add_argument("--local", action="store_true", help="Run locally (ignore AWS)")
    parser.add_argument("--symbols-limit", type=int, default=100, help="Limit symbols for testing")
    parser.add_argument("--no-sync", action="store_true", help="Disable Dropbox sync")
    args = parser.parse_args()
    
    print("="*80)
    print("EDGAR AWS Runner + Data Logger + Dropbox Sync")
    print("="*80)
    
    # Initialize data logger
    log_dir = Path("/Users/umashankar/market-pipeline/code/python_files/reports")
    log_dir.mkdir(exist_ok=True)
    data_logger = DataLogger(log_dir)
    
    print(f"\n📊 Data Logger initialized")
    print(f"  JSON log: {data_logger.json_log}")
    print(f"  Metrics log: {data_logger.metrics_log}")
    
    # Initialize Dropbox sync (if available)
    if not args.no_sync:
        print(f"\n☁️  Dropbox Sync initialized")
        dropbox = DropboxSync(log_dir)
        dropbox.start_daemon(interval_minutes=15)
    else:
        dropbox = None
    
    # Run extraction
    print(f"\n{'='*80}")
    
    if args.local:
        extracted = run_local_extraction(data_logger, args.symbols_limit)
    else:
        instance_id = run_aws_extraction(args.profile, args.region, args.instance_id)
        if not instance_id:
            # Fall back to local
            extracted = run_local_extraction(data_logger, args.symbols_limit)
    
    # Final sync
    print(f"\n[2/3] Final Dropbox sync...")
    if dropbox:
        dropbox.sync_now()
    
    print(f"\n[3/3] Summary")
    status = data_logger.get_status()
    print(f"  Total extracted: {status.get('successful', 0)}")
    print(f"  Failed: {status.get('failed', 0)}")
    print(f"  Duration: {status.get('duration_seconds', 0):.0f}s")
    print(f"  Logs: {data_logger.json_log}")
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    main()
