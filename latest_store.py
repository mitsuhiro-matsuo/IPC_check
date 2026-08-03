"""Shared storage and parsing for the IPC8_DAT latest IPC file."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pandas as pd


COLUMNS = ["IPC記号", "階層", "適用期間", "状態", "番号", "説明"]


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _read_metadata(folder: Path) -> list[dict[str, str | int]]:
    path = _metadata_path(folder)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_metadata(folder: Path, records: list[dict[str, str | int]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _metadata_path(folder).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_ipc8_dat(raw: bytes) -> pd.DataFrame:
    """Parse the fixed-width, line-oriented IPC8_DAT format."""
    text = None
    for encoding in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("IPC8_DATを文字コードとして読み込めませんでした")

    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        match = re.match(r"^(?P<symbol>[A-Z]\d{2}[A-Z]\s+\d+/\d+)\s+(?P<level>\d+).*?\[DATE:(?P<date>[^ ]+)\s+STS:(?P<status>[^\]]+)\](?P<number>\d{4})(?P<description>.*)$", line)
        if not match:
            raise ValueError(f"IPC8_DATの{line_number}行目を解析できません: {line[:40]}")
        rows.append({
            "IPC記号": re.sub(r"\s+", " ", match.group("symbol")).strip(),
            "階層": match.group("level"),
            "適用期間": match.group("date"),
            "状態": match.group("status"),
            "番号": match.group("number"),
            "説明": match.group("description").strip(),
        })
    if not rows:
        raise ValueError("IPC8_DATにデータ行がありません")
    return pd.DataFrame(rows, columns=COLUMNS).drop_duplicates()


def list_registered(folder: str | Path = "data/latest_ipc") -> pd.DataFrame:
    records = _read_metadata(Path(folder))
    if not records:
        return pd.DataFrame(columns=["更新時期", "source", "registered_at", "rows", "file"])
    return pd.DataFrame(records).sort_values("更新時期", ascending=False, ignore_index=True)


def registered_data(folder: str | Path = "data/latest_ipc") -> pd.DataFrame:
    folder = Path(folder)
    frames = []
    for record in _read_metadata(folder):
        path = folder / str(record["file"])
        if path.exists():
            frames.append(pd.read_csv(path, dtype=str).reindex(columns=COLUMNS))
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def revision_from_filename(filename: str) -> str:
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", filename)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def register_latest(frame: pd.DataFrame, updated: str, source: str, folder: str | Path = "data/latest_ipc", file_stem: str = "IPC8_DAT") -> dict[str, str | int]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", file_stem)
    filename = f"{safe_stem}_{re.sub(r'[^0-9A-Za-z]', '', updated) or 'latest'}.csv"
    frame.reindex(columns=COLUMNS).to_csv(folder / filename, index=False, encoding="utf-8-sig")
    records = [record for record in _read_metadata(folder) if record["更新時期"] != updated]
    record: dict[str, str | int] = {
        "更新時期": updated,
        "source": source,
        "registered_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "rows": len(frame),
        "file": filename,
    }
    records.append(record)
    _write_metadata(folder, records)
    return record