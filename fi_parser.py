"""Parsing and comparison keys for Japanese FI classification symbols."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

@dataclass(frozen=True)
class ParsedFI:
    original: str
    normalized: str | None
    error: str | None


def _text(value: object) -> str:
    return "" if value is None else unicodedata.normalize("NFKC", str(value)).strip()


def parse_fi(value: object) -> ParsedFI:
    """Normalize an FI symbol while preserving expansion and booklet tokens."""
    original = _text(value)
    if not original:
        return ParsedFI(original, None, "値が空です")

    match = re.fullmatch(
        r"\s*(?P<section>[A-Z]\s*\d{2}\s*[A-Z])\s*(?P<main>\d{1,4})\s*/\s*(?P<subgroup>\d{1,6})(?P<attached>[A-Z])?(?:\s+(?P<expansion>[A-Z0-9]+))?(?:\s+(?P<booklet>[A-Z]))?\s*",
        original.upper(),
    )
    if not match:
        return ParsedFI(original, None, "FI記号の形式ではありません")

    section = re.sub(r"\s+", "", match.group("section"))
    main = match.group("main").lstrip("0") or "0"
    subgroup = match.group("subgroup").zfill(2)
    group_key = f"{section}{main}/{subgroup}"
    expansion = match.group("expansion") or ""
    booklet = match.group("booklet") or ""
    expansion_with_booklet = re.fullmatch(r"(\d+)([A-Z])", expansion)
    if expansion_with_booklet and not booklet:
        expansion, booklet = expansion_with_booklet.groups()
    suffix = " ".join(part for part in (match.group("attached"), expansion, booklet) if part)
    return ParsedFI(original, f"{group_key} {suffix}".strip(), None)


def normalize_fi_key(value: object) -> str:
    """Return a stable comparison key for an FI symbol or an empty string."""
    return parse_fi(value).normalized or ""


def format_fi_symbol(value: object) -> str:
    """Format an FI symbol for display without fixed-width padding."""
    parsed = parse_fi(value)
    if not parsed.normalized:
        return parsed.original
    match = re.fullmatch(r"(?P<section>[A-Z]\d{2}[A-Z])(?P<main>\d+)/(?P<subgroup>\d+)(?:\s+(?P<suffix>.*))?", parsed.normalized)
    if not match:
        return parsed.original
    suffix = match.group("suffix")
    return f"{match.group('section')} {match.group('main')}/{match.group('subgroup')}" + (f" {suffix}" if suffix else "")