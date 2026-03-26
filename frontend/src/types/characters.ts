export type CharacterListItem = {
  id: number;
  character_name: string;
  corporation_name: string | null;
  granted_scopes: string[];
  sync_enabled: boolean;
  last_token_refresh: string | null;
  last_successful_sync: string | null;
  assets_sync_status: string;
  orders_sync_status: string;
  skills_sync_status: string;
  structures_sync_status: string;
  accessible_structure_count: number;
};

export type AccessibleStructureItem = {
  structure_name: string;
  structure_id: number;
  system_name: string | null;
  region_name: string | null;
  access_verified_at: string;
  tracking_enabled: boolean;
  polling_tier: string;
  last_snapshot_at: string | null;
  confidence_score: number;
};

export type CharacterDetail = {
  id: number;
  character_name: string;
  corporation_name: string | null;
  granted_scopes: string[];
  sync_enabled: boolean;
  sync_toggles: Record<string, boolean>;
  structures: AccessibleStructureItem[];
  skills: string[];
};
