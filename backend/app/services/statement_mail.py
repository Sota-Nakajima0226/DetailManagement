"""明細案内メールの受理。400 相当は記録せず、200 相当は送ったときもスキップのときも記録する。"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import config
from app.models import CardIssuer, Statement, StatementMailNotification
from app.schemas import StatementMailNotifyRequest
from app.services.line_messaging import LineSendError, line_is_configured, push_text_message


logger = logging.getLogger(__name__)

_TOKYO = ZoneInfo("Asia/Tokyo")
_GMAIL_MESSAGE_URL = re.compile(
    r"^https://mail\.google\.com/mail/u/0/#inbox/([^/?#\s\\]+)$"
)
_MESSAGE_ID = re.compile(r"^[^/?#\s\\]+$")


class StatementMailRejected(Exception):
    """入力が不正。受理記録は残さない。"""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class StatementMailDeliveryError(Exception):
    """LINE 送信に失敗した。受理記録は残さず、呼び出し元がやり直せる。"""


@dataclass
class StatementMailResult:
    card_issuer_code: str
    year: int
    month: int
    notified: bool
    skip_reason: Optional[str]


def resolve_year_month(year: Optional[int], month: Optional[int]) -> tuple[int, int]:
    if year is None and month is None:
        today = datetime.now(_TOKYO).date()
        return today.year, today.month
    if year is None or month is None or not 1 <= month <= 12:
        raise StatementMailRejected("invalid year or month")
    return year, month


def mail_url_is_valid(mail_url: str) -> bool:
    return _GMAIL_MESSAGE_URL.fullmatch(mail_url) is not None


def message_id_is_valid(message_id: str) -> bool:
    return _MESSAGE_ID.fullmatch(message_id) is not None


def upload_base_is_valid(base: str) -> bool:
    if not base or "?" in base or "#" in base or any(char.isspace() for char in base):
        return False
    parsed = urlparse(base)
    return parsed.scheme == "https" and bool(parsed.netloc)


def build_upload_page_url(base: str, year: int, month: int) -> str:
    return f"{base}?year={year}&month={month}"


def build_statement_mail_text(
    *,
    display_name: str,
    year: int,
    month: int,
    mail_url: str,
    upload_url: str,
) -> str:
    return (
        f"{display_name}の明細メールが届きました（{year}年{month}月分）。\n"
        "\n"
        "1. メールを開き、明細のCSVをダウンロードしてください。\n"
        f"{mail_url}\n"
        "\n"
        "2. ダウンロードしたCSVを、次の画面からアップロードしてください。\n"
        f"{upload_url}"
    )


def notify_statement_mail(
    db: Session,
    body: StatementMailNotifyRequest,
) -> StatementMailResult:
    year, month = resolve_year_month(body.year, body.month)
    if not message_id_is_valid(body.source_message_id) or not mail_url_is_valid(body.mail_url):
        raise StatementMailRejected("invalid mail url")

    existing = (
        db.query(StatementMailNotification)
        .filter(StatementMailNotification.source_message_id == body.source_message_id)
        .first()
    )
    if existing is not None:
        return StatementMailResult(
            card_issuer_code=body.card_issuer_code,
            year=year,
            month=month,
            notified=False,
            skip_reason="duplicate_message",
        )

    issuer = db.query(CardIssuer).filter(CardIssuer.code == body.card_issuer_code).first()
    if issuer is None or not _flag(issuer.is_active):
        raise StatementMailRejected("unknown card issuer")

    if not _flag(issuer.include_in_reminder):
        if not _save(db, issuer, body, year, month, notified=False, skip_reason="issuer_excluded"):
            return _duplicate(body, year, month)
        return _skipped(body, year, month, "issuer_excluded")

    uploaded = (
        db.query(Statement)
        .filter(
            Statement.card_issuer_id == issuer.id,
            Statement.year == year,
            Statement.month == month,
        )
        .first()
    )
    if uploaded is not None and not body.force:
        if not _save(db, issuer, body, year, month, notified=False, skip_reason="already_uploaded"):
            return _duplicate(body, year, month)
        return _skipped(body, year, month, "already_uploaded")

    upload_base = config.APP_UPLOAD_URL
    if not upload_base_is_valid(upload_base):
        logger.warning(
            "statement mail skipped: upload url is not configured issuer=%s",
            body.card_issuer_code,
        )
        if not _save(
            db,
            issuer,
            body,
            year,
            month,
            notified=False,
            skip_reason="upload_url_not_configured",
        ):
            return _duplicate(body, year, month)
        return _skipped(body, year, month, "upload_url_not_configured")

    if not line_is_configured():
        logger.warning(
            "statement mail skipped: LINE is not configured issuer=%s",
            body.card_issuer_code,
        )
        if not _save(db, issuer, body, year, month, notified=False, skip_reason="line_not_configured"):
            return _duplicate(body, year, month)
        return _skipped(body, year, month, "line_not_configured")

    text = build_statement_mail_text(
        display_name=str(issuer.display_name),
        year=year,
        month=month,
        mail_url=body.mail_url,
        upload_url=build_upload_page_url(upload_base, year, month),
    )
    try:
        push_text_message(text)
    except LineSendError as exc:
        raise StatementMailDeliveryError() from exc

    if not _save(db, issuer, body, year, month, notified=True, skip_reason=None):
        return _duplicate(body, year, month)
    return StatementMailResult(
        card_issuer_code=body.card_issuer_code,
        year=year,
        month=month,
        notified=True,
        skip_reason=None,
    )


def _flag(value: object) -> bool:
    return value is True or value == 1


def _skipped(
    body: StatementMailNotifyRequest,
    year: int,
    month: int,
    skip_reason: str,
) -> StatementMailResult:
    return StatementMailResult(
        card_issuer_code=body.card_issuer_code,
        year=year,
        month=month,
        notified=False,
        skip_reason=skip_reason,
    )


def _duplicate(
    body: StatementMailNotifyRequest,
    year: int,
    month: int,
) -> StatementMailResult:
    return _skipped(body, year, month, "duplicate_message")


def _save(
    db: Session,
    issuer: CardIssuer,
    body: StatementMailNotifyRequest,
    year: int,
    month: int,
    *,
    notified: bool,
    skip_reason: Optional[str],
) -> bool:
    db.add(
        StatementMailNotification(
            card_issuer_id=issuer.id,
            source_message_id=body.source_message_id,
            year=year,
            month=month,
            mail_url=body.mail_url,
            notified=notified,
            skip_reason=skip_reason,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True
