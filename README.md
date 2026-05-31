# TravelBuddy Lab: Tool-Calling Agent with `create_agent`

This lab introduces a practical pattern for building an LLM application that can reason over tool outputs and produce a grounded final response. You will implement a travel assistant for TravelBuddy that can search flights, estimate budget feasibility, and suggest hotels based on the remaining budget.

## Prerequisite Knowledge

Before starting this lab, you should be comfortable with:

- basic Python functions and modules
- reading JSON data
- environment setup with `uv`
- the idea of LLM tools / function calling
- prompt basics for system and user instructions

## Learning Outcomes

After completing this lab, you should be able to:

- build a prebuilt tool-calling agent with `create_agent`
- design clear tool schemas and tool descriptions
- write a system prompt that controls tool usage and answer style
- keep the final answer grounded in tool outputs
- evaluate agent quality with answer-based grading

## Lab Deliverable

Complete [src/agent/graph.py](/Users/duongnh59.al1/Documents/Project/Vin20K/Cohort2/Day-4-Lab/labs/src/agent/graph.py) so that the agent:

- calls the correct tools when information is available
- asks for clarification when key trip details are missing
- refuses unsafe or illegal requests
- returns a concise final answer in Vietnamese

## Project Layout

- `task.txt`: assignment brief
- `guide.md`: implementation guide
- `rubric.md`: grading rubric
- `src/agent/graph.py`: lab scaffold
- `src/core/`: model helpers and result schema
- `src/utils/`: dataset helpers
- `grade/scoring.py`: grading script
- `data/`: datasets and grading cases

## Setup

```bash
cd labs
uv sync --extra dev
```

## Run the Grader

```bash
uv run python grade/scoring.py --module agent.graph --provider google
```

## Optional LLM Judge

The grader also supports an additional LLM-based quality pass for the final answer:

```bash
uv run python grade/scoring.py --module agent.graph --provider google --judge-provider google
```
