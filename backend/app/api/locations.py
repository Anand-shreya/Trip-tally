from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.providers.locations import LocationProviderError, search_locations
from app.schemas.location import LocationKind, LocationSuggestion

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search", response_model=list[LocationSuggestion])
async def search_location_options(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    kind: LocationKind,
) -> list[LocationSuggestion]:
    try:
        return await search_locations(q.strip(), kind)
    except LocationProviderError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Location search is temporarily unavailable",
        ) from None
