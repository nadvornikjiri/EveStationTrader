import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { connectCharacter, getCharacter, getCharacters, patchCharacter, syncCharacter, trackStructure } from "../api/characters";

export function useCharacters() {
  return useQuery({
    queryKey: ["characters"],
    queryFn: getCharacters,
    placeholderData: (previousData) => previousData,
    refetchInterval: 60_000,
  });
}

export function useCharacterDetail(characterId: number | null) {
  return useQuery({
    queryKey: ["character", characterId],
    queryFn: () => getCharacter(characterId!),
    enabled: characterId !== null,
    placeholderData: (previousData) => previousData,
  });
}

export function useConnectCharacter() {
  return useMutation({
    mutationFn: connectCharacter,
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
  });
}

export function useSyncCharacter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (characterId: number) => syncCharacter(characterId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["characters"] });
    },
  });
}

export function usePatchCharacter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ characterId, syncEnabled }: { characterId: number; syncEnabled: boolean }) =>
      patchCharacter(characterId, { sync_enabled: syncEnabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["characters"] });
      void queryClient.invalidateQueries({ queryKey: ["character"] });
    },
  });
}

export function useTrackStructure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ characterId, structureId }: { characterId: number; structureId: number }) =>
      trackStructure(characterId, structureId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["character"] });
    },
  });
}
