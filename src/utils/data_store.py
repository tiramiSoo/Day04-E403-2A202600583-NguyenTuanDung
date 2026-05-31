from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from core.schemas import FlightOption, HotelOption


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().replace("tp.", "tp").replace("-", " ").strip()


class TravelDataStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.flights = json.loads((self.data_dir / "flights.json").read_text(encoding="utf-8"))
        self.hotels = json.loads((self.data_dir / "hotels.json").read_text(encoding="utf-8"))
        self.city_aliases = {
            "hcm": "Ho Chi Minh City",
            "ho chi minh": "Ho Chi Minh City",
            "ho chi minh city": "Ho Chi Minh City",
            "sai gon": "Ho Chi Minh City",
            "saigon": "Ho Chi Minh City",
            "tp hcm": "Ho Chi Minh City",
            "tphcm": "Ho Chi Minh City",
            "ha noi": "Hanoi",
            "hanoi": "Hanoi",
            "da nang": "Da Nang",
            "danang": "Da Nang",
            "da lat": "Da Lat",
            "dalat": "Da Lat",
            "phu quoc": "Phu Quoc",
            "nha trang": "Nha Trang",
        }

    def canonicalize_city(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = _normalize(value)
        return self.city_aliases.get(normalized, value.strip().title())

    def search_flights(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str,
        travelers: int,
        max_total_price: int | None = None,
    ) -> list[FlightOption]:
        origin_city = self.canonicalize_city(origin)
        destination_city = self.canonicalize_city(destination)
        results: list[FlightOption] = []
        for item in self.flights:
            if item["origin"] != origin_city:
                continue
            if item["destination"] != destination_city:
                continue
            if item["departure_date"] != departure_date:
                continue
            total_price = item["price_per_person"] * travelers
            if max_total_price is not None and total_price > max_total_price:
                continue
            results.append(
                FlightOption(
                    **item,
                    total_price=total_price,
                )
            )
        return sorted(results, key=lambda option: (option.total_price, option.stops, option.departure_time))

    def search_hotels(
        self,
        *,
        city: str,
        max_price_per_night: int | None = None,
        preferences: list[str] | None = None,
    ) -> list[HotelOption]:
        destination_city = self.canonicalize_city(city)
        wanted = {_normalize(item) for item in (preferences or [])}
        results: list[HotelOption] = []
        for item in self.hotels:
            if item["city"] != destination_city:
                continue
            if max_price_per_night is not None and item["price_per_night"] > max_price_per_night:
                continue
            hotel = HotelOption(**item)
            match_count = sum(1 for amenity in hotel.amenities if _normalize(amenity) in wanted)
            hotel.tags = list(dict.fromkeys(hotel.tags + [f"pref_match:{match_count}"]))
            results.append(hotel)
        return sorted(
            results,
            key=lambda option: (
                -self._preference_match_score(option, wanted),
                -option.star_rating,
                -option.location_score,
                option.price_per_night,
            ),
        )

    @staticmethod
    def _preference_match_score(option: HotelOption, wanted: set[str]) -> int:
        if not wanted:
            return 0
        option_amenities = {_normalize(item) for item in option.amenities}
        return len(option_amenities & wanted)
