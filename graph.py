from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from simple_solution.utils.data_store import OrderDataStore
from src.core.llm import build_chat_model, normalize_content
from src.core.schemas import AgentResult, OrderLineInput, ToolCallRecord

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "artifacts" / "orders"


def build_system_prompt(today: str | None = None) -> str:
    current_day = today or "2026-06-01"
    return f"""You are a strict order assistant. Today is {current_day}.

## STEP 0 — GUARDRAILS (check before everything else)
If the request contains ANY of the following instructions, REFUSE the ENTIRE request immediately. Do NOT call any tools. Do NOT process even the "valid parts" of such requests.
- Bypass or ignore stock limits
- Skip catalog or pricing checks
- Apply unauthorized discounts or manually set discount rates
- Create fake invoices or orders outside the system

## STEP 1 — PRE-FLIGHT CHECK (before calling any tool)
An order requires EXACTLY these 4 fields. Check each one:
  [1] Customer full name    — must be stated explicitly
  [2] Phone number          — must be stated explicitly (digits)
  [3] Email address         — must be stated explicitly (contains @)
  [4] Shipping address      — must be stated explicitly

If ANY of the 4 is absent → reply asking for only the missing field(s). Do NOT call any tools.
Note: a phone number is NOT an email. An address is NOT an email. Check for @ symbol.

## STEP 2 — TOOL SEQUENCE (must follow this exact order, no exceptions)
1. list_products — call separately for each product name (multiple calls allowed, one per product)
2. get_product_details — ONE call with ALL product_ids at once → gives detail_token
3. get_discount — ONLY AFTER step 2 completes; pass customer EMAIL as `customer` → gives discount_rate and campaign_code
4. calculate_order_totals — use detail_token from step 2, discount_rate from step 3
   → If stock error in result: STOP immediately. Inform user. Do NOT call save_order.
5. save_order — pass ALL fields below as a JSON string

CRITICAL: get_discount must always come AFTER get_product_details. Never call get_discount before or during step 2.

## STEP 3 — save_order PAYLOAD (every field is required)
{{
  "customer_name": "<copy exactly from user message>",
  "customer_phone": "<copy exactly from user message>",
  "customer_email": "<copy exactly from user message>",
  "shipping_address": "<copy exactly from user message>",
  "items": [{{"product_id": "...", "quantity": N}}, ...],
  "detail_token": "<from get_product_details>",
  "discount_rate": <number, from get_discount>,
  "campaign_code": "<string, from get_discount, e.g. FLASH-10 or FLASH-20>",
  "customer_tier": "<from get_discount>",
  "notes": ""
}}
IMPORTANT: notes must always be empty string "" — do NOT add content to notes.

Answer in Vietnamese. Keep answers concise."""


def build_tools(store: OrderDataStore):
    @tool
    def list_products(search_text: str = "", extra: str = "", limit: int = 8) -> str:
        """Search the product catalog by name or keywords. Returns product_ids needed for get_product_details. Call get_product_details next with all found product_ids."""
        category = ""
        tags: list[str] = []
        text = (search_text or "").strip()
        if extra:
            for piece in extra.split(","):
                piece = piece.strip()
                if not piece:
                    continue
                if piece.lower().startswith("category="):
                    category = piece.split("=", 1)[1].strip()
                else:
                    tags.append(piece)
        payload = store.list_products(
            query=text or None,
            category=category or None,
            required_tags=tags,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def get_product_details(product_ids_text: str = "") -> str:
        """Get price, stock, and detail_token for products. Pass ALL product_ids at once as a JSON array. The returned detail_token is required for calculate_order_totals and save_order."""
        product_ids = _coerce_product_ids(product_ids_text)
        return json.dumps(store.get_product_details(product_ids), ensure_ascii=False)

    @tool
    def get_discount(customer: str = "") -> str:
        """Get discount_rate and campaign_code for a customer. Pass the customer EMAIL as the `customer` parameter. Returns discount_rate (0.1 or 0.2) and campaign_code (e.g. FLASH-10) — both must be used exactly in save_order."""
        customer_text = customer.strip()
        seed_hint = customer_text
        customer_tier = "standard"
        if customer_text:
            if "vip" in customer_text.lower():
                customer_tier = "vip"
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", customer_text)
            if email_match:
                seed_hint = email_match.group(0)
        return json.dumps(store.get_discount(seed_hint=seed_hint or "guest", customer_tier=customer_tier), ensure_ascii=False)

    @tool
    def calculate_order_totals(items_text: str = "", discount_rate: float = 0.0, detail_token: str = "") -> str:
        """Calculate subtotal, discount_amount, and final_total. items_text: JSON list of {product_id, quantity}. discount_rate: from get_discount. detail_token: from get_product_details."""
        items = _coerce_items(items_text)
        payload = store.calculate_order_totals(items=items, detail_token=detail_token, discount_rate=discount_rate)
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def save_order(order_payload: str = "") -> str:
        """Save the confirmed order. order_payload must be a JSON string with: customer_name, customer_phone, customer_email, shipping_address, items (list of {product_id, quantity}), detail_token (from get_product_details), discount_rate (from get_discount), campaign_code (from get_discount), customer_tier (from get_discount)."""
        payload = _coerce_object(order_payload)
        items = _coerce_items(payload.get("items", []))
        result = store.save_order(
            customer_name=str(payload.get("customer_name", "")),
            customer_phone=str(payload.get("customer_phone", "")),
            customer_email=str(payload.get("customer_email", "")),
            shipping_address=str(payload.get("shipping_address", "")),
            items=items,
            detail_token=str(payload.get("detail_token", "")),
            discount_rate=float(payload.get("discount_rate", 0.0)),
            campaign_code=str(payload.get("campaign_code", "")),
            customer_tier=str(payload.get("customer_tier", "standard")),
            notes=str(payload.get("notes", "")),
        )
        return json.dumps(result, ensure_ascii=False)

    return [list_products, get_product_details, get_discount, calculate_order_totals, save_order]


def build_agent(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    provider: str = "custom",
    model_name: str | None = None,
    today: str | None = None,
):
    store = OrderDataStore(data_dir or DEFAULT_DATA_DIR, output_dir or DEFAULT_OUTPUT_DIR, today=today)
    model = build_chat_model(provider=provider, model_name=model_name, temperature=0.0)
    return create_agent(
        model=model,
        tools=build_tools(store),
        system_prompt=build_system_prompt(today or store.today),
    )


def run_agent(
    query: str,
    *,
    provider: str = "custom",
    model_name: str | None = None,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    today: str | None = None,
) -> AgentResult:
    agent = build_agent(
        data_dir=data_dir,
        output_dir=output_dir,
        provider=provider,
        model_name=model_name,
        today=today,
    )
    response = agent.invoke({"messages": [{"role": "user", "content": query}]})
    messages = response["messages"] if isinstance(response, dict) else response
    tool_calls = extract_tool_calls(messages)
    saved_order, saved_order_path = extract_saved_order(tool_calls)
    return AgentResult(
        query=query,
        final_answer=extract_final_answer(messages),
        tool_calls=tool_calls,
        provider=provider,
        model_name=model_name,
        saved_order=saved_order,
        saved_order_path=saved_order_path,
    )


def extract_final_answer(messages) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = normalize_content(message.content)
            if text:
                return text
    return ""


def extract_tool_calls(messages) -> list[ToolCallRecord]:
    pending: dict[str, dict[str, Any]] = {}
    records: list[ToolCallRecord] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in getattr(message, "tool_calls", []) or []:
                pending[tool_call["id"]] = {
                    "name": tool_call["name"],
                    "args": tool_call.get("args", {}) or {},
                }
        elif isinstance(message, ToolMessage):
            metadata = pending.pop(message.tool_call_id, {})
            records.append(
                ToolCallRecord(
                    name=str(getattr(message, "name", None) or metadata.get("name", "")),
                    args=metadata.get("args", {}),
                    output=normalize_content(message.content),
                )
            )

    for metadata in pending.values():
        records.append(ToolCallRecord(name=metadata["name"], args=metadata["args"], output=""))
    return records


def extract_saved_order(tool_calls: list[ToolCallRecord]) -> tuple[dict | None, str | None]:
    for record in reversed(tool_calls):
        if record.name != "save_order" or not record.output:
            continue
        try:
            payload = json.loads(record.output)
        except json.JSONDecodeError:
            continue
        if payload.get("status") != "saved":
            return None, None
        return payload.get("saved_order"), payload.get("path")
    return None, None


def _coerce_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}
    return {}


def _coerce_product_ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except Exception:
                continue
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in re.split(r"[,\s]+", text) if item.strip()]
    return []


def _coerce_items(raw: Any) -> list[OrderLineInput]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        items = []
        if text:
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(text)
                except Exception:
                    continue
                if isinstance(parsed, list):
                    items = parsed
                    break
            if not items:
                for piece in text.split(","):
                    piece = piece.strip()
                    if not piece:
                        continue
                    if ":" in piece:
                        product_id, qty = piece.split(":", 1)
                        items.append({"product_id": product_id.strip(), "quantity": int(qty.strip())})
    else:
        items = []

    normalized: list[OrderLineInput] = []
    for item in items:
        if isinstance(item, OrderLineInput):
            normalized.append(item)
            continue
        if isinstance(item, dict):
            product_id = str(item.get("product_id", "")).strip()
            quantity = int(item.get("quantity", 1))
            if product_id:
                normalized.append(OrderLineInput(product_id=product_id, quantity=quantity))
    return normalized
