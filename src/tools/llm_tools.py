from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_groq_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


def generate_subject(
    email_content: str, employee_name: str | None = None, employee_memory: str = ""
) -> str:
    client = get_groq_client()

    name_context = f"The recipient's name is {employee_name}." if employee_name else ""

    memory_context = ""
    if employee_memory:
        memory_context = f"\n\nRecipient Memory:\n{employee_memory}"

    prompt = f"""Generate a concise, professional email subject line based on the following email content.
{name_context}{memory_context}

Email Content:
{email_content}

Rules:
- Keep it under 60 characters
- Make it engaging but professional
- Do not include quotes or prefixes like "Subject:"
- Just return the subject line

Subject:"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are an expert email subject line generator. Generate concise, professional subjects.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=50,
    )

    content = response.choices[0].message.content
    return content.strip() if content else "Email from NovaHR"
