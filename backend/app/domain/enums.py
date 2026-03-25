from enum import Enum


class LocationType(str, Enum):
    NPC_STATION = "npc_station"
    STRUCTURE = "structure"


class DemandSource(str, Enum):
    ADAM4EVE = "adam4eve"
    LOCAL_STRUCTURE = "local_structure"
    REGIONAL_FALLBACK = "regional_fallback"
    BLENDED = "blended"


class TrackingTier(str, Enum):
    CORE = "core"
    SECONDARY = "secondary"
    USER = "user"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class JobType(str, Enum):
    ADAM4EVE_SYNC = "adam4eve_sync"
    STRUCTURE_SNAPSHOT_SYNC = "structure_snapshot_sync"
    CHARACTER_SYNC = "character_sync"
    OPPORTUNITY_REBUILD = "opportunity_rebuild"
