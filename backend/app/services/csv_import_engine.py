"""プロファイル駆動の汎用 CSV → 共通モデル変換。

会社専用パーサは置かない。差分は csv_import_profiles の JSON 設定のみ。
custom_hook は未対応（無視）。
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class CommonCsvRow:
    used_at: date
    shop_name: str
    amount: int
    card_holder: Optional[str]


@dataclass(frozen=True)
class CsvParseResult:
    rows: list[CommonCsvRow]
    error_count: int
    headers: list[str]


class CsvImportError(ValueError):
    """プロファイルまたは CSV が解釈できないときのエラー。"""


def header_signature_matches(
    headers: Sequence[str],
    header_signature: Sequence[str],
) -> bool:
    """header_signature の全要素がヘッダに含まれる（順序不問）。"""
    header_set = {h.strip() for h in headers if h is not None and str(h).strip()}
    if not header_signature:
        return False
    return all(str(col).strip() in header_set for col in header_signature)


def _as_mapping(profile: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(profile, Mapping):
        return profile
    # SQLAlchemy モデル等: 属性から必要なキーを拾う
    keys = (
        "encoding",
        "header_signature",
        "column_mapping",
        "transforms",
        "skip_rules",
        "custom_hook",
    )
    return {k: getattr(profile, k) for k in keys if hasattr(profile, k)}


def _decode_csv(content: bytes, encoding: str) -> str:
    try:
        return content.decode(encoding)
    except LookupError as exc:
        raise CsvImportError(f"Unknown encoding: {encoding}") from exc
    except UnicodeDecodeError as exc:
        raise CsvImportError(f"Failed to decode CSV with encoding={encoding}") from exc


def _normalize_amount(raw: str, remove_chars: Sequence[str]) -> str:
    text = raw.strip().strip('"').strip("'")
    for ch in remove_chars:
        text = text.replace(ch, "")
    return text.strip()


def _apply_card_holder(
    raw: Optional[str],
    holder_map: Mapping[str, str],
    default_holder: Optional[str],
) -> Optional[str]:
    if raw is None:
        return default_holder
    text = str(raw).strip()
    if not text or text == "nan":
        return default_holder
    mapped = holder_map.get(text)
    if mapped is not None:
        return mapped
    return text


def _should_skip_row(row: Mapping[str, str], skip_rules: Sequence[Mapping[str, Any]]) -> bool:
    for rule in skip_rules:
        col = rule.get("when_column")
        if not col:
            continue
        cell = (row.get(str(col)) or "").strip()
        if "equals" in rule and cell == str(rule["equals"]):
            return True
        if "contains" in rule and str(rule["contains"]) in cell:
            return True
    return False


def parse_csv_with_profile(
    content: bytes,
    profile: Mapping[str, Any] | Any,
) -> CsvParseResult:
    """バイト列と取込プロファイルから共通モデル行を返す。

    Raises:
        CsvImportError: デコード失敗、必須列不足、シグネチャ不一致など。
    """
    conf = _as_mapping(profile)
    encoding = str(conf.get("encoding") or "utf-8")
    header_signature = list(conf.get("header_signature") or [])
    column_mapping = dict(conf.get("column_mapping") or {})
    transforms = dict(conf.get("transforms") or {})
    skip_rules = list(conf.get("skip_rules") or [])

    text = _decode_csv(content, encoding)
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    if not headers:
        raise CsvImportError("CSV has no header row")

    if header_signature and not header_signature_matches(headers, header_signature):
        raise CsvImportError("CSV headers do not match header_signature")

    required_fields = ("used_at", "shop_name", "amount")
    for field in required_fields:
        col = column_mapping.get(field)
        if not col:
            raise CsvImportError(f"column_mapping missing required field: {field}")
        if col not in headers:
            raise CsvImportError(f"Mapped column not in CSV header: {col}")

    date_format = str(transforms.get("date_format") or "%Y/%m/%d")
    remove_chars = list(transforms.get("amount_remove_chars") or [])
    holder_map = dict(transforms.get("card_holder_map") or {})
    default_holder = transforms.get("default_card_holder")
    if default_holder is not None:
        default_holder = str(default_holder)

    used_at_col = str(column_mapping["used_at"])
    shop_col = str(column_mapping["shop_name"])
    amount_col = str(column_mapping["amount"])
    holder_col = column_mapping.get("card_holder")
    holder_col = str(holder_col) if holder_col else None

    rows: list[CommonCsvRow] = []
    error_count = 0

    for raw_row in reader:
        row = {k: (v if v is not None else "") for k, v in raw_row.items()}
        if _should_skip_row(row, skip_rules):
            continue

        used_at_raw = str(row.get(used_at_col) or "").strip()
        shop_name = str(row.get(shop_col) or "").strip()
        amount_raw = str(row.get(amount_col) or "").strip()

        if not used_at_raw or not shop_name or not amount_raw:
            continue
        if used_at_raw == "nan" or shop_name == "nan" or amount_raw == "nan":
            continue

        try:
            used_at = datetime.strptime(used_at_raw, date_format).date()
            amount = int(float(_normalize_amount(amount_raw, remove_chars)))
        except ValueError:
            error_count += 1
            continue

        holder_raw = row.get(holder_col) if holder_col else None
        card_holder = _apply_card_holder(
            None if holder_raw is None else str(holder_raw),
            holder_map,
            default_holder,
        )

        rows.append(
            CommonCsvRow(
                used_at=used_at,
                shop_name=shop_name,
                amount=amount,
                card_holder=card_holder,
            )
        )

    return CsvParseResult(rows=rows, error_count=error_count, headers=headers)
