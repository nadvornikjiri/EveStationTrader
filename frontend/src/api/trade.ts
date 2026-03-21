import { apiGet } from "./client";
import type { OpportunityItem, SourceSummary, TargetLocation } from "../types/trade";

export function getTargets() {
  return apiGet<TargetLocation[]>("/targets");
}

export function getSourceSummaries(targetLocationId: number, periodDays: number) {
  return apiGet<SourceSummary[]>(
    `/opportunities/source-summaries?target_location_id=${targetLocationId}&period_days=${periodDays}`,
  );
}

export function getOpportunityItems(targetLocationId: number, sourceLocationId: number, periodDays: number) {
  return apiGet<OpportunityItem[]>(
    `/opportunities/items?target_location_id=${targetLocationId}&source_location_id=${sourceLocationId}&period_days=${periodDays}`,
  );
}
