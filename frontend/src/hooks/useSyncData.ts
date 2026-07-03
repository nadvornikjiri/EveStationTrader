import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cancelSyncJob, clearStaleJobs, clearSyncData, getFallbackDiagnostics, getScheduleConfigs, getSyncJobs, getSyncStatus, runSyncJob, updateScheduleConfig } from "../api/sync";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: getSyncStatus,
    placeholderData: (previousData) => previousData,
    refetchInterval: 1_000,
  });
}

export function useSyncJobs(limit = 25, offset = 0) {
  return useQuery({
    queryKey: ["syncJobs", limit, offset],
    queryFn: () => getSyncJobs(limit, offset),
    placeholderData: (previousData) => previousData,
    refetchInterval: 3_000,
  });
}

export function useFallbackDiagnostics() {
  return useQuery({
    queryKey: ["fallbackDiagnostics"],
    queryFn: getFallbackDiagnostics,
    placeholderData: (previousData) => previousData,
    refetchInterval: 5_000,
  });
}

export function useRunSyncJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runSyncJob,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["syncStatus"] }),
        queryClient.invalidateQueries({ queryKey: ["syncJobs"] }),
      ]);
    },
  });
}

export function useCancelSyncJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelSyncJob,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["syncStatus"] }),
        queryClient.invalidateQueries({ queryKey: ["syncJobs"] }),
      ]);
    },
  });
}

export function useClearStaleJobs() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: clearStaleJobs,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["syncStatus"] }),
        queryClient.invalidateQueries({ queryKey: ["syncJobs"] }),
      ]);
    },
  });
}

export function useScheduleConfigs() {
  return useQuery({
    queryKey: ["scheduleConfigs"],
    queryFn: getScheduleConfigs,
    placeholderData: (previousData) => previousData,
    refetchInterval: 30_000,
  });
}

export function useUpdateScheduleConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateScheduleConfig,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["scheduleConfigs"] });
    },
  });
}

export function useClearSyncData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: clearSyncData,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["syncStatus"] }),
        queryClient.invalidateQueries({ queryKey: ["syncJobs"] }),
        queryClient.invalidateQueries({ queryKey: ["fallbackDiagnostics"] }),
      ]);
    },
  });
}
