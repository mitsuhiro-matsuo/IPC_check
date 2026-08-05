"""Persistent storage and parsing for FI revision workbooks."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re

import pandas as pd

from fi_parser import format_fi_symbol, normalize_fi_key


COLUMNS = ["改正時期", "改正種別", "改正前FI", "改正後FI", "改正前タイトル", "改正後タイトル"]
SHEET_TYPES = {"新設": "新設", "廃止": "廃止", "タイトル変更": "タイトル変更", "ドット変更": "ドット変更"}


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _read_metadata(folder: Path) -> list[dict[str, str | int]]:
    path = _metadata_path(folder)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        records = json.loads(text)
    except json.JSONDecodeError as exc:
        records, end = json.JSONDecoder().raw_decode(text)
        if not isinstance(records, list) or not text[end:].strip():
            raise ValueError(f"FI改正情報のメタデータを読み込めません: {exc}") from exc
        _write_metadata(folder, records)
    if not isinstance(records, list):
        raise ValueError("FI改正情報のメタデータ形式が不正です")
    return records


def _write_metadata(folder: Path, records: list[dict[str, str | int]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = _metadata_path(folder)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _cell(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text in {"\\", "－", "-"} else text


def _fi_symbol(group: object, expansion: object = "", booklet: object = "") -> str:
    parts = [_cell(group), _cell(expansion), _cell(booklet)]
    raw = " ".join(part for part in parts if part)
    key = normalize_fi_key(raw)
    return format_fi_symbol(key) if key else raw


def _standard_rows(frame: pd.DataFrame, revision: str, change_type: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, row in frame.iloc[2:].iterrows():
        values = [_cell(value) for value in row.tolist()]
        if not any(values):
            continue
        if change_type == "廃止":
            old_symbol = _fi_symbol(*values[1:4])
            new_symbol = _fi_symbol(*values[5:8])
            old_title = values[4] if len(values) > 4 else ""
            new_title = values[8] if len(values) > 8 else ""
        else:
            new_symbol = _fi_symbol(*values[1:4])
            old_symbol = new_symbol if change_type in {"タイトル変更", "ドット変更"} else ""
            new_title = values[4] if len(values) > 4 else ""
            old_title = values[5] if len(values) > 5 else ""
        if not old_symbol and not new_symbol:
            continue
        rows.append({
            "改正時期": revision,
            "改正種別": change_type,
            "改正前FI": old_symbol,
            "改正後FI": new_symbol,
            "改正前タイトル": old_title,
            "改正後タイトル": new_title,
        })
    return rows


def parse_revision_workbook(raw: bytes, revision: str) -> pd.DataFrame:
    """Convert the four standard FI workbook sheets to common revision records."""
    sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None, dtype=str, engine="xlrd")
    records: list[dict[str, str]] = []
    for sheet_name, change_type in SHEET_TYPES.items():
        if sheet_name in sheets:
            records.extend(_standard_rows(sheets[sheet_name], revision, change_type))
    if not records:
        expected = "、".join(SHEET_TYPES)
        raise ValueError(f"FI改正ブックに対象シートがありません: {expected}")
    return pd.DataFrame(records, columns=COLUMNS).drop_duplicates().reset_index(drop=True)


def revision_from_filename(filename: str) -> str:
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", filename)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def list_registered(folder: str | Path = "data/fi_revisions") -> pd.DataFrame:
    records = _read_metadata(Path(folder))
    if not records:
        return pd.DataFrame(columns=["revision", "source", "registered_at", "rows", "file"])
    return pd.DataFrame(records).sort_values("revision", ascending=False, ignore_index=True)


def registered_data(folder: str | Path = "data/fi_revisions") -> pd.DataFrame:
    folder = Path(folder)
    frames = [pd.read_csv(folder / str(item["file"]), dtype=str) for item in _read_metadata(folder) if (folder / str(item["file"])).exists()]
    return pd.concat(frames, ignore_index=True).reindex(columns=COLUMNS).drop_duplicates() if frames else pd.DataFrame(columns=COLUMNS)


def register_revision(frame: pd.DataFrame, revision: str, source: str, folder: str | Path = "data/fi_revisions", file_stem: str = "fi") -> dict[str, str | int]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{re.sub(r'[^A-Za-z0-9_.-]', '_', file_stem)}_{revision.replace('.', '')}.csv"
    frame.reindex(columns=COLUMNS).to_csv(folder / filename, index=False, encoding="utf-8-sig")
    records = [record for record in _read_metadata(folder) if record["revision"] != revision]
    record: dict[str, str | int] = {
        "revision": revision,
        "source": source,
        "registered_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "rows": len(frame),
        "file": filename,
    }
    records.append(record)
    _write_metadata(folder, records)
    return record