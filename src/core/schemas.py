from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FlightOption(BaseModel):
    flight_id: str
    origin: str
    destination: str
    departure_date: str
    airline: str
    departure_time: str
    arrival_time: str
    price_per_person: int
    total_price: int
    stops: int
    tags: list[str] = Field(default_factory=list)


class HotelOption(BaseModel):
    hotel_id: str
    city: str
    name: str
    star_rating: float
    location_score: float
    price_per_night: int
    amenities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    output: str = ""


class AgentResult(BaseModel):
    query: str
    final_answer: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    provider: str = "google"
    model_name: str | None = None
