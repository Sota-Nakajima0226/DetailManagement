"""LINE Messaging API へのテキスト1通。トークンや本文はログに出さない。"""
from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core import config


logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineNotConfiguredError(Exception):
    """チャネルアクセストークンかグループ ID が無い。"""


class LineSendError(Exception):
    """LINE への送信に失敗した。メッセージには秘密や本文を含めない。"""


def line_is_configured() -> bool:
    return bool(config.LINE_CHANNEL_ACCESS_TOKEN and config.LINE_GROUP_ID)


def build_upload_completed_text(month: int, display_names: list[str]) -> str:
    names = "、".join(display_names)
    return f"{month}月の明細がアップロードされました（{names}）。確認してください。"


def notify_upload_completed(month: int, display_names: list[str]) -> None:
    """成功した表示名があるときだけ1通送る。未設定や送信失敗では例外を出さない。"""
    if not display_names:
        return
    if not line_is_configured():
        logger.warning("upload completion LINE skipped: LINE is not configured")
        return
    try:
        push_text_message(build_upload_completed_text(month, display_names))
    except Exception:
        logger.warning("upload completion LINE failed")


def push_text_message(text: str) -> None:
    """設定済みグループへテキストを1通送る。未設定や失敗は例外にする。"""
    token = config.LINE_CHANNEL_ACCESS_TOKEN
    group_id = config.LINE_GROUP_ID
    if not token or not group_id:
        raise LineNotConfiguredError()

    payload = json.dumps(
        {"to": group_id, "messages": [{"type": "text", "text": text}]},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        LINE_PUSH_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        logger.warning("LINE push failed: status=%s", exc.code)
        raise LineSendError() from None
    except URLError:
        logger.warning("LINE push failed: network error")
        raise LineSendError() from None
