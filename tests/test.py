from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# connect once
def connect_calendar():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)

    creds = flow.run_local_server(port=0)

    service = build("calendar", "v3", credentials=creds)
    print("Connected!")
    return service


# create event
def create_event(service, title, start, end):
    event = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end, "timeZone": "Asia/Kolkata"},
    }

    event = service.events().insert(calendarId="primary", body=event).execute()
    print("Created:", event.get("htmlLink"))


# main
service = connect_calendar()

start = (datetime.now() + timedelta(minutes=1)).isoformat()
end = (datetime.now() + timedelta(hours=1)).isoformat()

create_event(service, "Test Event", start, end)
