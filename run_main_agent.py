from dotenv import load_dotenv
from src.main_agent import run_main_agent
from src.tools.reminder_service import start_reminder_service

load_dotenv()


def print_result(result: dict):
    print("\n" + "=" * 60)
    print("MAIN AGENT RESULT")
    print("=" * 60)

    print(f"\n[Intent] {result['intent'].upper()}")
    print(f"[Memory Stored] {'Yes' if result.get('memory_stored') else 'No'}")

    execution = result.get("execution_result", {})
    print(f"\n[Action] {execution.get('action_summary', 'N/A')}")

    if result["intent"] == "email":
        email_result = execution.get("email_result", {})
        if email_result:
            print(f"\n[Email Summary]")
            print(f"  Sent: {email_result.get('total_sent', 0)}")
            print(f"  Skipped: {email_result.get('total_skipped', 0)}")

            sent = email_result.get("sent", [])
            if sent:
                print(f"\n  [Sent Emails]")
                for s in sent:
                    status = "✓" if s.get("success") else "✗"
                    print(f"    {status} {s.get('name', 'N/A')} ({s.get('to', 'N/A')})")

            skipped = email_result.get("skipped", [])
            if skipped:
                print(f"\n  [Skipped - No Valid Email]")
                for s in skipped:
                    print(f"    - {s.get('name', 'N/A')} ({s.get('reason', 'N/A')})")

    if execution.get("subject"):
        print(f"\n[Generated Subject] {execution.get('subject')}")

    if result.get("error"):
        print(f"\n[Error] {result['error']}")

    print("=" * 60 + "\n")


def main():
    print("\n" + "=" * 60)
    print("     NOVAHR MAIN AGENT")
    print("     AI-Powered Task Router")
    print("=" * 60)

    start_reminder_service()

    while True:
        user_input = input("\nWhat would you like to do- ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        if not user_input:
            print("Please enter a command.")
            continue

        print("\nProcessing...")
        result = run_main_agent(user_input)
        print_result(result)


if __name__ == "__main__":
    main()
