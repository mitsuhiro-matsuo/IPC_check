"""Persistent storage and official downloads for IPC revision information."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import zipfile

import pandas as pd

from ipc_parser import parse_ipc


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _read_metadata(folder: Path) -> list[dict[str, str | int]]:
    path = _metadata_path(folder)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_metadata(folder: Path, metadata: list[dict[str, str | int]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _metadata_path(folder).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def list_registered(folder: str | Path = "data/ipc_revisions") -> pd.DataFrame:
    records = _read_metadata(Path(folder))
    if not records:
        return pd.DataFrame(columns=["revision", "source", "registered_at", "rows", "file"])
    return pd.DataFrame(records).sort_values("revision", ascending=False, ignore_index=True)


def registered_data(folder: str | Path = "data/ipc_revisions") -> pd.DataFrame:
    folder = Path(folder)
    files = [folder / str(item["file"]) for item in _read_metadata(folder)]
    frames = [pd.read_csv(path, dtype=str) for path in files if path.exists()]
    if not frames:
        return pd.DataFrame(columns=["改正前バージョン", "改正後バージョン", "改正前記号", "属性1", "改正後記号", "属性2"])
    return normalize_revision_frame(pd.concat(frames, ignore_index=True).drop_duplicates())


def normalize_revision_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Insert the IPC slash in the third and fifth columns."""
    result = frame.copy()
    if result.shape[1] < 5:
        return result
    for column_index in (2, 4):
        column = result.columns[column_index]
        result[column] = result[column].map(
            lambda value: parse_ipc(value).normalized or value
        )
    return result


def _parse_revision_csv(raw: bytes, filename: str) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            frame = pd.read_csv(io.BytesIO(raw), header=None, dtype=str, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"CSVを読み込めませんでした: {filename}")
    if frame.shape[1] < 6:
        raise ValueError(f"CSVの列数が6列未満です: {filename}")
    frame = frame.iloc[:, :6].fillna("")
    frame.columns = ["改正前バージョン", "改正後バージョン", "改正前記号", "属性1", "改正後記号", "属性2"]
    return normalize_revision_frame(frame)


def parse_revision_zip(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("ZIP内にCSVファイルがありません")
        return pd.concat([_parse_revision_csv(archive.read(name), name) for name in csv_names], ignore_index=True).drop_duplicates()


def revision_from_filename(filename: str) -> str:
    match = re.search(r"(?:rcl[_-])?(20\d{2})(0[1-9]|1[0-2])", filename, re.IGNORECASE)
    if not match:
        return ""
    return f"{match.group(1)}.{match.group(2)}"


def parse_revision_csv(raw: bytes) -> pd.DataFrame:
    return _parse_revision_csv(raw, "uploaded.csv")


def register_revision(frame: pd.DataFrame, revision: str, source: str, folder: str | Path = "data/ipc_revisions", source_url: str = "", file_stem: str = "uploaded") -> dict[str, str | int]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    frame = normalize_revision_frame(frame)
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", file_stem)
    filename = f"{safe_stem}_{revision.replace('.', '')}.csv"
    frame.to_csv(folder / filename, index=False, encoding="utf-8-sig")
    metadata = _read_metadata(folder)
    metadata = [item for item in metadata if item["revision"] != revision]
    record: dict[str, str | int] = {
        "revision": revision,
        "source": source,
        "source_url": source_url,
        "registered_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "rows": len(frame),
        "file": filename,
    }
    metadata.append(record)
    _write_metadata(folder, metadata)
    return record