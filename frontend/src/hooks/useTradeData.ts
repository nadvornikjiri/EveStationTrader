import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteInTransitAsset,
  getInTransitAssets,
  getOpportunityItemDetail,
  getOpportunityItems,
  getSources,
  getSourceSummaries,
  getTargetOptions,
  getTargets,
  getTargetOpportunityItems,
  type TradeFilters,
  upsertInTransitAsset,
} from "../api/trade";

export function useTargets() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: getTargets,
  });
}

export function useTargetOptions() {
  return useQuery({
    queryKey: ["targetOptions"],
    queryFn: getTargetOptions,
  });
}

export function useSources(targetLocationId: number | null, periodDays: number, enabled = true) {
  return useQuery({
    queryKey: ["sources", targetLocationId, periodDays],
    queryFn: () => getSources(targetLocationId ?? 0, periodDays),
    enabled: targetLocationId !== null && enabled,
  });
}

export function useSourceSummaries(targetLocationId: number | null, periodDays: number, filters: TradeFilters, enabled = true) {
  return useQuery({
    queryKey: ["sourceSummaries", targetLocationId, periodDays, filters],
    queryFn: () => getSourceSummaries(targetLocationId ?? 0, periodDays, filters),
    enabled: targetLocationId !== null && enabled,
    refetchInterval: 60_000,
  });
}

export function useOpportunityItems(
  targetLocationId: number | null,
  sourceLocationId: number | null,
  periodDays: number,
  filters: TradeFilters,
  enabled = true,
) {
  return useQuery({
    queryKey: ["opportunityItems", targetLocationId, sourceLocationId, periodDays, filters],
    queryFn: () => getOpportunityItems(targetLocationId ?? 0, sourceLocationId ?? 0, periodDays, filters),
    enabled: targetLocationId !== null && sourceLocationId !== null && enabled,
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

export function useTargetOpportunityItems(targetLocationId: number | null, periodDays: number, enabled = true) {
  return useQuery({
    queryKey: ["targetOpportunityItems", targetLocationId, periodDays],
    queryFn: () => getTargetOpportunityItems(targetLocationId ?? 0, periodDays),
    enabled: targetLocationId !== null && enabled,
    refetchInterval: 60_000,
  });
}

export function useInTransitAssets(targetLocationId: number | null, enabled = true) {
  return useQuery({
    queryKey: ["inTransitAssets", targetLocationId],
    queryFn: () => getInTransitAssets(targetLocationId ?? 0),
    enabled: targetLocationId !== null && enabled,
    refetchInterval: 60_000,
  });
}

export function useUpsertInTransitAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: upsertInTransitAsset,
    onSuccess: (record) => {
      void queryClient.invalidateQueries({ queryKey: ["inTransitAssets", record.target_location_id] });
    },
  });
}

export function useDeleteInTransitAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId }: { entryId: number }) => deleteInTransitAsset(entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["inTransitAssets"] });
    },
  });
}
