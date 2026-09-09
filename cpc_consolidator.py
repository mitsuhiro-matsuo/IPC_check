"""Build a latest-only CPC match result table."""

from __future__ import annotations

import pandas as pd

from ipc_parser import format_ipc_symbol, normalize_ipc_key


RESULT_COLUMNS = ["対象データ", "入力CPC", "最新CPC記号", "CPC標題", "一致可否"]
REVISION_RESULT_COLUMNS = [
    "対象データ", "入力CPC", "改正時期", "改正種別", "改正種別（日本語）", "改正前CPC", "改正後CPC",
    "改正前標題", "改正後標題", "最新CPC記号", "最新CPC標題", "一致可否",
]
AMENDMENT_TYPE_LABELS = {
    "C": "再分類を伴う分類範囲変更",
    "D": "廃止",
    "E": "分類範囲拡大（他記号から文献を受入、2019.05にTへ移行）",
    "F": "凍結（再分類完了後に廃止予定）",
    "M": "分類範囲変更なしの修正（再分類なし）",
    "N": "再分類を伴う新設",
    "Q": "廃止記号からの行政移管で初期収録された新設",
    "T": "分類範囲拡大（他記号から文献を受入、Eの後継）",
    "U": "変更なし",
}


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def amendment_type_label(value: object) -> str:
    return AMENDMENT_TYPE_LABELS.get(_text(value).upper(), "")


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


def build_revision_result(target: pd.DataFrame, revisions: pd.DataFrame,
                          latest: pd.DataFrame, target_id: object,
                          target_input: object) -> pd.DataFrame:
    """Return matching CPC revisions, keeping latest-only results for other symbols."""
    latest = latest.copy()
    latest["_key"] = latest["CPC記号"].fillna("").astype(str).map(normalize_ipc_key)
    latest_titles = {
        key: _text(description)
        for key, description in zip(latest["_key"], latest["説明"])
        if key
    }
    rows: list[dict[str, str]] = []
    for _, target_row in target.iterrows():
        target_key = normalize_ipc_key(target_row.get("正規化CPC", ""))
        if not target_key:
            continue
        matching_revisions = revisions[
            revisions["改正前CPC"].fillna("").astype(str).map(normalize_ipc_key).eq(target_key)
            | revisions["改正後CPC"].fillna("").astype(str).map(normalize_ipc_key).eq(target_key)
        ]
        matching_revisions = matching_revisions[
            matching_revisions["改正種別"].fillna("").astype(str).str.strip().str.upper().isin(
                {"C", "D", "E", "F", "M", "N", "Q", "T"}
            )
        ]
        latest_matches = latest[latest["_key"] == target_key]
        active = latest_matches[latest_matches["状態"].fillna("").astype(str).str.strip() == "A"]
        latest_match = active.iloc[0] if not active.empty else (latest_matches.iloc[0] if not latest_matches.empty else None)
        latest_symbol = _text(latest_match["CPC記号"]) if latest_match is not None else ""
        latest_title = _text(latest_match["説明"]) if latest_match is not None else ""
        base = {
            "対象データ": _text(target_row[target_id]),
            "入力CPC": format_ipc_symbol(target_row[target_input]),
            "最新CPC記号": latest_symbol,
            "最新CPC標題": latest_title,
            "一致可否": "一致" if latest_match is not None else "不一致",
        }
        if matching_revisions.empty:
            rows.append(base)
            continue
        for _, revision in matching_revisions.iterrows():
            new_key = normalize_ipc_key(revision["改正後CPC"])
            amendment_type = _text(revision["改正種別"])
            rows.append({
                **base,
                "改正時期": _text(revision["改正時期"]),
                "改正種別": amendment_type,
                "改正種別（日本語）": amendment_type_label(amendment_type),
                "改正前CPC": _text(revision["改正前CPC"]),
                "改正後CPC": _text(revision["改正後CPC"]),
                "改正前標題": _text(revision["改正前標題"]),
                "改正後標題": _text(revision["改正後標題"]) or latest_titles.get(new_key, ""),
            })
    return pd.DataFrame(rows, columns=REVISION_RESULT_COLUMNS).drop_duplicates().reset_index(drop=True)