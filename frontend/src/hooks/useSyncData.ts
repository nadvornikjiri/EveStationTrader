import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getFallbackDiagnostics, getSyncJobs, getSyncStatus, runSyncJob } from "../api/sync";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: getSyncStatus,
    refetchInterval: 60_000,
  });
}

export function useSyncJobs() {
  return useQuery({
    queryKey: ["syncJobs"],
    queryFn: getSyncJobs,
    refetchInterval: 60_000,
  });
}

export function useFallbackDiagnostics() {
  return useQuery({
    queryKey: ["fallbackDiagnostics"],
    queryFn: getFallbackDiagnostics,
    refetchInterval: 60_000,
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
