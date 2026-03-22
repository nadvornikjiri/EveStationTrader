import { useQuery } from "@tanstack/react-query";

import {
  getOpportunityItemDetail,
  getOpportunityItems,
  getSourceSummaries,
  getTargets,
} from "../api/trade";

export function useTargets() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: getTargets,
  });
}

export function useSourceSummaries(targetLocationId: number | null, periodDays: number) {
  return useQuery({
    queryKey: ["sourceSummaries", targetLocationId, periodDays],
    queryFn: () => getSourceSummaries(targetLocationId ?? 0, periodDays),
    enabled: targetLocationId !== null,
    refetchInterval: 60_000,
  });
}

export function useOpportunityItems(
  targetLocationId: number | null,
  sourceLocationId: number | null,
  periodDays: number,
) {
  return useQuery({
    queryKey: ["opportunityItems", targetLocationId, sourceLocationId, periodDays],
    queryFn: () => getOpportunityItems(targetLocationId ?? 0, sourceLocationId ?? 0, periodDays),
    enabled: targetLocationId !== null && sourceLocationId !== null,
    refetchInterval: 60_000,
  });
}

export function useOpportunityItemDetail(
  targetLocationId: number | null,
  sourceLocationId: number | null,
  typeId: number | null,
  periodDays: number,
) {
  return useQuery({
    queryKey: ["opportunityItemDetail", targetLocationId, sourceLocationId, typeId, periodDays],
    queryFn: () => getOpportunityItemDetail(targetLocationId ?? 0, sourceLocationId ?? 0, typeId ?? 0, periodDays),
    enabled: targetLocationId !== null && sourceLocationId !== null && typeId !== null,
    refetchInterval: 60_000,
  });
}
