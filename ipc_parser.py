"""IPC text parsing compatible with the VBA normalization rules."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ParsedIPC:
    original: str
    normalized: str | None
    error: str | None


def _standard_ipc_parts(value: str) -> tuple[str, str, str] | None:
    compact = re.sub(r"\s+", "", value).upper()
    if "/" in compact:
        left, subgroup = compact.split("/", 1)
        match = re.fullmatch(r"([A-Z]\d{2}[A-Z])(\d{1,4})", left)
        if match and subgroup.isdigit() and len(subgroup) <= 6:
            return match.group(1), match.group(2), subgroup
        return None
    match = re.fullmatch(r"([A-Z]\d{2}[A-Z])(\d{1,4})", compact)
    if match:
        return match.group(1), match.group(2), "00"
    match = re.fullmatch(r"([A-Z]\d{2}[A-Z])(\d{4})(\d{6})", compact)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def ipc_main_group_prefix(value: object) -> str:
    """Return the normalized key prefix for a slashless IPC main group."""
    text = "" if value is None else unicodedata.normalize("NFKC", str(value)).strip()
    compact = re.sub(r"\s+", "", text).upper()
    match = re.fullmatch(r"([A-Z]\d{2}[A-Z])(\d{1,4})", compact)
    if not match:
        return ""
    section, main_group = match.groups()
    return f"{section}{main_group.lstrip('0') or '0'}/"


def _standard_comparison_key(parts: tuple[str, str, str]) -> str:
    section, main_group, subgroup = parts
    main_group = main_group.lstrip("0") or "0"
    subgroup = subgroup.rstrip("0") or "0"
    return f"{section}{main_group}/{subgroup}"


def format_ipc_symbol(value: object) -> str:
    """Format fixed-width or standard IPC text without presentation padding."""
    text = "" if value is None else unicodedata.normalize("NFKC", str(value)).strip()
    parts = _standard_ipc_parts(text)
    if not parts:
        return text
    section, main_group, subgroup = parts
    main_group = main_group.lstrip("0") or "0"
    while len(subgroup) > 2 and subgroup.endswith("0"):
        subgroup = subgroup[:-1]
    subgroup = subgroup.zfill(2)
    return f"{section} {main_group}/{subgroup}"


def parse_ipc(value: object) -> ParsedIPC:
    """Normalize year-prefixed IPC values and ordinary IPC symbols."""
    original = "" if value is None else unicodedata.normalize("NFKC", str(value)).strip()
    if not original:
        return ParsedIPC(original, None, "値が空です")

    standard_parts = _standard_ipc_parts(original)
    if standard_parts:
        section, main_group, subgroup = standard_parts
        return ParsedIPC(original, f"{section}{main_group.zfill(4)}/{subgroup}", None)

    slash = original.find("/")
    if slash < 0:
        return ParsedIPC(original, None, "'/' が必要です")

    if slash < 5:
        return ParsedIPC(original, None, "5文字目以降に '/' が必要です")
    year = original[:4]
    classification = re.sub(r"\s+", "", original[4:slash])
    number = re.sub(r"\s+", "", original[slash + 1 :])
    if not year.isdigit() or len(year) != 4:
        return ParsedIPC(original, None, "先頭4文字が年ではありません")
    if not classification:
        return ParsedIPC(original, None, "分類コードが空です")
    if not number or not number.isdigit():
        return ParsedIPC(original, None, "番号が数字ではありません")
    if len(classification) > 4:
        return ParsedIPC(original, None, "分類コードが4文字を超えています")
    if len(number) > 6:
        return ParsedIPC(original, None, "番号が6桁を超えています")
    # Treat leading zeroes as presentation padding too.  Thus ``1`` and
    # ``0001`` (and ``456`` and ``000456``) produce the same comparison key.
    if classification.isdigit():
        classification = classification.lstrip("0") or "0"
    number = number.lstrip("0") or "0"
    return ParsedIPC(original, year + classification.zfill(4) + number.ljust(6, "0"), None)


def normalize_ipc_key(value: object) -> str:
    """Return one comparison key for raw or already-normalized IPC values."""
    text = "" if value is None else unicodedata.normalize("NFKC", str(value)).strip()
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return ""

    standard_parts = _standard_ipc_parts(text)
    if standard_parts:
        return _standard_comparison_key(standard_parts)

    # Workbook reference sheets commonly already contain the 14-character key.
    if len(compact) == 14 and compact[:4].isdigit():
        classification = compact[4:8]
        number = compact[8:]
        if classification.isdigit():
            classification = classification.lstrip("0") or "0"
        number = number.lstrip("0") or "0"
        return compact[:4] + classification.zfill(4) + number.ljust(6, "0")
    parsed = parse_ipc(text)
    return parsed.normalized or ""