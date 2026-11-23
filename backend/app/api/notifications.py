"""明細案内メールの着信通知。ユーザー JWT ではなく REMIND_CRON_SECRET で認証する。"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.schemas import StatementMailNotifyRequest, StatementMailNotifyResponse
from app.services.statement_mail import (
    StatementMailDeliveryError,
    StatementMailRejected,
    notify_statement_mail,
)


router = APIRouter(prefix="/notify", tags=["notify"])

_bearer_scheme = HTTPBearer(auto_error=False)


def require_remind_cron_secret(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> None:
    expected = config.REMIND_CRON_SECRET
    provided = credentials.credentials if credentials is not None else ""
    if not expected or not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid notify secret",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/statement-mail", response_model=StatementMailNotifyResponse)
def post_statement_mail(
    body: StatementMailNotifyRequest,
    _: None = Depends(require_remind_cron_secret),
    db: Session = Depends(get_db),
) -> StatementMailNotifyResponse:
    try:
        result = notify_statement_mail(db, body)
    except StatementMailRejected as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc
    except StatementMailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LINE notification failed",
        ) from exc

    return StatementMailNotifyResponse(
        card_issuer_code=result.card_issuer_code,
        year=result.year,
        month=result.month,
        notified=result.notified,
        skip_reason=result.skip_reason,
    )
