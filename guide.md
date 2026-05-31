# Implementation Guide

## 1. Lab Context

TravelBuddy wants a lightweight travel assistant that can use tools instead of relying only on free-form model responses. The assistant should check flight options, estimate whether the budget still works, and look for hotels that fit the remaining nightly budget.

This lab uses a prebuilt agent pattern with `create_agent` rather than a custom multi-node workflow. The emphasis is on tool design, prompting, and grounded answers.

## 2. Requirements

Your implementation must:

- use `create_agent`
- define exactly three tools:
  - `search_flights`
  - `calculate_budget`
  - `search_hotels`
- answer in Vietnamese
- ask for clarification when key trip information is missing
- refuse unsafe or illegal requests
- use tool outputs as the source of truth for prices and recommendations

## 3. Expected Outcome

By the end of the lab, you should have a working agent that can:

- receive a natural-language travel request
- call the right tools in the right order
- produce a concise final recommendation
- handle normal, ambiguous, unsafe, and budget-constrained requests

## 4. Files You Will Work With

- `src/agent/graph.py`: main lab scaffold
- `src/utils/data_store.py`: mock flight and hotel search helpers
- `src/core/llm.py`: model helpers and optional LLM-judge support
- `src/core/schemas.py`: minimal result schema
- `data/flights.json`
- `data/hotels.json`
- `data/graded_cases.json`
- `grade/scoring.py`

## 5. Recommended Build Order

### Step 1: Build the system prompt

Implement `build_system_prompt(...)`.

The prompt should instruct the agent to:

- ask for missing trip details before using tools
- refuse unsafe or illegal requests
- use the tools in this order when information is available:
  1. `search_flights`
  2. `calculate_budget`
  3. `search_hotels`
- avoid inventing prices or availability
- return a short final answer in Vietnamese

### Step 2: Define the tools

Implement `build_tools(store)`.

Each tool should have:

- a clear name
- a useful docstring
- explicit arguments
- compact output that the model can reuse in the final answer

Recommended behavior:

- `search_flights`: returns matching flights for route, date, and traveler count
- `calculate_budget`: returns remaining budget after flight and local transport
- `search_hotels`: returns hotels that fit the nightly budget and preferences

### Step 3: Build the agent

Implement `build_agent(...)`.

You should:

1. create `TravelDataStore`
2. build the chat model
3. build the tools
4. call `create_agent(...)`

### Step 4: Run the agent

Implement `run_agent(...)`.

You should:

1. build the agent
2. invoke it with one user message
3. extract the final AI answer
4. extract a lightweight tool-call trace
5. return `AgentResult`

## 6. Tool-Calling Expectations

For standard travel requests, the expected tool order is:

1. `search_flights`
2. `calculate_budget`
3. `search_hotels`

For clarification and guardrail cases, the agent may respond without using tools.

## 7. Running the Lab

Setup:

```bash
cd labs
uv sync --extra dev
```

Grade your implementation:

```bash
uv run python grade/scoring.py --module agent.graph --provider google
```

Run with the optional LLM judge:

```bash
uv run python grade/scoring.py --module agent.graph --provider google --judge-provider google
```

## 8. Submission Standard

A strong submission should:

- use the required tools correctly
- keep tool schemas readable and specific
- produce grounded recommendations
- handle missing information clearly
- refuse unsafe requests cleanly
- generate concise, useful Vietnamese answers
