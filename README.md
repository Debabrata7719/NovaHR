# NovaHR - AI-Powered HR Assistant

An intelligent HR assistant built with Python that uses LLM-powered routing to handle employee communication tasks. The system routes user requests to specialized agents (currently email), maintains conversation history per employee, and provides personalized interactions based on task history.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Components](#components)
- [Memory System](#memory-system)
- [Adding New Agents](#adding-new-agents)
- [Configuration](#configuration)
- [Usage](#usage)
- [Database Schema](#database-schema)

---

## Overview

NovaHR is designed to help HR staff communicate with employees efficiently. It uses natural language understanding (via Groq's LLM) to:

1. **Route requests** - Classify user input into appropriate task types (email, general queries)
2. **Extract details** - Parse required parameters (recipients, subject, content)
3. **Execute tasks** - Run the appropriate agent to complete the task
4. **Learn from interactions** - Store task history and conversation context per employee

### Why This Architecture?

- **Agent-based**: Extensible design - add new capabilities by creating new agents
- **Memory-first**: Every interaction is stored per-employee for personalized future responses
- **LLM-powered routing**: Natural language understanding without hardcoded rules
- **Stateless pipeline**: Each request flows through the same stages (check memory → route → extract → execute → save)

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Main Agent Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│  1. check_memory()     → Load recent context from MongoDB   │
│  2. route_to_agent()    → Classify intent via LLM           │
│  3. extract_details()   → Parse parameters via LLM           │
│  4. get_employee_memory_for_task() → Load employee data     │
│  5. execute_task()      → Run appropriate agent              │
│  6. save_memory()       → Store results in MongoDB          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Response + Memory Updated
```

### Data Flow

1. **User Input** → `run_main_agent.py` receives natural language request
2. **Memory Check** → Retrieves recent interactions for context
3. **Intent Classification** → LLM determines task type (email, general, etc.)
4. **Detail Extraction** → LLM parses required parameters
5. **Task Execution** → Specialized agent performs the action
6. **Memory Save** → Results stored in MongoDB for future reference

---

## Project Structure

```
NovaHR/
├── run_main_agent.py           # CLI entry point
│
├── src/
│   ├── __init__.py
│   │
│   ├── main_agent/             # Core orchestration
│   │   ├── __init__.py         # Main agent + state machine
│   │   ├── router.py           # LLM-based task classification
│   │   ├── memory.py           # MongoDB memory operations
│   │   │
│   │   └── agents/             # Specialized agents
│   │       └── email/
│   │           └── executor.py  # Email task execution
│   │
│   └── tools/                  # Utilities
│       ├── __init__.py
│       ├── llm_tools.py        # LLM subject generation
│       ├── mysql_tools.py      # Employee database CRUD
│       └── email_tools.py      # SMTP email sending
│
└── tests/
    ├── test.py                 # Basic DB connectivity test
    └── test_memory.py          # Memory system tests
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
    intent: str                  # Classified intent (email, general)
    routing_result: dict        # LLM routing decision
    email_details: dict         # Parsed email parameters
    execution_result: dict      # Agent execution output
    memory_stored: bool         # Memory save status
    employee_memory: str        # Employee context for prompts
    employee_id: str | None     # Identified employee ID
    employee_name: str | None  # Identified employee name
    recipient_emp_ids: list     # All recipient IDs (for batch)
    error: str | None           # Error message if any
```

**Pipeline Functions:**
| Function | Purpose |
|----------|---------|
| `check_memory()` | Loads recent interactions from MongoDB |
| `route_to_agent()` | Classifies intent using Groq LLM |
| `extract_details()` | Extracts task-specific parameters |
| `get_employee_memory_for_task()` | Loads employee data from MySQL + memory |
| `execute_task()` | Runs the appropriate agent |
| `save_memory()` | Stores task results and messages |

### 2. Router (`src/main_agent/router.py`)

Handles LLM-powered intent classification and detail extraction.

**Intent Classification:**
- Uses Groq's `llama-3.1-8b-instant` model
- Classifies into: `email`, `general`
- System prompt instructs conservative classification

**Detail Extraction:**
- For email intents: extracts `recipients`, `subject_hint`, `content_hint`
- Returns JSON for easy parsing

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
| By Email | Direct email address |

**Execution Flow:**
1. Resolve recipients using MySQL queries
2. Generate subject line using LLM (with employee preferences)
3. Send bulk emails via SMTP
4. Return execution result with details

### 4. Memory System (`src/main_agent/memory.py`)

MongoDB-backed per-employee memory storage.

### 5. Tools (`src/tools/`)

| File | Purpose |
|------|---------|
| `mysql_tools.py` | Employee CRUD operations |
| `email_tools.py` | SMTP email sending |
| `llm_tools.py` | Subject line generation |

---

## Memory System

### Design Goals

1. **Per-employee storage** - Each employee has their own memory document
2. **Task history** - Complete record of all interactions
3. **Conversation continuity** - Rolling window of recent messages
4. **Personalization** - Store preferences for tailored communication

### Document Structure

```json
{
    "employee_id": "emp_101",
    "name": "Rahul Sharma",
    "preferences": {
        "communication_style": "formal",
        "tone": "polite"
    },
    "task_history": [
        {
            "intent": "email",
            "agent": "email_agent",
            "input": "send email to AI team",
            "output": "Email sent successfully",
            "details": {
                "recipients": [
                    {"employee_id": "emp_101", "email": "ai_team@gmail.com"}
                ],
                "subject": "Meeting Request",
                "total_sent": 1,
                "total_skipped": 0
            },
            "status": "success",
            "timestamp": "2026-04-07T16:34:00"
        }
    ],
    "recent_messages": [
        {"role": "user", "content": "send email", "timestamp": "..."},
        {"role": "assistant", "content": "Email sent successfully", "timestamp": "..."}
    ]
}
```

### Why This Structure?

| Field | Purpose | Why |
|-------|---------|-----|
| `employee_id` | Primary key | Links to MySQL employee records |
| `name` | Display | Human-readable identification |
| `preferences` | Personalization | Customize communication style |
| `task_history` | Audit trail | Complete history of all interactions |
| `recent_messages` | Context | Rolling window for conversation continuity |

### Key Functions

| Function | Purpose |
|----------|---------|
| `get_employee_memory(emp_id)` | Get or create employee document |
| `save_employee_task_entry()` | Add task to single employee's history |
| `save_batch_task_entry()` | Add task to multiple employees (bulk emails) |
| `append_recent_message()` | Add message to conversation (max 20, FIFO) |
| `get_employee_memory_prompt()` | Generate context string for LLM prompts |
| `update_employee_info()` | Update name, preferences, etc. |

### Memory Saving Logic

In `save_memory()`, the system:

1. **For batch operations (bulk emails):**
   - Creates task entry for EACH recipient
   - All entries share same `input`, `output`, `timestamp`
   - `details.recipients` array lists all batch members

2. **For single operations:**
   - Creates one task entry for the target employee

3. **Message storage:**
   - User message stored with `role: user`
   - Assistant response stored with `role: assistant`
   - Maximum 20 messages per employee (oldest removed first)

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
    parameters: dict,           # Extracted from user input
    employee_memory: str = "",  # For context-aware responses
) -> dict:
    """
    Returns:
        {
            "success": bool,
            "action_summary": str,    # Short description for memory
            "result_data": {...}       # Agent-specific result details
        }
    """
    # Your implementation here
    pass
```

### Step 3: Register in Main Agent

Update `execute_task()` in `src/main_agent/__init__.py`:

```python
def execute_task(state: MainAgentState) -> MainAgentState:
    if state["intent"] == "your_intent":
        from src.main_agent.agents.your_agent.executor import execute_your_task
        
        execution_result = execute_your_task(
            parameters=state.get("your_details", {}),
            employee_memory=state.get("employee_memory", ""),
        )
        state["execution_result"] = execution_result
    
    # ... existing code
```

### Step 4: Update Router

Add your intent to `AVAILABLE_AGENTS` in `router.py`:

```python
AVAILABLE_AGENTS = ["email", "general", "your_intent"]
```

### Step 5: Update Extract Details

Add detail extraction for your intent in `extract_details()`:

```python
def extract_details(state: MainAgentState) -> MainAgentState:
    if state["intent"] == "your_intent":
        try:
            details = parse_your_details(state["user_input"])
            state["your_details"] = details
        except Exception as e:
            state["your_details"] = {"error": str(e)}
    return state
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

### Example Interactions

```
You: send email to John asking about project status
Assistant: Email sent to John (john@company.com)

You: send announcement to Engineering department
Assistant: Email sent to 15 employees in Engineering department

You: what was the last email sent?
Assistant: The last email was sent to John asking about project status
```

### Running Tests

```bash
# Memory system tests
python -m pytest tests/test_memory.py -v

# Basic DB connectivity
python tests/test.py
```

---

## Database Schema

### MySQL - `employee_data` Table

| Column | Type | Description |
|--------|------|-------------|
| employee_id | VARCHAR(50) | Primary key (e.g., emp_101) |
| name | VARCHAR(100) | Employee full name |
| email | VARCHAR(100) | Email address |
| department | VARCHAR(50) | Department name |
| role | VARCHAR(50) | Job role |
| created_at | TIMESTAMP | Record creation time |

### MongoDB - `Agent_memory` Collection

Each document follows the structure defined in [Document Structure](#document-structure).

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.x |
| AI/LLM | Groq API (Llama 3.1 8B Instant) |
| Agent Framework | LangGraph (optional, in requirements) |
| Employee Database | MySQL |
| Memory Store | MongoDB |
| Email | SMTP (Gmail) |
| Configuration | python-dotenv |

---

## Future Enhancements

- [ ] Add more agents (scheduling, reporting, etc.)
- [ ] Preference learning from task history
- [ ] Batch operation history aggregation
- [ ] Email template customization per employee
- [ ] Response retry logic for failed tasks
- [ ] Rate limiting for email sending
