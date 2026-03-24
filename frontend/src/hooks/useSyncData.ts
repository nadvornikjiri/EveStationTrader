import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cancelSyncJob, getFallbackDiagnostics, getSyncJobs, getSyncStatus, runSyncJob } from "../api/sync";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: getSyncStatus,
    placeholderData: (previousData) => previousData,
    refetchInterval: 5_000,
  });
}

export function useSyncJobs() {
  return useQuery({
    queryKey: ["syncJobs"],
    queryFn: getSyncJobs,
    placeholderData: (previousData) => previousData,
    refetchInterval: 5_000,
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
