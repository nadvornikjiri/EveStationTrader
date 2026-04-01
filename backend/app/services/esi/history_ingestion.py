from app.services.adam4eve.history_ingestion import (
    AdamStationPriceHistoryIngestionResult,
    AdamStationPriceHistoryIngestionService,
    AdamStationPriceHistoryRecord,
)

# Backward-compatible exports while the runtime code transitions off the old ESI naming.
EsiRegionalHistoryRecord = AdamStationPriceHistoryRecord
EsiRegionalHistoryIngestionResult = AdamStationPriceHistoryIngestionResult
EsiRegionalHistoryIngestionService = AdamStationPriceHistoryIngestionService
