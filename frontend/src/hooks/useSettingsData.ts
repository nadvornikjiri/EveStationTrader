import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getSettings, updateSettings } from "../api/settings";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
    placeholderData: (previousData) => previousData,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: async (settings) => {
      queryClient.setQueryData(["settings"], settings);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}
