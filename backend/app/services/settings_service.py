from app.api.schemas.settings import UserSettingsResponse, UserSettingsUpdate


class SettingsService:
    def get_settings(self) -> UserSettingsResponse:
        return UserSettingsResponse(
            default_filters={
                "min_item_profit": 15_000_000,
                "min_order_margin_pct": 0.20,
                "roi_now": 0.05,
                "target_demand_day": 1,
            }
        )

    def update_settings(self, payload: UserSettingsUpdate) -> UserSettingsResponse:
        return UserSettingsResponse(**payload.model_dump())
