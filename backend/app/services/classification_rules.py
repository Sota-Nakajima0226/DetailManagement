"""分類ルールのパターン検証。保存はしない。"""
from __future__ import annotations

import re


class RulePatternError(Exception):
    """パターンが空、または正規表現としてコンパイルできない。"""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def validate_rule_pattern(pattern: str, is_regex: bool) -> None:
    """前後の空白を除いて空なら拒否する。正規表現のときだけ compile する。"""
    if pattern.strip() == "":
        raise RulePatternError("pattern is empty")
    if not is_regex:
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        raise RulePatternError("invalid regular expression") from exc
