from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.chatgpt.deps import get_chatgpt_service
from app.chatgpt.models import ChatGPTModelSelection, ChatGPTStatus
from app.chatgpt.service import ChatGPTService
from app.core.config import get_settings

router = APIRouter(prefix="/auth/chatgpt", tags=["chatgpt"])
STATE_COOKIE = "tripwise_chatgpt_state"
COOKIE_PATH = "/api/v1/auth/chatgpt"
Service = Annotated[ChatGPTService, Depends(get_chatgpt_service)]


def _frontend_redirect(*, result: str, reason: str | None = None) -> RedirectResponse:
    settings = get_settings()
    query = {"chatgpt": result}
    if reason:
        query["reason"] = reason
    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}/?{urlencode(query)}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    response.delete_cookie(
        STATE_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/start", response_class=RedirectResponse)
def start_chatgpt_authorization(service: Service) -> RedirectResponse:
    authorization = service.start_authorization()
    response = RedirectResponse(
        authorization.url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    response.set_cookie(
        STATE_COOKIE,
        authorization.state,
        max_age=600,
        httponly=True,
        secure=False,
        samesite="lax",
        path=COOKIE_PATH,
    )
    return response


@router.get("/callback", response_class=RedirectResponse)
def complete_chatgpt_authorization(
    service: Service,
    code: Annotated[str | None, Query()] = None,
    state_value: Annotated[str | None, Query(alias="state")] = None,
    client_id: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
    state_cookie: Annotated[str | None, Cookie(alias=STATE_COOKIE)] = None,
) -> RedirectResponse:
    del error_description
    if not state_value or not state_cookie or not hmac_compare(state_value, state_cookie):
        return _frontend_redirect(result="error", reason="state_mismatch")
    if error or not code:
        return _frontend_redirect(result="error", reason="authorization_failed")
    try:
        result = service.complete_authorization(
            code=code,
            state=state_value,
            callback_client_id=client_id,
        )
    except Exception:
        return _frontend_redirect(result="error", reason="authorization_failed")
    callback_result = "connected" if result.plan_enabled else "scope_required"
    return _frontend_redirect(result=callback_result)


def hmac_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


@router.get("/status", response_model=ChatGPTStatus)
def chatgpt_status(service: Service) -> ChatGPTStatus:
    return service.status()


@router.post("/model", response_model=ChatGPTStatus)
def select_chatgpt_model(
    payload: ChatGPTModelSelection,
    service: Service,
) -> ChatGPTStatus:
    try:
        return service.select_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/disconnect", response_model=ChatGPTStatus)
def disconnect_chatgpt(service: Service) -> ChatGPTStatus:
    try:
        return service.disconnect()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
