from fastapi import APIRouter, HTTPException

from app.api.schemas.characters import AccessibleStructureItem, CharacterDetail, CharacterListItem, CharacterPatchRequest
from app.api.schemas.common import MessageResponse
from app.services.characters.service import CharacterService

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterListItem])
def get_characters() -> list[CharacterListItem]:
    return CharacterService().list_characters()


@router.post("/connect", response_model=MessageResponse)
def connect_character() -> MessageResponse:
    return MessageResponse(message="Use /api/auth/login to start the EVE SSO flow.")


@router.get("/{character_id}", response_model=CharacterDetail)
def get_character(character_id: int) -> CharacterDetail:
    try:
        return CharacterService().get_character(character_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{character_id}/sync", response_model=MessageResponse)
def sync_character(character_id: int) -> MessageResponse:
    return MessageResponse(message=f"Queued sync for character {character_id}.")


@router.patch("/{character_id}", response_model=MessageResponse)
def patch_character(character_id: int, payload: CharacterPatchRequest) -> MessageResponse:
    return MessageResponse(message=f"Updated character {character_id} with {payload.model_dump(exclude_none=True)}.")


@router.get("/{character_id}/structures", response_model=list[AccessibleStructureItem])
def get_character_structures(character_id: int) -> list[AccessibleStructureItem]:
    try:
        return CharacterService().get_character(character_id).structures
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{character_id}/structures/{structure_id}/track", response_model=MessageResponse)
def track_structure(character_id: int, structure_id: int) -> MessageResponse:
    return MessageResponse(message=f"Enabled tracking for structure {structure_id} via character {character_id}.")
