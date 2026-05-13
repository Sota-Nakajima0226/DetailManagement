"""ルール未適用の店名を OpenAI でカテゴリ分類する。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncOpenAI

from app.core.config import LOG_AI_CLASSIFICATION_DETAIL
from app.core.logging import log_event

logger = logging.getLogger(__name__)

# 1リクエストあたりの店名件数（トークン上限とレイテンシのバランス）
_BATCH_SIZE = 32

# DB に保存する生レスポンスの上限
_MAX_RAW_LEN = 4000


@dataclass(frozen=True)
class ShopAiClassification:
    """1店名分の AI 分類結果（確信度が閾値未満のときは category_id / classified_by は None）。"""

    category_id: Optional[int]
    classified_by: Optional[str]
    ai_confidence: Optional[float]
    ai_raw_response: Optional[str]


def _truncate_raw(text: str) -> str:
    if len(text) <= _MAX_RAW_LEN:
        return text
    return text[: _MAX_RAW_LEN - 3] + "..."


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON object not found in model output")
    return json.loads(stripped[start : end + 1])


def _coerce_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in payload and isinstance(payload["items"], list):
        return [x for x in payload["items"] if isinstance(x, dict)]
    if "classifications" in payload and isinstance(payload["classifications"], list):
        return [x for x in payload["classifications"] if isinstance(x, dict)]
    raise ValueError("expected 'items' or 'classifications' array in JSON")


async def classify_shop_names_openai(
    *,
    api_key: str,
    model: str,
    confidence_threshold: float,
    categories: list[tuple[int, str]],
    shop_names: list[str],
) -> dict[str, ShopAiClassification]:
    """
    shop_names のうち重複を除いた店名ごとに分類結果を返す。
    API 失敗時はログのうえ空 dict を返す（呼び出し側は未分類扱い）。
    """
    if not shop_names or not categories:
        return {}

    allowed_ids = {cid for cid, _ in categories}
    unique_shops = list(dict.fromkeys(shop_names))
    client = AsyncOpenAI(api_key=api_key)
    out: dict[str, ShopAiClassification] = {}

    categories_block = json.dumps(
        [{"id": cid, "name": name} for cid, name in categories],
        ensure_ascii=False,
    )

    for offset in range(0, len(unique_shops), _BATCH_SIZE):
        batch = unique_shops[offset : offset + _BATCH_SIZE]
        shops_json = json.dumps(batch, ensure_ascii=False)
        user_prompt = f"""あなたは日本の家計簿アプリのカテゴリ分類器です。

次の JSON 配列は、クレジットカード明細の「利用店名・商品名」です（重複なし）:
{shops_json}

利用可能なカテゴリは次の JSON 配列のみです。id は必ずこの一覧の id のいずれかを使ってください:
{categories_block}

各店名について、最も適切な category_id と、あなたの判断の確信度 confidence（0.0〜1.0）を付けてください。

次の JSON だけを返してください（説明文やコードフェンスは禁止）:
{{"items":[{{"shop_name":"（入力と同一の文字列）","category_id":数値,"confidence":0.0〜1.0}},...]}}

ルール:
- items の要素数は入力店名の件数と同じにする。
- 各 shop_name は入力と完全に一致させる。
- 迷う場合は confidence を低くする。
"""

        try:
            request_fields: dict[str, Any] = {
                "model": model,
                "batch_size": len(batch),
                "category_count": len(categories),
                "confidence_threshold": confidence_threshold,
            }
            if LOG_AI_CLASSIFICATION_DETAIL:
                request_fields["shop_names"] = batch
            log_event(logger, "ai_classification_request", **request_fields)

            response = await client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You output only valid JSON objects. No markdown.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw_content = (response.choices[0].message.content or "").strip()
            payload = _parse_json_object(raw_content)
            items = _coerce_items(payload)
            if len(items) != len(batch):
                logger.warning(
                    "ai_classification_response_count_mismatch",
                    extra={
                        "event_name": "ai_classification_response_count_mismatch",
                        "event_fields": {
                            "batch_size": len(batch),
                            "returned_count": len(items),
                            **({"sample_shop_names": batch[:3]} if LOG_AI_CLASSIFICATION_DETAIL else {}),
                        },
                    },
                )

            accepted_count = 0
            low_confidence_count = 0
            invalid_category_count = 0
            result_details: list[dict[str, Any]] = []

            for entry in items:
                name = str(entry.get("shop_name", "")).strip()
                if not name:
                    continue
                entry_raw = _truncate_raw(json.dumps(entry, ensure_ascii=False))
                try:
                    cid = int(entry["category_id"])
                except (KeyError, TypeError, ValueError):
                    cid = -1
                try:
                    conf = float(entry.get("confidence", 0.0))
                except (TypeError, ValueError):
                    conf = 0.0
                conf = max(0.0, min(1.0, conf))

                if cid not in allowed_ids:
                    invalid_category_count += 1
                    out[name] = ShopAiClassification(
                        category_id=None,
                        classified_by=None,
                        ai_confidence=conf,
                        ai_raw_response=entry_raw,
                    )
                    if LOG_AI_CLASSIFICATION_DETAIL:
                        result_details.append(
                            {
                                "shop_name": name,
                                "category_id": None,
                                "confidence": conf,
                                "accepted": False,
                                "reason": "invalid_category",
                            }
                        )
                    continue

                if conf >= confidence_threshold:
                    accepted_count += 1
                    out[name] = ShopAiClassification(
                        category_id=cid,
                        classified_by="ai",
                        ai_confidence=conf,
                        ai_raw_response=entry_raw,
                    )
                    if LOG_AI_CLASSIFICATION_DETAIL:
                        result_details.append(
                            {
                                "shop_name": name,
                                "category_id": cid,
                                "confidence": conf,
                                "accepted": True,
                            }
                        )
                else:
                    low_confidence_count += 1
                    out[name] = ShopAiClassification(
                        category_id=None,
                        classified_by=None,
                        ai_confidence=conf,
                        ai_raw_response=entry_raw,
                    )
                    if LOG_AI_CLASSIFICATION_DETAIL:
                        result_details.append(
                            {
                                "shop_name": name,
                                "category_id": cid,
                                "confidence": conf,
                                "accepted": False,
                                "reason": "low_confidence",
                            }
                        )

            response_fields: dict[str, Any] = {
                "model": model,
                "batch_size": len(batch),
                "returned_count": len(items),
                "accepted_count": accepted_count,
                "low_confidence_count": low_confidence_count,
                "invalid_category_count": invalid_category_count,
            }
            if LOG_AI_CLASSIFICATION_DETAIL:
                response_fields["results"] = result_details
            log_event(logger, "ai_classification_response", **response_fields)
        except Exception:
            logger.exception(
                "ai_classification_failed",
                extra={
                    "event_name": "ai_classification_failed",
                    "event_fields": {
                        "model": model,
                        "batch_size": len(batch),
                        **({"sample_shop_names": batch[:5]} if LOG_AI_CLASSIFICATION_DETAIL else {}),
                    },
                },
            )

    return out
