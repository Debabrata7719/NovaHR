from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

from src.tools.calendar_tools import create_event, get_events


def get_groq_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def decide_action(user_input: str, memory_context: str = "") -> dict:
    client = get_groq_client()

    system_prompt = """You are a scheduling decision agent. Your job is to classify the user's request into one of these actions:

1. "create_event" - Create a new calendar event (meeting, appointment, reminder, book meeting, schedule something)
2. "get_events" - Fetch/retrieve/view events for a specific date (what's on calendar, show events, any meetings)

CRITICAL RULES - Use "create_event" for these patterns:
- "schedule a meeting", "book an event", "add to calendar", "set reminder"
- "do same", "do again", "repeat", "again", "same thing" - refers to creating NEW event similar to before
- Any request to CREATE, ADD, SCHEDULE, BOOK something
- "for today", "for tomorrow", "next Monday" - when combined with scheduling intent

Use "get_events" for these patterns:
- "what's on my calendar", "show events", "view calendar", "any meetings"
- "what did I schedule", "show my events"
- Any request to VIEW, CHECK, SHOW existing events

EXAMPLES:
- "schedule a meeting tomorrow" -> create_event
- "do same for today 1pm" -> create_event ("same" means create similar to before)
- "book a call at 3pm" -> create_event
- "what's on my calendar today?" -> get_events
- "show me my events" -> get_events
- "any meetings tomorrow?" -> get_events
- "do it again" -> create_event (again means create new)

Return ONLY the action name in lowercase.
Do not include quotes or extra text."""

    if memory_context:
        prompt = f"""Classify this user request. Consider the conversation history:

Conversation History:
{memory_context}

User: {user_input}

Action:"""
    else:
        prompt = f"""Classify this user request:

User: {user_input}

Action:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=20,
        )

        content = response.choices[0].message.content
        action = content.strip().lower() if content else "create_event"

        if action not in ["create_event", "get_events"]:
            action = "create_event"

        return {"action": action, "confidence": "high"}

    except Exception as e:
        return {"action": "create_event", "confidence": "low", "error": str(e)}


def extract_create_event_details(user_input: str) -> dict:
    client = get_groq_client()

    prompt = f"""Extract calendar event details from this user request:

User: {user_input}

Extract:
1. title: What is the event/meeting about? (or "Untitled Event" if unclear)
2. date: When should the event be? (use natural language like "tomorrow", "next Monday", "2026-04-10", "today")
3. time: At what time? 
   - CRITICAL: Handle time formats correctly
   - '09.35 pm' means 9:35 PM (21:35 in 24-hour), NOT 09:35
   - '08.10 pm' or '8.10 pm' means 08:10 PM (20:10), NOT 02:40
   - '9am' or '09.00 am' means 09:00
   - '2.30pm' or '2:30 pm' means 14:30
   - Use 24-hour format: '21:35' not '09.35 pm'
4. description: Any additional details about the event (or empty string)
5. attendees: Any email addresses mentioned (or empty list)

IMPORTANT TIME RULES:
- '09.35 pm' or '9.35 pm' → time: '21:35' (9:35 PM in 24-hour)
- '08.10 pm' or '8.10 pm' → time: '20:10'
- '9am' or '09.00 am' → time: '09:00'
- '2:30pm' or '2.30 pm' → time: '14:30'
- '8pm' or '08.00 pm' → time: '20:00'
- ALWAYS add 12 to hour when converting PM times (except 12pm=12, 12am=0)

Return as JSON with keys: title, date, time, description, attendees
Only return the JSON, nothing else."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You extract calendar event details. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )

        content = response.choices[0].message.content
        content = content.strip() if content else "{}"

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content.strip())

    except Exception as e:
        return {
            "title": "Untitled Event",
            "date": "",
            "time": "",
            "description": "",
            "attendees": [],
            "error": str(e),
        }


def extract_get_events_details(user_input: str) -> dict:
    client = get_groq_client()

    prompt = f"""Extract calendar fetch details from this user request:

User: {user_input}

Extract:
1. date: What date to fetch events for? (yesterday, today, tomorrow, specific date, or empty for today)
2. max_results: How many events to fetch? (default 10)

Return as JSON with keys: date, max_results
Only return the JSON, nothing else."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You extract calendar fetch details. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=100,
        )

        content = response.choices[0].message.content
        content = content.strip() if content else "{}"

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        details = json.loads(content.strip())

        if not details.get("date"):
            details["date"] = "today"

        return details

    except Exception as e:
        return {"date": "today", "max_results": 10, "error": str(e)}


def execute_scheduling_task(
    user_input: str,
    employee_memory: str = "",
    memory_context: str = "",
) -> dict:
    try:
        decision_result = decide_action(user_input, memory_context)
        action = decision_result.get("action", "get_events")

        if action == "create_event":
            details = extract_create_event_details(user_input)

            title = details.get("title", "Untitled Event")
            date = details.get("date", "")
            time = details.get("time", "")
            description = details.get("description", "")
            attendees = details.get("attendees", [])

            if not date:
                return {
                    "success": False,
                    "action": "create_event",
                    "action_summary": "Could not determine date for the event",
                    "error": "Date is required",
                }

            result = create_event(
                title=title,
                date=date,
                time=time,
                description=description,
                attendee_emails=attendees if attendees else None,
            )

            if result.get("success"):
                actual_time = result.get("start", "")
                formatted_time = ""

                if actual_time:
                    from datetime import datetime
                    from zoneinfo import ZoneInfo

                    try:
                        dt_utc = datetime.fromisoformat(
                            actual_time.replace("Z", "+00:00")
                        )
                        dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
                        formatted_time = dt_ist.strftime("%I:%M %p")
                    except:
                        formatted_time = ""

                return {
                    "success": True,
                    "action": "create_event",
                    "action_summary": f"Created event '{title}' for {date} at {formatted_time}",
                    "details": {
                        "title": title,
                        "date": date,
                        "time": formatted_time,
                        "event_id": result.get("event_id"),
                        "html_link": result.get("html_link"),
                    },
                }
            else:
                return {
                    "success": False,
                    "action": "create_event",
                    "action_summary": f"Failed to create event: {result.get('error')}",
                    "error": result.get("error"),
                }

        elif action == "get_events":
            details = extract_get_events_details(user_input)

            date = details.get("date", "today")
            max_results = details.get("max_results", 10)

            result = get_events(date=date, max_results=max_results)

            if result.get("success"):
                events = result.get("events", [])
                event_count = len(events)

                if event_count == 0:
                    summary = f"No events found for {date}"
                elif event_count == 1:
                    summary = f"1 event on {date}: {events[0]['title']}"
                else:
                    event_titles = [e["title"] for e in events[:3]]
                    summary = (
                        f"{event_count} events on {date}: {', '.join(event_titles)}"
                    )
                    if event_count > 3:
                        summary += f" and {event_count - 3} more"

                return {
                    "success": True,
                    "action": "get_events",
                    "action_summary": summary,
                    "details": {
                        "date": date,
                        "total_events": event_count,
                        "events": events,
                    },
                }
            else:
                return {
                    "success": False,
                    "action": "get_events",
                    "action_summary": f"Failed to fetch events: {result.get('error')}",
                    "error": result.get("error"),
                }

        else:
            return {
                "success": False,
                "action": action,
                "action_summary": f"Unknown action: {action}",
                "error": "Unhandled action type",
            }

    except Exception as e:
        return {
            "success": False,
            "action_summary": f"Task execution failed: {str(e)}",
            "error": str(e),
        }
