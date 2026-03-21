import { apiGet } from "./client";
import type { OpportunityItem, SourceSummary, TargetLocation } from "../types/trade";

export function getTargets() {
  return apiGet<TargetLocation[]>("/targets");
}

export function getSourceSummaries(targetLocationId: number) {
  return apiGet<SourceSummary[]>(`/opportunities/source-summaries?target_location_id=${targetLocationId}`);
}

export function getOpportunityItems(targetLocationId: number, sourceLocationId: number) {
  return apiGet<OpportunityItem[]>(
    `/opportunities/items?target_location_id=${targetLocationId}&source_location_id=${sourceLocationId}`,
  );
}
