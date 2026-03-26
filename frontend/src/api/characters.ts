import { apiGet, apiPatch, apiPost } from "./client";
import type { CharacterDetail, CharacterListItem } from "../types/characters";

export function getCharacters() {
  return apiGet<CharacterListItem[]>("/characters");
}

export function getCharacter(characterId: number) {
  return apiGet<CharacterDetail>(`/characters/${characterId}`);
}

export function connectCharacter() {
  return apiPost<{ authorize_url: string; scopes: string[] }>("/characters/connect");
}

export function syncCharacter(characterId: number) {
  return apiPost<{ message: string }>(`/characters/${characterId}/sync`);
}

export function patchCharacter(characterId: number, body: { sync_enabled?: boolean }) {
  return apiPatch<{ message: string }>(`/characters/${characterId}`, body);
}

export function trackStructure(characterId: number, structureId: number) {
  return apiPost<{ message: string }>(`/characters/${characterId}/structures/${structureId}/track`);
}
