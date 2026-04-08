from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from src.main_agent.memory import (
    get_employee_memory,
    get_memory_context,
    get_recent_memories,
    save_employee_task_entry,
    save_batch_task_entry,
    append_recent_message,
    update_employee_info,
    get_employee_memory_prompt,
)
from src.main_agent.router import route_task, parse_email_details
from src.main_agent.agents.email.executor import execute_email_task
from src.main_agent.agents.scheduling.executor import execute_scheduling_task


class MainAgentState(TypedDict):
    user_input: str
    memory_context: str
    intent: str
    routing_result: dict
    email_details: dict
    execution_result: dict
    memory_stored: bool
    employee_memory: str
    employee_id: str | None
    employee_name: str | None
    recipient_emp_ids: list[str]
    error: str | None


# ── Node functions ──────────────────────────────────────────────────────────


def check_memory(state: MainAgentState) -> MainAgentState:
    try:
        state["memory_context"] = get_memory_context(
            user_input=state["user_input"], limit=3
        )
    except Exception as e:
        state["memory_context"] = f"Memory check failed: {str(e)}"
    return state


def route_to_agent(state: MainAgentState) -> MainAgentState:
    try:
        memory_context = state.get("memory_context", "")
        routing_result = route_task(state["user_input"], memory_context)
        state["intent"] = routing_result["intent"]
        state["routing_result"] = routing_result
        state["error"] = None
    except Exception as e:
        state["intent"] = "general"
        state["routing_result"] = {"intent": "general", "error": str(e)}
        state["error"] = f"Routing failed: {str(e)}"
    return state


def extract_details(state: MainAgentState) -> MainAgentState:
    if state["intent"] == "email":
        try:
            email_details = parse_email_details(state["user_input"])
            state["email_details"] = email_details
        except Exception as e:
            state["email_details"] = {
                "recipients": "all",
                "subject_hint": "",
                "content_hint": state["user_input"],
                "error": str(e),
            }
    return state


def get_employee_memory_for_task(state: MainAgentState) -> MainAgentState:
    if state["intent"] == "email":
        try:
            from src.tools.mysql_tools import (
                get_employees_by_name,
                get_employees_by_department,
                get_all_employees,
            )

            email_details = state.get("email_details", {})
            recipients_query = email_details.get("recipients", "all").lower().strip()

            if recipients_query == "all":
                recipients = get_all_employees()
            elif recipients_query.startswith("dept:") or recipients_query.startswith(
                "department:"
            ):
                dept = (
                    recipients_query.replace("department:", "")
                    .replace("dept:", "")
                    .strip()
                )
                recipients = get_employees_by_department(dept)
            else:
                recipients = get_employees_by_name(recipients_query)

            if recipients:
                first_recipient = recipients[0]
                emp_id = first_recipient.get("employee_id")
                emp_name = first_recipient.get("name")

                if emp_id:
                    state["employee_id"] = emp_id
                    state["employee_name"] = emp_name
                    state["recipient_emp_ids"] = [
                        r.get("employee_id") for r in recipients if r.get("employee_id")
                    ]
                    state["employee_memory"] = get_employee_memory_prompt(emp_id)
        except Exception as e:
            state["employee_id"] = None
            state["employee_name"] = None
            state["recipient_emp_ids"] = []
            state["employee_memory"] = ""
    return state


def execute_task(state: MainAgentState) -> MainAgentState:
    try:
        if state["intent"] == "email":
            email_details = state.get("email_details", {})

            recipients_query = email_details.get("recipients", "all")
            content = email_details.get("content_hint", state["user_input"])
            subject_hint = email_details.get("subject_hint", "")
            employee_memory = state.get("employee_memory", "")

            execution_result = execute_email_task(
                recipients_query=recipients_query,
                email_content=content,
                subject_hint=subject_hint,
                employee_memory=employee_memory,
            )
            state["execution_result"] = execution_result

        elif state["intent"] == "general":
            state["execution_result"] = {
                "success": True,
                "response": "I'm here to help! Currently I can send emails to employees and manage calendar events. Just tell me what you'd like to communicate or schedule.",
                "action_summary": "General query - responded with help message",
            }
        elif state["intent"] == "scheduling":
            employee_memory = state.get("employee_memory", "")
            memory_context = state.get("memory_context", "")

            execution_result = execute_scheduling_task(
                user_input=state["user_input"],
                employee_memory=employee_memory,
                memory_context=memory_context,
            )
            state["execution_result"] = execution_result
        elif state["intent"] == "memory":
            from src.main_agent.memory import get_recent_memories

            user_input_lower = state["user_input"].lower()

            date_filter = None
            if "today" in user_input_lower:
                date_filter = "today"
            elif "yesterday" in user_input_lower:
                date_filter = "yesterday"

            recent_tasks = get_recent_memories(limit=5, date_filter=date_filter)

            if recent_tasks:
                task_list = []
                for i, task in enumerate(recent_tasks, 1):
                    timestamp = task.get("timestamp", "N/A")
                    if "T" in timestamp:
                        timestamp = timestamp.split("T")[0]
                    output = task.get("output", task.get("action_taken", "N/A"))
                    agent = task.get("agent", "N/A")
                    task_list.append(f"{i}. [{timestamp}] {output} (via {agent})")

                response_text = "Here are your recent activities:\n" + "\n".join(
                    task_list
                )
            else:
                response_text = (
                    "No previous activities found. This is your first interaction!"
                )

            state["execution_result"] = {
                "success": True,
                "response": response_text,
                "action_summary": response_text,
            }
        else:
            state["execution_result"] = {
                "success": False,
                "action_summary": f"Unknown intent: {state['intent']}",
                "error": "Unhandled intent type",
            }

        state["error"] = None

    except Exception as e:
        state["execution_result"] = {
            "success": False,
            "action_summary": "Task execution failed",
            "error": str(e),
        }
        state["error"] = str(e)

    return state


def save_memory(state: MainAgentState) -> MainAgentState:
    try:
        execution_result = state.get("execution_result", {})
        success = execution_result.get("success", False)
        action_summary = execution_result.get("action_summary", "No action taken")
        status = "success" if success else "failed"

        intent = state.get("intent", "unknown")
        agent = f"{intent}_agent"
        user_input = state.get("user_input", "")
        recipient_emp_ids = state.get("recipient_emp_ids", [])

        if intent == "email":
            details = {
                "recipients": execution_result.get("recipients_info", []),
                "subject": execution_result.get("subject", ""),
                "total_sent": execution_result.get("email_result", {}).get(
                    "total_sent", 0
                ),
                "total_skipped": execution_result.get("email_result", {}).get(
                    "total_skipped", 0
                ),
            }
        elif intent == "scheduling":
            exec_details = execution_result.get("details", {})
            details = {
                "action": execution_result.get("action", ""),
                "title": exec_details.get("title", ""),
                "date": exec_details.get("date", ""),
                "time": exec_details.get("time", ""),
                "event_id": exec_details.get("event_id", ""),
            }
        else:
            details = {}

        emp_id = state.get("employee_id")
        emp_name = state.get("employee_name")

        if recipient_emp_ids:
            save_batch_task_entry(
                emp_ids=recipient_emp_ids,
                intent=intent,
                agent=agent,
                task_input=user_input,
                task_output=action_summary,
                details=details,
                status=status,
            )
        elif emp_id:
            save_employee_task_entry(
                emp_id=emp_id,
                intent=intent,
                agent=agent,
                task_input=user_input,
                task_output=action_summary,
                details=details,
                status=status,
            )
        elif intent == "scheduling":
            save_employee_task_entry(
                emp_id="calendar_user",
                intent=intent,
                agent=agent,
                task_input=user_input,
                task_output=action_summary,
                details=details,
                status=status,
            )

        if emp_id:
            if emp_name:
                update_employee_info(emp_id, emp_name)

            append_recent_message(
                emp_id=emp_id,
                role="user",
                content=user_input,
            )

            append_recent_message(
                emp_id=emp_id,
                role="assistant",
                content=action_summary,
            )

        state["memory_stored"] = True

    except Exception as e:
        state["memory_stored"] = False
        state["error"] = f"Memory save failed: {str(e)}"

    return state


# ── Conditional edge: route after intent classification ─────────────────────


def should_extract_details(state: MainAgentState) -> str:
    """After routing, only extract details for email intent. Scheduling handles its own."""
    if state["intent"] == "email":
        return "extract_details"
    return "execute_task"


# ── Build the LangGraph StateGraph ──────────────────────────────────────────


def _build_graph() -> StateGraph:
    graph = StateGraph(MainAgentState)

    # Register nodes
    graph.add_node("check_memory", check_memory)
    graph.add_node("route_to_agent", route_to_agent)
    graph.add_node("extract_details", extract_details)
    graph.add_node("get_employee_memory", get_employee_memory_for_task)
    graph.add_node("execute_task", execute_task)
    graph.add_node("save_memory", save_memory)

    # Entry point
    graph.set_entry_point("check_memory")

    # Linear edges
    graph.add_edge("check_memory", "route_to_agent")

    # Conditional edge: skip extract_details + get_employee_memory for general intent
    graph.add_conditional_edges(
        "route_to_agent",
        should_extract_details,
        {
            "extract_details": "extract_details",
            "execute_task": "execute_task",
        },
    )

    graph.add_edge("extract_details", "get_employee_memory")
    graph.add_edge("get_employee_memory", "execute_task")
    graph.add_edge("execute_task", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile()


# Compile once at import time
_graph = _build_graph()


# ── Public entry point ───────────────────────────────────────────────────────


def run_main_agent(user_input: str) -> dict:
    initial_state = MainAgentState(
        user_input=user_input,
        memory_context="",
        intent="",
        routing_result={},
        email_details={},
        execution_result={},
        memory_stored=False,
        employee_memory="",
        employee_id=None,
        employee_name=None,
        recipient_emp_ids=[],
        error=None,
    )

    final_state = _graph.invoke(initial_state)

    return {
        "user_input": final_state["user_input"],
        "memory_context": final_state["memory_context"],
        "intent": final_state["intent"],
        "routing_result": final_state["routing_result"],
        "execution_result": final_state["execution_result"],
        "employee_id": final_state["employee_id"],
        "employee_name": final_state["employee_name"],
        "memory_stored": final_state["memory_stored"],
        "error": final_state["error"],
    }
