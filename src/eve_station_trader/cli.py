from __future__ import annotations

import argparse
import json
import sys

from .config import (
    BROKER_FEE_DEFAULT,
    DEFAULT_CACHE_TTL_SECONDS,
    KNOWN_HUBS,
    SALES_TAX_DEFAULT,
    TOP_RESULTS_DEFAULT,
)
from .report import render_table
from .service import TraderService


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    service = TraderService(
        cache_ttl=args.cache_ttl,
        datasource=args.datasource,
    )
    result = service.scan(
        source_hub_key=args.source_hub,
        destination_hub_key=args.destination_hub,
        source_region_id=args.source_region_id,
        source_location_id=args.source_location_id,
        destination_region_id=args.destination_region_id,
        destination_location_id=args.destination_location_id,
        strategy=args.strategy,
        minimum_profit=args.min_profit,
        minimum_roi_percent=args.min_roi,
        sales_tax=args.sales_tax,
        destination_broker_fee=args.destination_broker_fee,
        top_n=args.top,
        refresh=args.refresh,
    )

    if args.format == "json":
        print(json.dumps(result["opportunities"], indent=2))
    else:
        print(
            render_table(
                service.resolve_hub(args.source_hub, args.source_region_id, args.source_location_id),
                service.resolve_hub(args.destination_hub, args.destination_region_id, args.destination_location_id),
                [
                    _dict_to_opportunity(row)
                    for row in result["opportunities"]
                ],
            )
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eve-station-trader",
        description="Scan EVE Online trade hubs for hub-to-hub market opportunities.",
    )
    parser.add_argument("--source-hub", choices=sorted(KNOWN_HUBS), default="jita")
    parser.add_argument("--destination-hub", choices=sorted(KNOWN_HUBS), default="amarr")
    parser.add_argument("--source-region-id", type=int)
    parser.add_argument("--source-location-id", type=int)
    parser.add_argument("--destination-region-id", type=int)
    parser.add_argument("--destination-location-id", type=int)
    parser.add_argument("--strategy", choices=["instant", "relist"], default="instant")
    parser.add_argument("--min-profit", type=float, default=20_000_000)
    parser.add_argument("--min-roi", type=float, default=8.0)
    parser.add_argument("--sales-tax", type=float, default=SALES_TAX_DEFAULT)
    parser.add_argument("--destination-broker-fee", type=float, default=BROKER_FEE_DEFAULT)
    parser.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL_SECONDS)
    parser.add_argument("--top", type=int, default=TOP_RESULTS_DEFAULT)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--datasource", default="tranquility")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    return parser


def _dict_to_opportunity(payload: dict[str, object]):
    from .models import Opportunity

    return Opportunity(**payload)


if __name__ == "__main__":
    sys.exit(main())
