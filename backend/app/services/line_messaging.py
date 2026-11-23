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
