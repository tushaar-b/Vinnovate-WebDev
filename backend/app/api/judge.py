from typing import Optional
from fastapi import APIRouter, Request, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Monitor
from app.services.judge import create_judge_session
from app.services.auth import verify_session_token, resolve_auth_payload, AuthContext

router = APIRouter(prefix="/judge", tags=["Judge Workspace"])


class JudgeSessionResponse(BaseModel):
    judge_session_id: str
    session_id: Optional[str] = None
    token: str
    expires_at: int
    role: str = "judge"
    max_monitors: int = 2
    monitor_count: int = 0
    limits: dict


class JudgeStatusResponse(BaseModel):
    active: bool = False
    authenticated: bool = False
    judge_session_id: Optional[str] = None
    session_id: Optional[str] = None
    role: Optional[str] = None


@router.post("/session", response_model=JudgeSessionResponse)
def start_judge_session(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Public endpoint to initiate or retain an anonymous evaluation session.
    No administrative credentials or passwords required.
    """
    # If client already has a valid judge session token, retain it so browser reloads keep monitors
    token_val = None
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_val = parts[1].strip()

    if token_val:
        payload = verify_session_token(token_val)
        if payload:
            auth_ctx = resolve_auth_payload(payload)
            if auth_ctx.is_judge and auth_ctx.judge_session_id:
                cnt = db.query(Monitor).filter(Monitor.judge_session_id == auth_ctx.judge_session_id).count()
                exp_ts = int(payload.get("exp", 0))
                return JudgeSessionResponse(
                    judge_session_id=auth_ctx.judge_session_id,
                    session_id=auth_ctx.judge_session_id,
                    token=token_val,
                    expires_at=exp_ts,
                    role="judge",
                    monitor_count=cnt,
                    max_monitors=2,
                    limits={
                        "max_monitors": 2,
                        "min_interval_minutes": 15,
                        "max_manual_checks_per_hour": 3,
                        "session_ttl_hours": 24,
                    },
                )

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "127.0.0.1")
    )
    return create_judge_session(client_ip)


@router.get("/session/status", response_model=JudgeStatusResponse)
def judge_session_status(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Checks validity of current judge session token.
    """
    token_val = None
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_val = parts[1].strip()

    if not token_val:
        token_val = request.query_params.get("token") or request.query_params.get("auth_token")

    if token_val:
        payload = verify_session_token(token_val)
        if payload:
            auth_ctx = resolve_auth_payload(payload)
            if auth_ctx.is_judge:
                return JudgeStatusResponse(
                    active=True,
                    authenticated=True,
                    judge_session_id=auth_ctx.judge_session_id,
                    session_id=auth_ctx.judge_session_id,
                    role="judge",
                )

    return JudgeStatusResponse(authenticated=False, judge_session_id=None, role=None)
