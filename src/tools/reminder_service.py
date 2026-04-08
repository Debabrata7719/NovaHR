import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
import dateparser

from src.tools.calendar_tools import get_events


REMINDER_WINDOW_MINUTES = 10
CHECK_INTERVAL_SECONDS = 60

notified_events: set = set()


def get_today_events() -> list[dict]:
    result = get_events(date="today", max_results=50)
    if not result.get("success"):
        return []
    return result.get("events", [])


def parse_event_datetime(date_time_str: str) -> Optional[datetime]:
    try:
        dt_utc = datetime.fromisoformat(date_time_str.replace("Z", "+00:00"))
        dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        return dt_ist
    except (ValueError, TypeError):
        return None


def get_time_until_event(event_start: datetime) -> float:
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    delta = event_start - now_ist
    return delta.total_seconds()


def should_notify(time_left_seconds: float) -> bool:
    return 0 < time_left_seconds <= (REMINDER_WINDOW_MINUTES * 60)


def format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p")


def notify_event(event: dict):
    event_id = event.get("id")
    title = event.get("title", "Untitled Event")
    start_str = event.get("start", "")
    start_dt = parse_event_datetime(start_str)
    time_str = format_time(start_dt) if start_dt else "Unknown time"
    link = event.get("html_link", "")

    print("\n" + "=" * 50)
    print("  REMINDER: Upcoming Event")
    print("=" * 50)
    print(f'  Event: "{title}"')
    print(f"  Time: {time_str}")
    if link:
        print(f"  Link: {link}")
    print("=" * 50 + "\n")


def check_reminders():
    events = get_today_events()
    if not events:
        return

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        start_str = event.get("start", "")
        if not start_str:
            continue

        start_dt = parse_event_datetime(start_str)
        if not start_dt:
            continue

        time_left = get_time_until_event(start_dt)

        if time_left <= 0:
            continue

        if should_notify(time_left):
            if event_id not in notified_events:
                notify_event(event)
                notified_events.add(event_id)


def start_reminder_loop():
    print("[Reminder Service] Starting background reminder check...")

    while True:
        try:
            check_reminders()
        except Exception as e:
            print(f"[Reminder Service] Error: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


def start_reminder_service():
    reminder_thread = threading.Thread(target=start_reminder_loop, daemon=True)
    reminder_thread.start()
    print("[Reminder Service] Running in background (checks every 60s)")
    return reminder_thread


def clear_notified_events():
    notified_events.clear()
