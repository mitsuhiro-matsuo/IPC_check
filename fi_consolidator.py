"""Build a unified FI revision result table."""

from __future__ import annotations

import pandas as pd

from fi_parser import format_fi_symbol, normalize_fi_key


RESULT_COLUMNS = ["対象データ", "改正時期", "改正種別", "改正前FI", "改正後FI", "改正前タイトル", "改正後タイトル"]


def build_result(target: pd.DataFrame, revisions: pd.DataFrame, latest: pd.DataFrame, target_id: object) -> pd.DataFrame:
    latest_titles = {
        normalize_fi_key(symbol): title
        for symbol, title in zip(latest.get("FI記号", pd.Series(dtype=str)), latest.get("説明", pd.Series(dtype=str)))
        if normalize_fi_key(symbol)
    }
    rows: list[dict[str, object]] = []
    for _, target_row in target.iterrows():
        target_key = normalize_fi_key(target_row["正規化FI"])
        if not target_key:
            continue
        for _, revision in revisions.iterrows():
            old_key = normalize_fi_key(revision["改正前FI"])
            new_key = normalize_fi_key(revision["改正後FI"])
            matches = old_key == target_key or (revision["改正種別"] == "新設" and new_key == target_key)
            if not matches:
                continue
            old_title = revision["改正前タイトル"]
            new_title = revision["改正後タイトル"] or latest_titles.get(new_key, "")
            rows.append({
                "対象データ": target_row[target_id],
                "改正時期": revision["改正時期"],
                "改正種別": revision["改正種別"],
                "改正前FI": format_fi_symbol(revision["改正前FI"]),
                "改正後FI": format_fi_symbol(revision["改正後FI"]),
                "改正前タイトル": old_title,
                "改正後タイトル": new_title,
            })
    return pd.DataFrame(rows, columns=RESULT_COLUMNS).drop_duplicates().reset_index(drop=True)