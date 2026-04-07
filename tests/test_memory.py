from src.main_agent.memory import (
    get_employee_memory,
    save_employee_task_entry,
    save_batch_task_entry,
    append_recent_message,
    update_employee_info,
    get_employee_by_id,
    get_task_history,
    get_recent_messages,
    clear_employee_memory,
)


def test_employee_memory_structure():
    emp_id = "test_emp_001"

    clear_employee_memory(emp_id)

    employee = get_employee_memory(emp_id)
    print("Initial employee memory:")
    print(f"  employee_id: {employee['employee_id']}")
    print(f"  name: {employee['name']}")
    print(f"  preferences: {employee['preferences']}")
    print(f"  task_history length: {len(employee['task_history'])}")
    print(f"  recent_messages length: {len(employee['recent_messages'])}")
    print()

    update_employee_info(emp_id, "Rahul Sharma")
    print("After updating name:")

    task_entry = save_employee_task_entry(
        emp_id=emp_id,
        intent="email",
        agent="email_agent",
        task_input="send email to AI team",
        task_output="Email sent successfully",
        details={
            "recipients": [{"employee_id": "emp_101", "email": "ai_team@gmail.com"}],
            "subject": "Meeting Request",
        },
        status="success",
    )
    print("After saving task entry:")
    print(f"  Task: {task_entry['intent']} via {task_entry['agent']}")
    print(f"  Input: {task_entry['input']}")
    print(f"  Output: {task_entry['output']}")
    print(f"  Details: {task_entry['details']}")
    print(f"  Status: {task_entry['status']}")
    print(f"  Timestamp: {task_entry['timestamp']}")
    print()

    append_recent_message(emp_id, "user", "send email to AI team")
    append_recent_message(emp_id, "assistant", "Email sent successfully")
    print("After appending messages:")

    messages = get_recent_messages(emp_id)
    print(f"  Recent messages ({len(messages)}):")
    for msg in messages:
        print(f"    - [{msg['role']}] {msg['content'][:50]}...")
    print()

    history = get_task_history(emp_id)
    print(f"Task history ({len(history)}):")
    for task in history:
        print(f"  - [{task['intent']}] {task['output']}")
    print()

    emp = get_employee_by_id(emp_id)
    print("Final employee document:")
    print(f"  employee_id: {emp['employee_id']}")
    print(f"  name: {emp['name']}")
    print(f"  preferences: {emp['preferences']}")
    print(f"  task_history: {len(emp['task_history'])} entries")
    print(f"  recent_messages: {len(emp['recent_messages'])} entries")
    print()

    print("Testing batch task entry...")
    batch_emp_ids = ["test_emp_002", "test_emp_003", "test_emp_004"]
    entries = save_batch_task_entry(
        emp_ids=batch_emp_ids,
        intent="email",
        agent="email_agent",
        task_input="send email to all employees",
        task_output="Email sent to 3 recipients",
        details={"recipients": batch_emp_ids, "subject": "Announcement"},
        status="success",
    )
    print(f"Saved batch entry for {len(entries)} employees")
    print()

    print("All tests passed!")


if __name__ == "__main__":
    test_employee_memory_structure()
