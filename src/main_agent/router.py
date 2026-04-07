from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

_client = None

AVAILABLE_AGENTS = ["email", "general"]

SYSTEM_PROMPT = """You are a task router for NovaHR assistant. Your job is to classify user requests into one of these categories:

1. "email" - Send emails, email-related tasks, communicate with employees
2. "general" - Conversational, help requests, or unrecognized tasks

Rules:
- Be conservative: if unsure, default to "general"
- "email" is only for clear email sending/communication tasks
- Return ONLY the category name in lowercase
- Do not include quotes or extra text
"""

ROUTING_PROMPT = """Classify this user request:

User: {user_input}

Category:"""


def get_groq_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


def route_task(user_input: str) -> dict:
    client = get_groq_client()

    prompt = ROUTING_PROMPT.format(user_input=user_input)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=20,
        )

        content = response.choices[0].message.content
        result = content.strip().lower() if content else "general"

        if result not in AVAILABLE_AGENTS:
            result = "general"

        return {
            "intent": result,
            "confidence": "high" if result != "general" else "medium",
            "reasoning": f"Routed to '{result}' based on intent analysis",
        }

    except Exception as e:
        return {
            "intent": "general",
            "confidence": "low",
            "reasoning": f"Routing failed: {str(e)}. Defaulting to 'general'",
            "error": str(e),
        }


def parse_email_details(user_input: str) -> dict:
    client = get_groq_client()

    prompt = f"""Extract email-related details from this user request:

User: {user_input}

Extract:
1. recipients: Who should receive the email? (employee ID, department name, person name, or 'all')
2. subject_hint: Any hints about the email subject (or empty string)
3. content_hint: Any details about what the email should say

Return as JSON with keys: recipients, subject_hint, content_hint
Only return the JSON, nothing else."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You extract email details. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=200,
        )

        import json

        content = response.choices[0].message.content
        content = content.strip() if content else "{}"
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())

    except Exception as e:
        return {
            "recipients": "all",
            "subject_hint": "",
            "content_hint": user_input,
            "error": str(e),
        }
