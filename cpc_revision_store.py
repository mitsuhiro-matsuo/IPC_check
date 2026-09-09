"""Official CPC revision download, XML parsing, and persistent storage."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from ipc_parser import format_ipc_symbol, normalize_ipc_key


COLUMNS = [
    "改正時期", "改正種別", "改正前CPC", "改正後CPC", "改正前標題", "改正後標題", "資料種別",
]
ARCHIVE_URL = "https://www.cooperativepatentclassification.org/Archive"
BULK_URL = "https://www.cooperativepatentclassification.org/cpcSchemeAndDefinitions/bulk"
USER_AGENT = "Mozilla/5.0 (compatible; CPC-Revision-Checker/1.0)"

KNOWN_TITLE_SYMBOL_CORRECTIONS = {
    ("A61F 2/06", "Artificial legs or feet or parts thereof"): "A61F 2/60",
}


def _metadata_path(folder: Path) -> Path:
    return folder / "metadata.json"


def _read_metadata(folder: Path) -> list[dict[str, str | int]]:
    path = _metadata_path(folder)
    if not path.exists():
        return []
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"CPC改正情報のメタデータを読み込めません: {exc}") from exc
    if not isinstance(records, list):
        raise ValueError("CPC改正情報のメタデータ形式が不正です")
    return records


def _write_metadata(folder: Path, records: list[dict[str, str | int]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = _metadata_path(folder)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child) == name:
            return "".join(child.itertext()).strip()
    return ""


def _symbol(value: object) -> str:
    key = normalize_ipc_key(value)
    return format_ipc_symbol(key) if key else ""


def _correct_title_symbol(symbol: str, title: str) -> str:
    return KNOWN_TITLE_SYMBOL_CORRECTIONS.get((symbol, title), symbol)


def revision_from_filename(filename: str) -> str:
    match = re.search(r"(20\d{2})(0[1-9]|1[0-2])", filename)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def _rcl_rows(root: ET.Element, revision: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in root.iter():
        if _local_name(item) != "revision-concordance-item":
            continue
        old_symbol = _symbol(_child_text(item, "classification-symbol"))
        targets = [
            _symbol("".join(target.itertext()).strip())
            for target in item.iter()
            if _local_name(target) == "target-symbol"
        ]
        for new_symbol in targets or [""]:
            if old_symbol or new_symbol:
                rows.append({
                    "改正時期": revision,
                    "改正種別": item.get("amendment-type", ""),
                    "改正前CPC": old_symbol,
                    "改正後CPC": new_symbol,
                    "改正前標題": "",
                    "改正後標題": "",
                    "資料種別": "Revision Concordance List",
                })
    return rows


def _compilation_rows(root: ET.Element, revision: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in root.iter():
        if _local_name(item) != "compilation-item":
            continue
        symbol = _symbol(_child_text(item, "classification-symbol"))
        if not symbol:
            continue
        title = _child_text(item, "title")
        symbol = _correct_title_symbol(symbol, title)
        rows.append({
            "改正時期": revision,
            "改正種別": item.get("amendment-type", ""),
            "改正前CPC": symbol,
            "改正後CPC": symbol,
            "改正前標題": title,
            "改正後標題": title,
            "資料種別": "Compilation of Changes",
        })
    return rows


def _scheme_xml_documents(raw: bytes) -> list[bytes]:
    """Return scheme XML documents, including the section ZIPs in the launch file."""
    documents: list[bytes] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            content = archive.read(name)
            if name.lower().endswith(".xml"):
                documents.append(content)
            elif name.lower().endswith(".zip"):
                try:
                    documents.extend(_scheme_xml_documents(content))
                except zipfile.BadZipFile:
                    continue
    return documents


def parse_cpc_scheme_zip(raw: bytes) -> pd.DataFrame:
    """Extract CPC symbols, titles, and revision dates from an official Scheme XML ZIP."""
    records: list[dict[str, str]] = []
    for document in _scheme_xml_documents(raw):
        try:
            root = ET.fromstring(document)
        except ET.ParseError:
            continue
        for item in root.iter():
            if _local_name(item) != "classification-item":
                continue
            symbol = _symbol(_child_text(item, "classification-symbol"))
            if not symbol:
                continue
            title = _child_text(item, "class-title")
            records.append({
                "CPC": symbol,
                "標題": title,
                "更新日": item.get("date-revised", ""),
            })
    if not records:
        raise ValueError("ZIP内にCPC Scheme XMLがありません")
    return pd.DataFrame(records).drop_duplicates(subset="CPC", keep="last").reset_index(drop=True)


def build_scheme_revision_rows(previous: pd.DataFrame, current: pd.DataFrame,
                               revision: str) -> pd.DataFrame:
    """Infer additions, deletions, and title changes between two Scheme snapshots."""
    previous_titles = dict(zip(previous["CPC"], previous["標題"]))
    current_titles = dict(zip(current["CPC"], current["標題"]))
    records: list[dict[str, str]] = []
    for symbol in sorted(set(previous_titles) - set(current_titles)):
        records.append(_scheme_revision_record(revision, "D", symbol, "", previous_titles[symbol], ""))
    for symbol in sorted(set(current_titles) - set(previous_titles)):
        records.append(_scheme_revision_record(revision, "N", "", symbol, "", current_titles[symbol]))
    for symbol in sorted(set(previous_titles) & set(current_titles)):
        if previous_titles[symbol] != current_titles[symbol]:
            records.append(_scheme_revision_record(revision, "M", symbol, symbol, previous_titles[symbol], current_titles[symbol]))
    return pd.DataFrame(records, columns=COLUMNS)


def _scheme_revision_record(revision: str, amendment_type: str, old_symbol: str,
                            new_symbol: str, old_title: str, new_title: str) -> dict[str, str]:
    return {
        "改正時期": revision,
        "改正種別": amendment_type,
        "改正前CPC": old_symbol,
        "改正後CPC": new_symbol,
        "改正前標題": old_title,
        "改正後標題": new_title,
        "資料種別": "Scheme XML差分（推定）",
    }


def build_initial_scheme_revision_rows(snapshot: pd.DataFrame, revision: str) -> pd.DataFrame:
    """Create inferred revision rows for items explicitly marked revised in the first snapshot."""
    date_prefix = revision.replace(".", "-")
    changed = snapshot[snapshot["更新日"].fillna("").astype(str).str.startswith(date_prefix)]
    records = [
        _scheme_revision_record(revision, "M", row.CPC, row.CPC, "", row.標題)
        for row in changed.itertuples(index=False)
    ]
    return pd.DataFrame(records, columns=COLUMNS)


def parse_cpc_revision_zip(raw: bytes, revision: str = "") -> pd.DataFrame:
    """Parse official RCL and Compilation XML documents from one CPC ZIP file."""
    records: list[dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        for name in xml_names:
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError as exc:
                raise ValueError(f"CPC改正XMLを読み込めませんでした: {name}") from exc
            root_name = _local_name(root)
            if root_name == "revision-concordance-table":
                records.extend(_rcl_rows(root, revision))
            elif root_name == "scheme-compilation":
                records.extend(_compilation_rows(root, revision))
    if not records:
        raise ValueError("ZIP内にCPC改正情報のXMLがありません")
    return pd.DataFrame(records, columns=COLUMNS).drop_duplicates().reset_index(drop=True)


def _open_url(url: str, timeout: int):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def download_official_file(url: str, timeout: int = 60) -> bytes:
    try:
        with _open_url(url, timeout) as response:
            return response.read()
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"CPC公式ファイルを取得できませんでした: {url}") from exc


def _official_links(page_url: str) -> list[str]:
    try:
        with _open_url(page_url, 30) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"CPC公式ページを取得できませんでした: {page_url}") from exc
    links = re.findall(r'href="([^"]+)"', page, flags=re.IGNORECASE)
    return [
        urljoin(page_url, link)
        for link in links
        if re.search(r"(?:Compilation|CPCNoticeOfChangeXMLArtefact)\d{6}.*\.zip", link, re.IGNORECASE)
    ]


def list_official_releases() -> pd.DataFrame:
    """Return downloadable RCL/Compilation releases, preferring RCL per period."""
    releases: dict[str, dict[str, str]] = {}
    for page_url in (ARCHIVE_URL, BULK_URL):
        for url in _official_links(page_url):
            revision = revision_from_filename(url)
            if not revision or revision < "2014.06":
                continue
            source_type = "Revision Concordance List" if "CPCNoticeOfChange" in url else "Compilation of Changes"
            current = releases.get(revision)
            if current is None or source_type == "Revision Concordance List":
                releases[revision] = {"revision": revision, "資料種別": source_type, "url": url}
    return pd.DataFrame(releases.values(), columns=["revision", "資料種別", "url"]).sort_values(
        "revision", ascending=False, ignore_index=True
    ) if releases else pd.DataFrame(columns=["revision", "資料種別", "url"])


def list_registered(folder: str | Path = "data/cpc_revisions") -> pd.DataFrame:
    records = _read_metadata(Path(folder))
    columns = ["revision", "source", "registered_at", "rows", "file", "source_url"]
    return pd.DataFrame(records).sort_values("revision", ascending=False, ignore_index=True) if records else pd.DataFrame(columns=columns)


def registered_data(folder: str | Path = "data/cpc_revisions") -> pd.DataFrame:
    folder = Path(folder)
    frames = [pd.read_csv(folder / str(item["file"]), dtype=str) for item in _read_metadata(folder) if (folder / str(item["file"])).exists()]
    return pd.concat(frames, ignore_index=True).reindex(columns=COLUMNS).drop_duplicates() if frames else pd.DataFrame(columns=COLUMNS)


def register_revision(frame: pd.DataFrame, revision: str, source: str, folder: str | Path = "data/cpc_revisions", source_url: str = "", file_stem: str = "cpc_revision") -> dict[str, str | int]:
    if not revision:
        raise ValueError("CPC改正時期をファイル名またはURLから判定できません")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{re.sub(r'[^A-Za-z0-9_.-]', '_', file_stem)}_{revision.replace('.', '')}.csv"
    frame.reindex(columns=COLUMNS).to_csv(folder / filename, index=False, encoding="utf-8-sig")
    records = [record for record in _read_metadata(folder) if record["revision"] != revision]
    record: dict[str, str | int] = {
        "revision": revision,
        "source": source,
        "source_url": source_url,
        "registered_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "rows": len(frame),
        "file": filename,
    }
    records.append(record)
    _write_metadata(folder, records)
    return record