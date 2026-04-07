from src.tools.mysql_tools import (
    get_employees_by_id,
    get_employees_by_department,
    get_employees_by_name,
    get_employees_by_role,
    get_employees_by_email,
    get_all_employees,
    get_all_departments,
)
from src.tools.email_tools import send_bulk_emails
from src.tools.llm_tools import generate_subject


def execute_email_task(
    recipients_query: str,
    email_content: str,
    subject_hint: str | None = None,
    employee_memory: str = "",
) -> dict:
    recipients = []
    query_type = "all"

    if recipients_query:
        query_lower = recipients_query.lower().strip()

        if query_lower == "all":
            recipients = get_all_employees()
            query_type = "all"

        elif query_lower.startswith("id:"):
            query_type = "id"
            query = query_lower[3:].strip()
            recipients = get_employees_by_id(query)

        elif query_lower.startswith("dept:") or query_lower.startswith("department:"):
            query_type = "department"
            query = query_lower.replace("department:", "").replace("dept:", "").strip()
            recipients = get_employees_by_department(query)

        elif query_lower.startswith("name:"):
            query_type = "name"
            query = query_lower[5:].strip()
            recipients = get_employees_by_name(query)

        else:
            query_type = "name"
            query_words = (
                query_lower.replace("department", "")
                .replace("role", "")
                .replace("employee", "")
                .strip()
            )

            id_recipients = get_employees_by_id(recipients_query)
            if id_recipients:
                query_type = "id"
                recipients = id_recipients
            else:
                id_recipients = get_employees_by_id(query_words)
                if id_recipients:
                    query_type = "id"
                    recipients = id_recipients
                else:
                    email_recipients = get_employees_by_email(recipients_query)
                    if email_recipients:
                        query_type = "email"
                        recipients = email_recipients
                    else:
                        departments = get_all_departments()
                        for dept in departments:
                            if (
                                query_lower == dept.lower()
                                or query_words == dept.lower()
                            ):
                                query_type = "department"
                                recipients = get_employees_by_department(dept)
                                break

                        if query_type == "name":
                            from src.tools.mysql_tools import get_all_roles

                            roles = get_all_roles()
                            for role in roles:
                                if (
                                    query_lower == role.lower()
                                    or query_words == role.lower()
                                ):
                                    query_type = "role"
                                    recipients = get_employees_by_role(role)
                                    break

                            if query_type == "name":
                                recipients = get_employees_by_name(recipients_query)
    else:
        recipients = get_all_employees()

    recipient_names = [r.get("name") for r in recipients if r.get("name")]
    recipient_name = recipient_names[0] if recipient_names else None

    if subject_hint:
        subject = generate_subject(subject_hint, recipient_name, employee_memory)
    else:
        subject = generate_subject(email_content, recipient_name, employee_memory)

    email_result = send_bulk_emails(recipients, subject, email_content)

    action_summary = f"Sent email to {email_result['total_sent']} recipients"
    if email_result["total_skipped"] > 0:
        action_summary += (
            f" (skipped {email_result['total_skipped']} without valid email)"
        )

    if recipients_query:
        action_summary += f" matching '{recipients_query}'"

    return {
        "success": email_result["total_sent"] > 0,
        "recipients_found": len(recipients),
        "query_type": query_type,
        "recipients_info": [
            {
                "employee_id": r.get("employee_id"),
                "email": r.get("email"),
                "name": r.get("name"),
            }
            for r in recipients
        ],
        "subject": subject,
        "email_result": email_result,
        "action_summary": action_summary,
    }
