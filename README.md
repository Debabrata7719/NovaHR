# NovaHR - AI-Powered HR Assistant

An intelligent HR assistant built with Python that uses LLM-powered routing to handle employee communication tasks. The system routes user requests to specialized agents, maintains conversation history per employee, and provides personalized interactions based on task history.

## Table of Contents

- [Overview](#overview)
- [Problems Faced & Solutions](#problems-faced--solutions)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Components](#components)
- [Memory System](#memory-system)
- [Scheduling Agent](#scheduling-agent)
- [Reminder Service](#reminder-service)
- [Intent Classification](#intent-classification)
- [Adding New Agents](#adding-new-agents)
- [Configuration](#configuration)
- [Usage](#usage)
- [Database Schema](#database-schema)
- [Technology Stack](#technology-stack)
- [Future Enhancements](#future-enhancements)

---

## Overview

NovaHR is designed to help HR staff communicate with employees efficiently. It uses natural language understanding (via Groq's LLM) to:

1. **Route requests** - Classify user input into appropriate task types
2. **Extract details** - Parse required parameters using LLM
3. **Execute tasks** - Run the appropriate agent to complete the task
4. **Learn from interactions** - Store task history and conversation context per employee
5. **Provide context-aware responses** - Use memory to understand user intent

### Supported Capabilities

| Capability | Description |
|------------|-------------|
| **Email Agent** | Send emails to employees by name, department, role, or all |
| **Scheduling Agent** | Create calendar events, view scheduled events |
| **Reminder Service** | Automatic notifications before upcoming events |
| **Memory Queries** | View past activities, filter by date (today/yesterday) |

### Why This Architecture?

- **Agent-based**: Extensible design - add new capabilities by creating new agents
- **Memory-first**: Every interaction is stored per-employee for personalized future responses
- **LLM-powered routing**: Natural language understanding without hardcoded rules
- **Stateless pipeline**: Each request flows through the same stages
- **Context-aware**: Router and agents use conversation history for better decisions

---

## Problems Faced & Solutions

This section documents the challenges encountered during development and how they were solved.

### Problem 1: Time Parsing Issues (Decimal Time Format)

**Issue:** User enters time like "08.10 pm" but system interprets it as 02:40 PM.

**Example:**
```
User Input: "schedule a meeting today at 08.10 pm"
Expected: 08:10 PM (20:10)
Actual: 02:40 PM (14:40) ❌
```

**Root Cause:**
- The `dateparser` library misinterprets decimal time formats
- "08.10" is parsed as hours.minutes without proper AM/PM handling
- The LLM also wasn't extracting time correctly

**Solution Implemented:**

1. **Created `validate_and_fix_time()` in `calendar_tools.py`:**
   - Added regex patterns to detect decimal time formats
   - Converts "08.10 pm" → "20:10" before passing to dateparser
   - Handles multiple formats: "8.10pm", "09.35 pm", "1.13 am"

```python
def validate_and_fix_time(time_str: str) -> str:
    # Handle decimal format like "08.10 pm" → "20:10"
    decimal_match = re.match(r"^(\d{1,2})\.(\d{1,2})\s*(am|pm)?$", time_str)
    if decimal_match:
        hour = int(decimal_match.group(1))
        minute = int(decimal_match.group(2))
        period = decimal_match.group(3)
        
        if period == "pm" and hour < 12:
            hour += 12
        # ...
        return f"{hour:02d}:{minute:02d}"
```

2. **Updated LLM prompts with explicit examples:**
   - Added rules like "'08.10 pm' → time: '20:10' (8:10 PM in 24-hour)"
   - Created few-shot examples in the extraction prompt

3. **Added post-processing validation:**
   - After LLM extraction, time goes through `validate_and_fix_time()`
   - Then parsed with direct datetime instead of relying on dateparser

**Files Modified:** `src/tools/calendar_tools.py`, `src/main_agent/agents/scheduling/executor.py`

---

### Problem 2: Reminder Shows Wrong Time (Timezone Issue)

**Issue:** Reminder notifications display times in UTC instead of IST.

**Example:**
```
Google Calendar stores: 2026-04-08T16:00:00Z (9:30 PM IST)
Reminder displays: 04:00 PM ❌
```

**Root Cause:**
- Google Calendar API returns event times in UTC (ends with "Z")
- The reminder service parsed the time but displayed it without timezone conversion
- The system was treating UTC as local time

**Solution Implemented:**

1. **Fixed `parse_event_datetime()` in `reminder_service.py`:**
```python
def parse_event_datetime(date_time_str: str) -> Optional[datetime]:
    try:
        dt_utc = datetime.fromisoformat(date_time_str.replace("Z", "+00:00"))
        dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        return dt_ist
    except:
        return None
```

2. **Fixed time display in scheduling executor:**
```python
# Convert UTC from Google Calendar to IST
dt_utc = datetime.fromisoformat(actual_time.replace("Z", "+00:00"))
dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
formatted_time = dt_ist.strftime("%I:%M %p")
```

3. **Fixed time calculation in reminder check:**
```python
def get_time_until_event(event_start: datetime) -> float:
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    delta = event_start - now_ist
    return delta.total_seconds()
```

**Files Modified:** `src/tools/reminder_service.py`, `src/main_agent/agents/scheduling/executor.py`

---

### Problem 3: "do same" Creates Wrong Action (Ambiguous Input)

**Issue:** User says "do same for today" but system fetches existing events instead of creating new one.

**Example:**
```
User Input: "do same for today 1.13 am"
Expected: Create new event similar to previous one
Actual: "2 events on today: Untitled Event, Untitled Event" ❌
```

**Root Cause:**
- The `decide_action()` function classified input as "get_events" instead of "create_event"
- Phrases like "do same", "do again", "repeat" weren't handled
- Default fallback was "get_events" (safer option)

**Solution Implemented:**

1. **Added explicit rules to `decide_action()` prompt:**
```python
system_prompt = """
CRITICAL RULES - Use "create_event" for these patterns:
- "schedule a meeting", "book an event", "add to calendar"
- "do same", "do again", "repeat", "again", "same thing"
- Any request to CREATE, ADD, SCHEDULE, BOOK something

EXAMPLES:
- "schedule a meeting tomorrow" -> create_event
- "do same for today 1pm" -> create_event
- "book a call at 3pm" -> create_event
- "what's on my calendar today?" -> get_events
- "show me my events" -> get_events
- "do it again" -> create_event
"""
```

2. **Changed default fallback:**
   - From: `get_events` (safer)
   - To: `create_event` (more aggressive for scheduling context)

**Files Modified:** `src/main_agent/agents/scheduling/executor.py`

---

### Problem 4: Memory Not Used for Context-Aware Decisions

**Issue:** Memory was fetched but not passed to the LLM for better decisions.

**Root Cause:**
- `check_memory()` fetched memory from MongoDB
- But `route_to_agent()` only received `user_input`
- Router and agents couldn't see conversation history

**Solution Implemented:**

1. **Updated router to accept memory context:**
```python
# router.py
def route_task(user_input: str, memory_context: str = "") -> dict:
    if memory_context:
        prompt = ROUTING_PROMPT.format(
            user_input=user_input,
            memory_context=memory_context
        )
    # ...
```

2. **Main Agent passes memory to router:**
```python
# __init__.py
def route_to_agent(state: MainAgentState) -> MainAgentState:
    memory_context = state.get("memory_context", "")
    routing_result = route_task(state["user_input"], memory_context)
    # ...
```

3. **Passed memory to scheduling agent:**
```python
elif state["intent"] == "scheduling":
    execution_result = execute_scheduling_task(
        user_input=state["user_input"],
        employee_memory=employee_memory,
        memory_context=memory_context,  # NEW
    )
```

4. **Security: Only Main Agent writes to memory**
   - Router and agents only READ memory
   - Main Agent's `save_memory()` has exclusive write access

**Files Modified:** `src/main_agent/router.py`, `src/main_agent/__init__.py`, `src/main_agent/agents/scheduling/executor.py`

---

### Problem 5: Memory Queries Not Handled

**Issue:** Questions like "what did I do yesterday?" returned generic help message.

**Example:**
```
User Input: "what is your previous task you do ?"
Expected: List of past activities
Actual: "I'm here to help! Currently I can send emails..." ❌
```

**Root Cause:**
- No "memory" intent in classification
- Router classified as "general" (default)

**Solution Implemented:**

1. **Added "memory" to AVAILABLE_AGENTS:**
```python
AVAILABLE_AGENTS = ["email", "scheduling", "memory", "general"]
```

2. **Created memory intent handler:**
```python
elif state["intent"] == "memory":
    # Extract date filter (today/yesterday)
    if "today" in user_input_lower:
        date_filter = "today"
    elif "yesterday" in user_input_lower:
        date_filter = "yesterday"
    
    recent_tasks = get_recent_memories(limit=5, date_filter=date_filter)
    # Format and return response
```

3. **Added date filtering to memory retrieval:**
```python
def get_recent_memories(limit: int = 10, date_filter: str = None) -> list:
    if date_filter == "today":
        # Filter to today's tasks only
    elif date_filter == "yesterday":
        # Filter to yesterday's tasks only
```

**Files Modified:** `src/main_agent/router.py`, `src/main_agent/__init__.py`, `src/main_agent/memory.py`

---

### Problem 6: Previous Memory Display in CLI

**Issue:** Every chat showed previous memory context, cluttering output.

**Solution Implemented:**

Removed memory context display from CLI output:
```python
# run_main_agent.py - REMOVED this:
if result.get("memory_context") and "No previous" not in result["memory_context"]:
    print(f"\n[Recent Memory]")
    print(result["memory_context"])
```

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Main Agent Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│  1. check_memory()        → Load recent context from MongoDB│
│  2. route_to_agent()        → Classify intent via LLM        │
│  3. extract_details()       → Parse parameters via LLM       │
│  4. get_employee_memory()  → Load employee data from MySQL │
│  5. execute_task()          → Run appropriate agent         │
│  6. save_memory()           → Store results in MongoDB      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Response + Memory Updated
```

### Intent Classification Flow

```
User Input
    │
    ▼
┌──────────────────┐
│  Router (LLM)   │ ← Receives user_input + memory_context
└──────────────────┘
    │
    ├─→ "email"      → Email Agent
    ├─→ "scheduling" → Scheduling Agent
    ├─→ "memory"     → Memory Query Handler
    └─→ "general"    → Generic Help Response
```

### Data Flow

1. **User Input** → `run_main_agent.py` receives natural language request
2. **Memory Check** → Retrieves recent interactions for context
3. **Intent Classification** → LLM determines task type with memory context
4. **Detail Extraction** → LLM parses required parameters
5. **Task Execution** → Specialized agent performs the action
6. **Memory Save** → Results stored in MongoDB (Main Agent only)

---

## Project Structure

```
NovaHR/
├── run_main_agent.py           # CLI entry point + starts reminder service
│
├── .env                        # Environment configuration
├── credentials.json            # Google OAuth2 credentials (in .gitignore)
├── token.json                  # OAuth refresh token (in .gitignore)
│
├── src/
│   ├── __init__.py
│   │
│   ├── main_agent/             # Core orchestration
│   │   ├── __init__.py         # Main agent + LangGraph pipeline
│   │   ├── router.py           # LLM-based task classification
│   │   ├── memory.py           # MongoDB memory operations
│   │   │
│   │   └── agents/             # Specialized agents
│   │       ├── email/
│   │       │   └── executor.py # Email task execution
│   │       │
│   │       └── scheduling/
│   │           ├── __init__.py
│   │           └── executor.py # Scheduling agent + decision making
│   │
│   └── tools/                  # Utilities
│       ├── __init__.py
│       ├── llm_tools.py       # LLM subject generation
│       ├── mysql_tools.py     # Employee database CRUD
│       ├── email_tools.py     # SMTP email sending
│       ├── calendar_tools.py  # Google Calendar API
│       └── reminder_service.py # Background reminder checker
│
└── tests/
    └── test.py                 # Google Calendar test
```

---

## Components

### 1. Main Agent (`src/main_agent/__init__.py`)

The orchestrator that manages the complete pipeline. Uses a `TypedDict` state to pass data between pipeline stages.

**State Fields:**
```python
class MainAgentState(TypedDict):
    user_input: str              # Original user request
    memory_context: str          # Recent interactions context
    intent: str                  # Classified intent (email, scheduling, memory, general)
    routing_result: dict        # LLM routing decision
    email_details: dict         # Parsed email parameters
    execution_result: dict      # Agent execution output
    memory_stored: bool         # Memory save status
    employee_memory: str        # Employee context for prompts
    employee_id: str | None     # Identified employee ID
    employee_name: str | None   # Identified employee name
    recipient_emp_ids: list     # All recipient IDs (for batch)
    error: str | None           # Error message if any
```

**Pipeline Functions:**
| Function | Purpose |
|----------|---------|
| `check_memory()` | Loads recent interactions from MongoDB |
| `route_to_agent()` | Classifies intent using Groq LLM with memory context |
| `extract_details()` | Extracts task-specific parameters |
| `get_employee_memory_for_task()` | Loads employee data from MySQL + memory |
| `execute_task()` | Runs the appropriate agent (email/scheduling/memory/general) |
| `save_memory()` | Stores task results in MongoDB (Main Agent only) |

### 2. Router (`src/main_agent/router.py`)

Handles LLM-powered intent classification and detail extraction.

**Intent Classification:**
- Uses Groq's `llama-3.1-8b-instant` model
- Classifies into: `email`, `scheduling`, `memory`, `general`
- Accepts `memory_context` parameter for context-aware classification
- Uses few-shot examples to handle ambiguous inputs

**Supported Intents:**
| Intent | Description |
|--------|-------------|
| `email` | Send emails, email-related tasks |
| `scheduling` | Calendar events, create/view meetings |
| `memory` | Activity queries, history requests |
| `general` | Help, unrecognized tasks |

### 3. Email Agent (`src/main_agent/agents/email/executor.py`)

Executes email tasks with flexible recipient resolution.

**Supported Recipient Queries:**
| Query Type | Example |
|------------|---------|
| All | `all`, `everyone` |
| By ID | `id:emp_101` |
| By Department | `dept:Engineering`, `department:HR` |
| By Name | `name:John`, `John Smith` |
| By Role | `role:Manager` |

### 4. Scheduling Agent (`src/main_agent/agents/scheduling/executor.py`)

Handles all calendar-related tasks using LLM decision making.

**Actions:**
| Action | Description |
|--------|-------------|
| `create_event` | Create new calendar event |
| `get_events` | Fetch/view events for a date |

**Features:**
- LLM-powered action decision with memory context
- Natural language time parsing (tomorrow, next Monday, etc.)
- Decimal time format handling (08.10 pm → 20:10)
- Google Calendar API integration
- Returns actual event time from Google Calendar (IST converted)

### 5. Reminder Service (`src/tools/reminder_service.py`)

Background service that notifies before upcoming events.

**Features:**
- Background thread checking every 60 seconds
- 10-minute configurable reminder window
- In-memory deduplication (prevents duplicate notifications)
- UTC to IST timezone conversion
- Console notifications (extensible)

**Configuration:**
```python
REMINDER_WINDOW_MINUTES = 10
CHECK_INTERVAL_SECONDS = 60
```

### 6. Memory System (`src/main_agent/memory.py`)

MongoDB-backed per-employee memory storage with date filtering.

**Key Functions:**
| Function | Purpose |
|----------|---------|
| `get_employee_memory(emp_id)` | Get or create employee document |
| `save_employee_task_entry()` | Add task to single employee's history |
| `get_recent_memories(limit, date_filter)` | Get recent activities with date filtering |
| `append_recent_message()` | Add message to conversation |

---

## Scheduling Agent

### Purpose
Handle all calendar-related tasks using natural language.

### Features

1. **LLM-Powered Decision Making**
   - Classifies input as `create_event` or `get_events`
   - Uses memory context for context-aware decisions
   - Handles ambiguous phrases like "do same", "again"

2. **Natural Language Time Parsing**
   ```python
   # These all work:
   "schedule meeting tomorrow at 3pm"     → 2026-04-10 15:00
   "book call for next Monday 9am"        → 2026-04-13 09:00
   "add reminder for today 08.10 pm"     → 2026-04-09 20:10
   "schedule for 1.13 pm"                 → 2026-04-09 13:13
   ```

3. **Time Format Handling**
   The system handles multiple time input formats:
   | Input | Parsed |
   |-------|--------|
   | `08.10 pm` | 20:10 |
   | `8.10pm` | 20:10 |
   | `9am` | 09:00 |
   | `2:30pm` | 14:30 |
   | `1.13 am` | 01:13 |
   | `1.13 pm` | 13:13 |

4. **Google Calendar Integration**
   - OAuth2 authentication with credentials.json
   - Token storage in token.json
   - Proper timezone handling (IST)

### Example Usage

```
You: schedule a meeting tomorrow at 3pm
Assistant: Created event 'Meeting' for tomorrow at 03:00 PM

You: do same for today 1.13 pm
Assistant: Created event 'Untitled Event' for today at 01:13 PM

You: show my calendar for today
Assistant: 2 events on today: Meeting at 3pm, Call at 5pm
```

---

## Reminder Service

### Purpose
Automatically notify the user before calendar events start.

### How It Works

1. **Background Thread**
   - Runs continuously in background
   - Checks every 60 seconds
   - Starts automatically when `run_main_agent.py` is executed

2. **Event Fetching**
   - Gets all events for current day from Google Calendar
   - Parses event times with UTC → IST conversion

3. **Reminder Logic**
   ```python
   def should_notify(time_left_seconds: float) -> bool:
       return 0 < time_left_seconds <= (REMINDER_WINDOW_MINUTES * 60)
   ```

4. **Duplicate Prevention**
   - Tracks notified event IDs in memory
   - Each event notified only once
   - Set clears on restart

### Sample Notification

```
==================================================
  REMINDER: Upcoming Event
==================================================
  Event: "Team Standup"
  Time: 09:00 AM
  Link: https://calendar.google.com/...
==================================================
```

---

## Intent Classification

### How It Works

The system uses LLM-based classification with these improvements:

1. **Few-shot Examples**
   ```
   - "schedule meeting" → create_event
   - "do same" → create_event  
   - "what's on calendar" → get_events
   ```

2. **Memory Context**
   - Router considers conversation history
   - Scheduling agent uses memory for context

3. **Confidence-based Fallbacks**
   - If unclear: scheduling → create_event (not get_events)
   - Memory queries default to showing recent activities

### Classification Logic

| User Input Pattern | Intent | Action |
|-------------------|--------|--------|
| "send email to John" | email | Send email |
| "schedule meeting tomorrow" | scheduling | create_event |
| "what's on my calendar?" | scheduling | get_events |
| "do same for today 1pm" | scheduling | create_event |
| "what did I do yesterday?" | memory | Show history |
| "show my activities" | memory | Show history |
| "help" | general | Help message |

---

## Adding New Agents

### Step 1: Create Agent Directory

```
src/main_agent/agents/
├── email/
│   └── executor.py
└── your_agent/
    └── executor.py
```

### Step 2: Implement Executor Function

```python
def execute_your_task(
    user_input: str,
    employee_memory: str = "",
    memory_context: str = "",
) -> dict:
    """
    Returns:
        {
            "success": bool,
            "action_summary": str,    # Short description for memory
            "details": {...}         # Agent-specific result details
        }
    """
    # Your implementation here
    pass
```

### Step 3: Register in Main Agent

Update `execute_task()` in `src/main_agent/__init__.py`:

```python
elif state["intent"] == "your_intent":
    execution_result = execute_your_task(
        user_input=state["user_input"],
        employee_memory=state.get("employee_memory", ""),
        memory_context=state.get("memory_context", ""),
    )
    state["execution_result"] = execution_result
```

### Step 4: Update Router

Add your intent to `AVAILABLE_AGENTS` in `router.py`:

```python
AVAILABLE_AGENTS = ["email", "scheduling", "memory", "general", "your_intent"]
```

### Step 5: Update System Prompt

Add your intent to `SYSTEM_PROMPT` in `router.py`:

```python
SYSTEM_PROMPT = """You are a task router for NovaHR...
1. "email" - Send emails...
2. "scheduling" - Calendar tasks...
3. "memory" - Activity queries...
4. "your_intent" - Description of your intent...
"""
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | MySQL host | `localhost` |
| `DB_USER` | MySQL username | `root` |
| `DB_PASSWORD` | MySQL password | `password123` |
| `DB_NAME` | Database name | `employee` |
| `GROQ_API_KEY` | Groq API key | `gsk_...` |
| `EMAIL_ADDRESS` | Gmail for sending | `your@gmail.com` |
| `EMAIL_APP_PASSWORD` | Gmail app password | `xxxx xxxx xxxx xxxx` |

### Google Calendar (OAuth2)

**Files (in .gitignore):**
- `credentials.json` - OAuth2 client secrets from Google Cloud Console
- `token.json` - Stored refresh token

**Scopes:**
```python
SCOPES = ["https://www.googleapis.com/auth/calendar"]
```

**Timezone:**
```python
TIMEZONE = ZoneInfo("Asia/Kolkata")
```

### MongoDB

**Connection:** `mongodb://localhost:27017/`
**Database:** `Memory`
**Collection:** `Agent_memory`

### MySQL

**Database:** `employee`
**Tables:** `employees`

---

## Usage

### Running the Agent

```bash
python run_main_agent.py
```

This starts:
1. Main Agent CLI
2. Reminder Service (background thread)

### Example Interactions

```
You: send email to John asking about project status
Assistant: Email sent to John (john@company.com)

You: schedule a meeting tomorrow at 3pm
Assistant: Created event 'Meeting' for tomorrow at 03:00 PM

You: do same for today 1.13 pm
Assistant: Created event 'Untitled Event' for today at 01:13 PM

You: show my calendar for today
Assistant: 2 events on today: Meeting at 3pm, Call at 5pm

You: what did I do yesterday?
Assistant: Here are your recent activities:
1. [2026-04-08] Created event for today at 09:30 PM (via scheduling_agent)

You: what is your previous task you do ?
Assistant: Here are your recent activities:
1. [2026-04-08] Created event 'Untitled Event' for today at 09:30 PM (via scheduling_agent)
```

### Running Tests

```bash
# Test Google Calendar
python tests/test.py

# Run main agent
python run_main_agent.py
```

---

## Database Schema

### MySQL - `employees` Table

| Column | Type | Description |
|--------|------|-------------|
| employee_id | VARCHAR(50) | Primary key (e.g., emp_101) |
| name | VARCHAR(100) | Employee full name |
| email | VARCHAR(100) | Email address |
| department | VARCHAR(50) | Department name |
| role | VARCHAR(50) | Job role |
| created_at | TIMESTAMP | Record creation time |

### MongoDB - `Agent_memory` Collection

```json
{
    "employee_id": "emp_101",
    "name": "Rahul Sharma",
    "task_history": [
        {
            "intent": "scheduling",
            "agent": "scheduling_agent",
            "input": "schedule meeting tomorrow at 3pm",
            "output": "Created event 'Meeting' for tomorrow at 03:00 PM",
            "details": {
                "title": "Meeting",
                "date": "2026-04-10",
                "time": "03:00 PM"
            },
            "status": "success",
            "timestamp": "2026-04-09T16:34:00"
        }
    ],
    "recent_messages": [
        {"role": "user", "content": "schedule meeting tomorrow at 3pm"},
        {"role": "assistant", "content": "Created event 'Meeting'..."}
    ]
}
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.x |
| AI/LLM | Groq API (Llama 3.1 8B Instant) |
| Agent Framework | LangGraph |
| Employee Database | MySQL |
| Memory Store | MongoDB |
| Email | SMTP (Gmail) |
| Calendar | Google Calendar API (OAuth2) |
| Configuration | python-dotenv |

---

## Future Enhancements

- [ ] Add structured output with Pydantic for intent classification
- [ ] Human-in-the-loop for ambiguous requests
- [ ] Preference learning from task history
- [ ] Email template customization per employee
- [ ] Response retry logic for failed tasks
- [ ] Rate limiting for email sending
- [ ] Reminder via email/WhatsApp
- [ ] Add more agents (reporting, analytics, etc.)

---

## Known Issues/Limitations

- Decimal time formats work but prefer "1:13 am" over "1.13 am"
- Reminder only fires when event is within 10-minute window
- Memory queries limited to last 5 activities
- Timezone hardcoded to IST (Asia/Kolkata)
- Reminder notifications clear on restart (in-memory storage)

---

## Security Notes

- `credentials.json` and `token.json` are in `.gitignore`
- `.env` file contains secrets - keep secure
- Only Main Agent has write access to memory database
- Router and agents only read from memory
