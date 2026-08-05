"""Shared storage and parsing for the fixed-width FI_DAT file."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pandas as pd

from fi_parser import format_fi_symbol, normalize_fi_key


COLUMNS = ["FI記号", "階層", "適用期間", "状態", "番号", "説明"]
LEGACY_SYMBOL_CORRECTIONS = {
    ("C09K 3/01 C", "ゴム一般用[FTM:4H017]"): "C09K 3/10 C",
}


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _read_metadata(folder: Path) -> list[dict[str, str | int]]:
    path = _metadata_path(folder)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write_metadata(folder: Path, records: list[dict[str, str | int]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _metadata_path(folder).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_fi_dat(raw: bytes) -> pd.DataFrame:
    """Parse line-oriented FI_DAT without dropping FI expansion identifiers."""
    text = None
    for encoding in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("FI_DATを文字コードとして読み込めませんでした")

    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<prefix>.*?)\s*(?P<level>\d+)\s*\[DATE:(?P<date>[^ ]+)\s+STS:(?P<status>[^\]]+)\]"
        r"(?P<number>\d{4})(?P<description>.*)$"
    )
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        line = line.rstrip("\r\n")
        match = pattern.match(line)
        if not match:
            fallback = re.match(
                r"^(?P<prefix>.*?)\s*\[DATE:(?P<date>[^ ]+)\s+STS:(?P<status>[^\]]+)\]"
                r"(?P<number>\d{4})(?P<description>.*)$",
                line,
            )
            if not fallback:
                if rows:
                    rows[-1]["説明"] = f"{rows[-1]['説明']} {line.strip()}".strip()
                    continue
                raise ValueError(f"FI_DATの{line_number}行目にDATE情報がありません: {line[:60]}")
            prefix = fallback.group("prefix").strip()
            level_match = re.match(r"^(?P<symbol>.*?)(?:\s+)(?P<level>\d+)$", prefix)
            symbol_text = level_match.group("symbol") if level_match else prefix
            level = level_match.group("level") if level_match else ""
            match_data = fallback.groupdict()
        else:
            symbol_text = match.group("prefix")
            level = match.group("level")
            match_data = match.groupdict()
        symbol = format_fi_symbol(symbol_text)
        if not normalize_fi_key(symbol):
            symbol = re.sub(r"\s+", " ", symbol_text).strip()
        rows.append({
            "FI記号": symbol,
            "階層": level,
            "適用期間": match_data["date"],
            "状態": match_data["status"],
            "番号": match_data["number"],
            "説明": match_data["description"].strip(),
        })
    if not rows:
        raise ValueError("FI_DATにデータ行がありません")
    return pd.DataFrame(rows, columns=COLUMNS).drop_duplicates()


def revision_from_filename(filename: str) -> str:
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", filename)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def list_registered(folder: str | Path = "data/latest_fi") -> pd.DataFrame:
    records = _read_metadata(Path(folder))
    if not records:
        return pd.DataFrame(columns=["更新時期", "source", "registered_at", "rows", "file"])
    return pd.DataFrame(records).sort_values("更新時期", ascending=False, ignore_index=True)


def registered_data(folder: str | Path = "data/latest_fi") -> pd.DataFrame:
    folder = Path(folder)
    frames = []
    for item in _read_metadata(folder):
        path = folder / str(item["file"])
        if not path.exists():
            continue
        frame = pd.read_csv(path, dtype=str).reindex(columns=COLUMNS)
        corrected = False
        for (legacy_symbol, description), corrected_symbol in LEGACY_SYMBOL_CORRECTIONS.items():
            mask = (frame["FI記号"] == legacy_symbol) & (frame["説明"] == description)
            if mask.any():
                frame.loc[mask, "FI記号"] = corrected_symbol
                corrected = True
        if corrected:
            frame.to_csv(path, index=False, encoding="utf-8-sig")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame(columns=COLUMNS)


def register_latest(frame: pd.DataFrame, updated: str, source: str, folder: str | Path = "data/latest_fi", file_stem: str = "FI_DAT") -> dict[str, str | int]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{re.sub(r'[^A-Za-z0-9_.-]', '_', file_stem)}_{re.sub(r'[^0-9A-Za-z]', '', updated) or 'latest'}.csv"
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