from datetime import datetime
from typing import Optional
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

_mongo_client = None

MAX_RECENT_MESSAGES = 20


def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient("mongodb://localhost:27017/")
    return _mongo_client


def get_employee_memory_collection():
    client = get_mongo_client()
    db = client["Memory"]
    return db["Agent_memory"]


def get_employee_memory(emp_id: str) -> dict:
    collection = get_employee_memory_collection()
    employee = collection.find_one({"employee_id": emp_id})

    if not employee:
        employee = {
            "employee_id": emp_id,
            "name": None,
            "preferences": {
                "communication_style": "formal",
                "tone": "polite",
            },
            "task_history": [],
            "recent_messages": [],
        }
        collection.insert_one(employee)
        return employee

    return employee


def get_employee_by_id(emp_id: str) -> Optional[dict]:
    collection = get_employee_memory_collection()
    return collection.find_one({"employee_id": emp_id})


def update_employee_info(emp_id: str, name: str | None = None) -> dict:
    collection = get_employee_memory_collection()
    update_fields = {}

    if name is not None:
        update_fields["name"] = name

    if update_fields:
        collection.update_one({"employee_id": emp_id}, {"$set": update_fields})

    result = get_employee_by_id(emp_id)
    return result if result is not None else {"employee_id": emp_id}


def save_employee_task_entry(
    emp_id: str,
    intent: str,
    agent: str,
    task_input: str,
    task_output: str,
    details: Optional[dict] = None,
    status: str = "success",
) -> dict:
    collection = get_employee_memory_collection()

    if collection.find_one({"employee_id": emp_id}) is None:
        get_employee_memory(emp_id)

    task_entry = {
        "intent": intent,
        "agent": agent,
        "input": task_input,
        "output": task_output,
        "details": details or {},
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    collection.update_one(
        {"employee_id": emp_id},
        {"$push": {"task_history": {"$each": [task_entry], "$slice": -50}}},
    )

    return task_entry


def save_batch_task_entry(
    emp_ids: list[str],
    intent: str,
    agent: str,
    task_input: str,
    task_output: str,
    details: dict | None = None,
    status: str = "success",
) -> list[dict]:
    entries = []
    for emp_id in emp_ids:
        entry = save_employee_task_entry(
            emp_id=emp_id,
            intent=intent,
            agent=agent,
            task_input=task_input,
            task_output=task_output,
            details=details,
            status=status,
        )
        entries.append(entry)
    return entries


def append_recent_message(emp_id: str, role: str, content: str) -> dict:
    collection = get_employee_memory_collection()

    if collection.find_one({"employee_id": emp_id}) is None:
        get_employee_memory(emp_id)

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }

    collection.update_one(
        {"employee_id": emp_id},
        {
            "$push": {
                "recent_messages": {
                    "$each": [message],
                    "$slice": -MAX_RECENT_MESSAGES,
                }
            }
        },
    )

    return message


def get_recent_messages(emp_id: str, limit: int = 10) -> list[dict]:
    employee = get_employee_by_id(emp_id)
    if not employee:
        return []

    messages = employee.get("recent_messages", [])
    return messages[-limit:] if limit > 0 else messages


def get_task_history(emp_id: str, limit: int = 10) -> list[dict]:
    employee = get_employee_by_id(emp_id)
    if not employee:
        return []

    history = employee.get("task_history", [])
    return history[-limit:] if limit > 0 else history


def update_preferences(emp_id: str, preferences: dict) -> dict:
    collection = get_employee_memory_collection()

    if collection.find_one({"employee_id": emp_id}) is None:
        get_employee_memory(emp_id)

    collection.update_one(
        {"employee_id": emp_id},
        {"$set": {"preferences": preferences}},
    )

    result: dict = get_employee_by_id(emp_id) or {
        "employee_id": emp_id,
        "preferences": preferences,
    }
    return result


def get_employee_memory_prompt(emp_id: str) -> str:
    employee = get_employee_memory(emp_id)

    if not employee:
        return ""

    task_history = employee.get("task_history", [])
    preferences = employee.get("preferences", {})

    parts = [f"Employee ID: {emp_id}"]

    name = employee.get("name")
    if name:
        parts.append(f"Name: {name}")

    if preferences:
        parts.append(
            f"Preferences: communication_style={preferences.get('communication_style', 'formal')}, "
            f"tone={preferences.get('tone', 'polite')}"
        )

    if task_history:
        parts.append(
            f"Task history ({len(task_history)} recent tasks): "
            + "; ".join([t.get("output", "")[:50] for t in task_history[-3:]])
        )

    return "\n".join(parts)


def clear_employee_memory(emp_id: str) -> bool:
    collection = get_employee_memory_collection()
    result = collection.delete_one({"employee_id": emp_id})
    return result.deleted_count > 0


def get_all_employees_memory() -> list[dict]:
    collection = get_employee_memory_collection()
    return list(collection.find({}))


def get_recent_memories(limit: int = 10) -> list:
    collection = get_employee_memory_collection()
    all_docs = list(collection.find({}))
    all_last_tasks = []
    for doc in all_docs:
        task_history = doc.get("task_history", [])
        if task_history:
            all_last_tasks.append(task_history[-1])
    # Sort by timestamp stored inside each task entry
    all_last_tasks.sort(
        key=lambda t: t.get("timestamp", ""),
        reverse=True,
    )
    return all_last_tasks[:limit]


def get_memory_context(user_input: str, limit: int = 3) -> str:
    recent = get_recent_memories(limit=limit)

    if not recent:
        return "No previous interactions found."

    context_parts = ["Previous interactions:"]
    for mem in recent:
        timestamp = mem.get("timestamp", "")
        if isinstance(timestamp, str):
            time_str = timestamp.split("T")[0] if "T" in timestamp else timestamp
        else:
            time_str = str(timestamp)

        context_parts.append(
            f"- [{time_str}] {mem.get('output', mem.get('action_taken', 'N/A'))} "
            f"(via {mem.get('agent', mem.get('agent_used', 'N/A'))})"
        )

    return "\n".join(context_parts)
