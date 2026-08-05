"""Latest-only matching for CPC target files."""

from __future__ import annotations

import pandas as pd

from ipc_parser import normalize_ipc_key, parse_ipc


def _text_series(frame: pd.DataFrame, column: object) -> pd.Series:
    return frame[column].fillna("").astype(str).str.strip()


def normalize_column(frame: pd.DataFrame, source_column: object) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = frame.copy()
    parsed = _text_series(result, source_column).map(parse_ipc)
    result["正規化CPC"] = parsed.map(lambda item: item.normalized or "")
    result["変換エラー"] = parsed.map(lambda item: item.error or "")
    return result, result[result["変換エラー"] != ""].copy()


def add_match_flags(target: pd.DataFrame, latest: pd.DataFrame) -> pd.DataFrame:
    result = target.copy()
    target_keys = _text_series(result, "正規化CPC").map(normalize_ipc_key)
    latest_keys = set(_text_series(latest, "CPC記号").map(normalize_ipc_key)) - {""}
    result["最新CPC一致"] = target_keys.map(lambda key: "*" if key in latest_keys else "")
    return result