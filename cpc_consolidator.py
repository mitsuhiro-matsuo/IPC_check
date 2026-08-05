"""Build a latest-only CPC match result table."""

from __future__ import annotations

import pandas as pd

from ipc_parser import format_ipc_symbol, normalize_ipc_key


RESULT_COLUMNS = ["対象データ", "入力CPC", "最新CPC記号", "CPC標題", "一致可否"]


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def build_result(target: pd.DataFrame, latest: pd.DataFrame, target_id: object,
                 target_input: object) -> pd.DataFrame:
    """Return one result per valid target CPC, including unmatched values."""
    latest = latest.copy()
    latest["_key"] = latest["CPC記号"].fillna("").astype(str).map(normalize_ipc_key)
    rows: list[dict[str, str]] = []
    for _, target_row in target.iterrows():
        key = normalize_ipc_key(target_row.get("正規化CPC", ""))
        if not key:
            continue
        candidates = latest[latest["_key"] == key]
        if not candidates.empty:
            active = candidates[candidates["状態"].fillna("").astype(str).str.strip() == "A"]
            match = active.iloc[0] if not active.empty else candidates.iloc[0]
            rows.append({
                "対象データ": _text(target_row[target_id]),
                "入力CPC": format_ipc_symbol(target_row[target_input]),
                "最新CPC記号": _text(match["CPC記号"]),
                "CPC標題": _text(match["説明"]),
                "一致可否": "一致",
            })
        else:
            rows.append({
                "対象データ": _text(target_row[target_id]),
                "入力CPC": format_ipc_symbol(target_row[target_input]),
                "最新CPC記号": "",
                "CPC標題": "",
                "一致可否": "不一致",
            })
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)