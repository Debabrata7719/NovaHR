import os
import re
from datetime import datetime, timedelta
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import dateparser
from zoneinfo import ZoneInfo

SCOPES = ["https://www.googleapis.com/auth/calendar"]

TOKEN_FILE = "token.json"

CREDENTIALS_FILE = "credentials.json"

TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_calendar_service():
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def validate_and_fix_time(time_str: str) -> str:
    """
    Validate and fix common time parsing issues.

    '08.10 pm' → '20:10'
    '8.10pm' → '20:10'
    '9am' → '09:00'
    '2.30pm' → '14:30'
    '2:30pm' → '14:30'
    '8pm' → '20:00'

    Returns the corrected time string or original if no fix needed.
    """
    if not time_str or not isinstance(time_str, str):
        return time_str

    original = time_str
    time_str = time_str.lower().strip()

    decimal_match = re.match(r"^(\d{1,2})\.(\d{1,2})\s*(am|pm)?$", time_str)
    if decimal_match:
        hour = int(decimal_match.group(1))
        minute = int(decimal_match.group(2))
        period = decimal_match.group(3)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        if hour > 23 or minute > 59:
            return original

        return f"{hour:02d}:{minute:02d}"

    colon_match = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)?$", time_str)
    if colon_match:
        hour = int(colon_match.group(1))
        minute = int(colon_match.group(2))
        period = colon_match.group(3)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    simple_match = re.match(r"^(\d{1,2})\s*(am|pm)$", time_str)
    if simple_match:
        hour = int(simple_match.group(1))
        period = simple_match.group(2)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"

    return time_str

    original = time_str
    time_str = time_str.lower().strip()

    decimal_match = re.match(r"^(\d{1,2})\.(\d{1,2})\s*(am|pm)?$", time_str)
    if decimal_match:
        hour = int(decimal_match.group(1))
        minute = int(decimal_match.group(2))
        period = decimal_match.group(3)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        if hour > 23 or minute > 59:
            return original

        return f"{hour:02d}:{minute:02d}"

    simple_match = re.match(r"^(\d{1,2})\s*(am|pm)$", time_str)
    if simple_match:
        hour = int(simple_match.group(1))
        period = simple_match.group(2)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"

    return time_str

    original = time_str
    time_str = time_str.lower().strip()

    decimal_match = re.match(r"^(\d{1,2})\.(\d{1,2})\s*(am|pm)?$", time_str)
    if decimal_match:
        hour = int(decimal_match.group(1))
        minute = int(decimal_match.group(2))
        period = decimal_match.group(3)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        if hour > 23 or minute > 59:
            return original

        return f"{hour:02d}:{minute:02d}"

    return time_str


def create_event(
    title: str,
    date: str,
    time: str,
    description: str = "",
    attendee_emails: Optional[list] = None,
) -> dict:
    try:
        service = get_calendar_service()

        parsed_date = dateparser.parse(date)
        if not parsed_date:
            return {
                "success": False,
                "error": f"Could not parse date: {date}",
            }

        if time:
            fixed_time = validate_and_fix_time(time)

            time_match = re.match(r"^(\d{2}):(\d{2})$", fixed_time)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                start_datetime = datetime(
                    parsed_date.year,
                    parsed_date.month,
                    parsed_date.day,
                    hour,
                    minute,
                    tzinfo=TIMEZONE,
                )
                end_datetime = start_datetime + timedelta(hours=1)
            else:
                parsed_time = dateparser.parse(fixed_time)
                if parsed_time:
                    start_datetime = datetime(
                        parsed_date.year,
                        parsed_date.month,
                        parsed_date.day,
                        parsed_time.hour,
                        parsed_time.minute,
                        tzinfo=TIMEZONE,
                    )
                    end_datetime = start_datetime + timedelta(hours=1)
                else:
                    start_datetime = parsed_date.replace(tzinfo=TIMEZONE)
                    end_datetime = start_datetime + timedelta(hours=1)
        else:
            start_datetime = parsed_date.replace(tzinfo=TIMEZONE)
            end_datetime = start_datetime + timedelta(hours=1)

        start_iso = start_datetime.isoformat()
        end_iso = end_datetime.isoformat()

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        }

        if attendee_emails:
            event["attendees"] = [{"email": email} for email in attendee_emails]

        event = service.events().insert(calendarId="primary", body=event).execute()

        return {
            "success": True,
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink"),
            "title": event.get("summary"),
            "start": event["start"].get("dateTime"),
            "end": event["end"].get("dateTime"),
        }

    except HttpError as error:
        return {"success": False, "error": f"Google Calendar API error: {error}"}
    except Exception as error:
        return {"success": False, "error": str(error)}


def get_events(date: str, max_results: int = 10) -> dict:
    try:
        service = get_calendar_service()

        parsed_date = dateparser.parse(date)
        if not parsed_date:
            return {
                "success": False,
                "error": f"Could not parse date: {date}",
            }

        start_of_day = parsed_date.replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=TIMEZONE
        )
        end_of_day = parsed_date.replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=TIMEZONE
        )

        start_rfc3339 = start_of_day.isoformat()
        end_rfc3339 = end_of_day.isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_rfc3339,
                timeMax=end_rfc3339,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        event_list = []
        for event in events:
            event_list.append(
                {
                    "id": event.get("id"),
                    "title": event.get("summary"),
                    "description": event.get("description"),
                    "start": event["start"].get("dateTime"),
                    "end": event["end"].get("dateTime"),
                    "html_link": event.get("htmlLink"),
                }
            )

        return {
            "success": True,
            "date": date,
            "total_events": len(event_list),
            "events": event_list,
        }

    except HttpError as error:
        return {"success": False, "error": f"Google Calendar API error: {error}"}
    except Exception as error:
        return {"success": False, "error": str(error)}
