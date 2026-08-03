"""Build the result table produced by the VBA macro."""

from __future__ import annotations

import pandas as pd

from ipc_parser import format_ipc_symbol, ipc_main_group_prefix, normalize_ipc_key


RESULT_COLUMNS = [
    "対象データ",
    "from-version",
    "to-version",
    "from-symbol",
    "modification",
    "to-symbol",
    "modification2",
    "to-symbolの内容",
]

MODIFICATION_LABELS = {
    "d": "d：廃止",
    "c": "c：主題事項の変更",
    "s": "s：変更されていないが再分類の源として利用",
}

MODIFICATION2_LABELS = {
    "c": "c：主題事項の変更",
    "n": "n：新設",
    "t": "t：変更されていないが移行先となるもの",
}


def _column(frame: pd.DataFrame, names: tuple[str, ...], index: int) -> object | None:
    for name in names:
        if name in frame.columns:
            return name
    return frame.columns[index] if frame.shape[1] > index else None


def _value(row: pd.Series | None, column: object | None) -> object:
    if row is None or column is None or column not in row.index or pd.isna(row[column]):
        return ""
    return row[column]


def _modification(value: object, labels: dict[str, str]) -> str:
    code = "" if pd.isna(value) else str(value).strip().lower()
    return labels.get(code, code)


def build_result(target: pd.DataFrame, old: pd.DataFrame, latest: pd.DataFrame,
                 old_key: object, latest_key: object, old_number: object | None = None,
                 target_id: object | None = None, target_input: object | None = None) -> pd.DataFrame:
    target = target.copy()
    old = old.copy()
    latest = latest.copy()
    target_keys = target["正規化IPC"].fillna("").astype(str).map(normalize_ipc_key)
    old_keys = old[old_key].fillna("").astype(str).str.strip().map(normalize_ipc_key)
    latest_keys = latest[latest_key].fillna("").astype(str).str.strip().map(normalize_ipc_key)
    if not target.columns.size or not latest.columns.size:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    target_id = target_id if target_id is not None else target.columns[min(1, len(target.columns) - 1)]
    target_input = target_input if target_input is not None else target.columns[min(2, len(target.columns) - 1)]
    from_version = _column(old, ("from-version", "改正前バージョン"), 0)
    to_version = _column(old, ("to-version", "改正後バージョン"), 1)
    from_symbol = _column(old, ("from-symbol", "改正前記号"), 2)
    old_attribute = _column(old, ("modification", "属性1"), 3)
    destination = _column(old, ("to-symbol", "改正後記号"), 4)
    destination_attribute = _column(old, ("modification2", "属性2"), 5)
    latest_meaning = "説明" if "説明" in latest.columns else None
    rows: list[dict[str, object]] = []

    for target_index, target_row in target.iterrows():
        key = target_keys.loc[target_index]
        if not key:
            continue
        direct_latest = latest[latest_keys == key]
        group_prefix = ipc_main_group_prefix(target_row[target_input])
        revision_rows = old[old_keys.str.startswith(group_prefix)] if group_prefix else old[old_keys == key]
        if not revision_rows.empty and to_version is not None:
            versions = revision_rows[to_version].fillna("").astype(str).str.strip()
            revision_rows = revision_rows[versions == versions.max()]
        candidates: list[tuple[pd.Series, pd.Series | None]] = []
        if not revision_rows.empty and destination is not None:
            for _, revision_row in revision_rows.iterrows():
                destination_key = normalize_ipc_key(revision_row[destination])
                destination_latest = latest[latest_keys == destination_key]
                if destination_latest.empty:
                    candidates.append((pd.Series(dtype=object), revision_row))
                else:
                    candidates.extend(
                        (latest_row, revision_row)
                        for _, latest_row in destination_latest.iterrows()
                    )
        else:
            candidates.extend((latest_row, None) for _, latest_row in direct_latest.iterrows())

        for latest_row, revision_row in candidates:
            latest_symbol = _value(latest_row, latest_key)
            to_symbol = _value(revision_row, destination) or latest_symbol
            rows.append({
                "対象データ": target_row[target_id],
                "from-version": _value(revision_row, from_version),
                "to-version": _value(revision_row, to_version),
                "from-symbol": format_ipc_symbol(_value(revision_row, from_symbol)),
                "modification": _modification(_value(revision_row, old_attribute), MODIFICATION_LABELS),
                "to-symbol": format_ipc_symbol(to_symbol),
                "modification2": _modification(_value(revision_row, destination_attribute), MODIFICATION2_LABELS),
                "to-symbolの内容": _value(latest_row, latest_meaning),
            })
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)