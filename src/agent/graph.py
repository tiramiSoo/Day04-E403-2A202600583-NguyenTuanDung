from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from core.llm import build_chat_model, normalize_content
from core.schemas import AgentResult, ToolCallRecord
from utils.data_store import TravelDataStore

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data"


def build_system_prompt(today: str | None = None) -> str:
    """
    Student TODO:
    - Write a system prompt for a TravelBuddy agent.
    - Keep the lab focused on prompt engineering and tool schema design.
    - Require this tool order when enough info exists:
      1. `search_flights`
      2. `calculate_budget`
      3. `search_hotels`
    - Tell the agent to:
      - refuse illegal or unsafe travel requests
      - ask a short clarification question when destination/date/budget/nights are missing
      - use only tool outputs for prices and recommendations
      - produce one final user-facing answer in Vietnamese
    - Include `today` so the model can resolve phrases like `cuoi tuan nay`.
    """
    raise NotImplementedError("Complete build_system_prompt() in src/agent/graph.py")


def build_tools(store: TravelDataStore):
    """
    Student TODO:
    - Define exactly three tools with strong names, docstrings, and argument schemas:
      - `search_flights`
      - `calculate_budget`
      - `search_hotels`
    - Return them as a list for `create_agent(...)`.
    - Each tool should return compact JSON/text that the agent can reuse in its final answer.
    """

    @tool
    def search_flights(origin: str, destination: str, departure_date: str, travelers: int = 1) -> str:
        """Search flights for a route and departure date."""
        raise NotImplementedError

    @tool
    def calculate_budget(
        total_budget: int,
        nights: int,
        cheapest_flight_total: int,
        destination: str,
        travelers: int = 1,
    ) -> str:
        """Calculate the remaining travel budget after flight and local transport costs."""
        raise NotImplementedError

    @tool
    def search_hotels(city: str, max_price_per_night: int, preferences: list[str] | None = None) -> str:
        """Search hotels that fit the remaining nightly budget and user preferences."""
        raise NotImplementedError

    return [search_flights, calculate_budget, search_hotels]


def build_agent(
    data_dir: Path | None = None,
    *,
    provider: str = "google",
    model_name: str | None = None,
    today: str | None = None,
):
    """
    Student TODO:
    - Create `TravelDataStore`.
    - Build the chat model with `build_chat_model(...)`.
    - Build tools with `build_tools(store)`.
    - Return `create_agent(model=..., tools=..., system_prompt=...)`.
    """
    raise NotImplementedError("Complete build_agent() in src/agent/graph.py")


def run_agent(
    query: str,
    *,
    provider: str = "google",
    model_name: str | None = None,
    data_dir: Path | None = None,
    today: str | None = None,
) -> AgentResult:
    """
    Student TODO:
    - Build the agent with `build_agent(...)`.
    - Invoke it with one user message.
    - Extract:
      - the final AI answer
      - the tool call trace from `messages`
    - Return an `AgentResult`.
    """
    raise NotImplementedError("Complete run_agent() in src/agent/graph.py")


def extract_final_answer(messages) -> str:
    """Optional helper: return the last AI message text."""
    raise NotImplementedError


def extract_tool_calls(messages) -> list[ToolCallRecord]:
    """Optional helper: convert tool messages into a simple grading trace."""
    raise NotImplementedError
