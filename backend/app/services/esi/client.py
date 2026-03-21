from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from app.core.config import get_settings
from app.services.esi.history_ingestion import EsiRegionalHistoryRecord


class EsiClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.a4e_user_agent,
            "X-Compatibility-Date": self.settings.esi_compatibility_date,
        }

    def exchange_code(self, code: str) -> dict:
        # TODO: Implement real EVE SSO token exchange.
        del code
        return {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
            "scopes": [],
        }

    def fetch_character_identity(self, access_token: str) -> dict:
        del access_token
        return {
            "character_id": 90000001,
            "character_name": "Demo Trader",
            "corporation_name": "Open Traders Union",
        }

    def fetch_regional_history(self, region_id: int, type_ids: Iterable[int]) -> list[EsiRegionalHistoryRecord]:
        today = date.today()
        history: list[EsiRegionalHistoryRecord] = []
        for offset, type_id in enumerate(type_ids):
            base_price = 100.0 + (offset * 10.0)
            history.append(
                {
                    "type_id": type_id,
                    "date": today.isoformat(),
                    "average": base_price,
                    "highest": base_price * 1.1,
                    "lowest": base_price * 0.9,
                    "order_count": 25,
                    "volume": 1_000 + (offset * 100),
                }
            )
        return history
