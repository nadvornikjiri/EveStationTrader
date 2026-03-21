import { useQuery } from "@tanstack/react-query";

import { getOpportunityItems, getSourceSummaries, getTargets } from "../api/trade";

export function useTargets() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: getTargets,
  });
}

export function useSourceSummaries(targetLocationId: number | null) {
  return useQuery({
    queryKey: ["sourceSummaries", targetLocationId],
    queryFn: () => getSourceSummaries(targetLocationId ?? 0),
    enabled: targetLocationId !== null,
    refetchInterval: 60_000,
  });
}

export function useOpportunityItems(targetLocationId: number | null, sourceLocationId: number | null) {
  return useQuery({
    queryKey: ["opportunityItems", targetLocationId, sourceLocationId],
    queryFn: () => getOpportunityItems(targetLocationId ?? 0, sourceLocationId ?? 0),
    enabled: targetLocationId !== null && sourceLocationId !== null,
    refetchInterval: 60_000,
  });
}
