"""Daily scheduler — runs the agent once per day at a configured time.

Usage:
    python scheduler.py              # runs every day at 06:00 UTC
    python scheduler.py --time 08:30 # runs every day at 08:30 UTC

The scheduler keeps running until interrupted (Ctrl+C).
For production, use cron or a process manager instead:
    0 6 * * *  cd /path/to/clancy_monitor && python agent.py >> logs/agent.log 2>&1
"""

import argparse
import time
import schedule
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def run_agent() -> None:
    now = datetime.now(timezone.utc)
    log_path = LOG_DIR / f"run_{now.strftime('%Y%m%d_%H%M%S')}.log"
    print(f"\n[scheduler] Starting agent run at {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"[scheduler] Log → {log_path}")

    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "agent.py")],
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    if proc.returncode == 0:
        print("[scheduler] Agent run completed successfully.")
    else:
        print(f"[scheduler] Agent run exited with code {proc.returncode}. Check log: {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clancy monitor daily scheduler")
    parser.add_argument("--time", default="06:00", help="Daily run time in HH:MM UTC (default 06:00)")
    parser.add_argument("--run-now", action="store_true", help="Run immediately before scheduling")
    args = parser.parse_args()

    if args.run_now:
        run_agent()

    schedule.every().day.at(args.time).do(run_agent)
    print(f"[scheduler] Scheduled daily run at {args.time} UTC. Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
