"""DataFrame matching for FI target files."""

from __future__ import annotations

import pandas as pd

from fi_parser import normalize_fi_key, parse_fi


def _text_series(frame: pd.DataFrame, column: object) -> pd.Series:
    return frame[column].fillna("").astype(str).str.strip()


def normalize_column(frame: pd.DataFrame, source_column: object) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = frame.copy()
    parsed = _text_series(result, source_column).map(parse_fi)
    result["正規化FI"] = parsed.map(lambda item: item.normalized or "")
    result["変換エラー"] = parsed.map(lambda item: item.error or "")
    return result, result[result["変換エラー"] != ""].copy()


def add_match_flags(target: pd.DataFrame, revisions: pd.DataFrame, latest: pd.DataFrame) -> pd.DataFrame:
    result = target.copy()
    target_keys = _text_series(result, "正規化FI").map(normalize_fi_key)
    old_keys = set(_text_series(revisions, "改正前FI").map(normalize_fi_key)) - {""}
    new_keys = set(_text_series(revisions, "改正後FI").map(normalize_fi_key)) - {""}
    revision_keys = old_keys | new_keys
    latest_keys = set(_text_series(latest, "FI記号").map(normalize_fi_key)) - {""}
    result["FI改正情報一致"] = target_keys.map(lambda key: "*" if key in revision_keys else "")
    result["最新FI一致"] = target_keys.map(lambda key: "*" if key in latest_keys else "")
    return result