import io
import zipfile

import pandas as pd

from cpc_consolidator import RESULT_COLUMNS, REVISION_RESULT_COLUMNS, amendment_type_label, build_result, build_revision_result
from cpc_latest_store import list_registered, parse_cpc_dat, register_latest, registered_data
from cpc_matcher import add_match_flags, normalize_column
from cpc_revision_store import COLUMNS as REVISION_COLUMNS
from cpc_revision_store import list_registered as list_revision_registered
from cpc_revision_store import build_scheme_revision_rows, parse_cpc_revision_zip, parse_cpc_scheme_zip, register_revision, registered_data as registered_revision_data


def _revision_zip() -> bytes:
    rcl = b'''<revision-concordance-table>
        <revision-concordance-item amendment-type="D">
            <classification-symbol>A01B1/00</classification-symbol>
            <transferred-to><target-symbol>A01B1/02</target-symbol></transferred-to>
        </revision-concordance-item>
    </revision-concordance-table>'''
    compilation = b'''<scheme-compilation>
        <compilation-item amendment-type="M">
            <classification-symbol>A01B1/04</classification-symbol><title>Updated title</title>
        </compilation-item>
    </scheme-compilation>'''
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("RP10000-rcl.xml", rcl)
        archive.writestr("cpc-compilation.xml", compilation)
    return raw.getvalue()


def test_cpc_dat_parses_sts_records_without_a_date_field():
    raw = "A01B   1/00     00[STS:A]0051Hand tools\n".encode("cp932")
    frame = parse_cpc_dat(raw)
    assert frame.loc[0, "CPC記号"] == "A01B 1/00"
    assert frame.loc[0, "階層"] == "00"
    assert frame.loc[0, "状態"] == "A"
    assert frame.loc[0, "説明"] == "Hand tools"


def test_cpc_dat_keeps_records_when_descriptions_have_invalid_cp932_bytes():
    raw = b"A01B   1/00     00[STS:A]0051Hand tools \x81\n"
    frame = parse_cpc_dat(raw)
    assert frame.loc[0, "CPC記号"] == "A01B 1/00"


def test_cpc_dat_accepts_expanded_symbols_without_a_separator():
    raw = b"A01C2001/048    02[STS:A]0014Machines\n"
    frame = parse_cpc_dat(raw)
    assert frame.loc[0, "CPC記号"] == "A01C2001/048"


def test_cpc_latest_data_is_persisted(tmp_path):
    frame = parse_cpc_dat("A01B   1/00     00[STS:A]0051Hand tools\n".encode("cp932"))
    register_latest(frame, "latest", "test", tmp_path)
    assert list_registered(tmp_path).loc[0, "更新時期"] == "latest"
    assert registered_data(tmp_path).loc[0, "CPC記号"] == "A01B 1/00"


def test_cpc_matches_normalized_symbols_and_keeps_unmatched_rows():
    target = pd.DataFrame({"id": ["A", "B"], "cpc": ["Ａ０１Ｂ　１／００", "A01B 99/99"]})
    latest = pd.DataFrame([
        ["A01B 1/00", "00", "T", "0007", "Generic title"],
        ["A01B 1/00", "00", "A", "0051", "Hand tools"],
    ], columns=["CPC記号", "階層", "状態", "番号", "説明"])
    normalized, errors = normalize_column(target, "cpc")
    flagged = add_match_flags(normalized, latest)
    result = build_result(flagged, latest, "id", "cpc")
    assert errors.empty
    assert flagged["最新CPC一致"].tolist() == ["*", ""]
    assert result.columns.tolist() == RESULT_COLUMNS
    assert result["一致可否"].tolist() == ["一致", "不一致"]
    assert result.loc[0, "最新CPC記号"] == "A01B 1/00"
    assert result.loc[0, "CPC標題"] == "Hand tools"


def test_invalid_cpc_symbol_is_returned_as_a_conversion_error():
    target = pd.DataFrame({"cpc": ["not a CPC"]})
    _, errors = normalize_column(target, "cpc")
    assert len(errors) == 1
    assert errors.loc[0, "変換エラー"]


def test_cpc_revision_zip_parses_rcl_and_compilation_xml():
    frame = parse_cpc_revision_zip(_revision_zip(), "2026.08")
    assert frame.columns.tolist() == REVISION_COLUMNS
    assert frame[["改正前CPC", "改正後CPC"]].values.tolist() == [
        ["A01B 1/00", "A01B 1/02"], ["A01B 1/04", "A01B 1/04"],
    ]
    assert frame["資料種別"].tolist() == ["Revision Concordance List", "Compilation of Changes"]


def test_cpc_revision_import_corrects_known_title_symbol_mismatch():
    compilation = b'''<scheme-compilation>
        <compilation-item amendment-type="U">
            <classification-symbol>A61F2/06</classification-symbol>
            <title>Artificial legs or feet or parts thereof</title>
        </compilation-item>
    </scheme-compilation>'''
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("cpc-compilation.xml", compilation)

    frame = parse_cpc_revision_zip(raw.getvalue(), "2014.06")

    assert frame.loc[0, "改正前CPC"] == "A61F 2/60"
    assert frame.loc[0, "改正後CPC"] == "A61F 2/60"


def test_cpc_revision_data_is_persisted(tmp_path):
    frame = parse_cpc_revision_zip(_revision_zip(), "2026.08")
    register_revision(frame, "2026.08", "test", tmp_path, "https://example.test/cpc.zip")
    assert list_revision_registered(tmp_path).loc[0, "revision"] == "2026.08"
    assert registered_revision_data(tmp_path)["改正前CPC"].tolist() == ["A01B 1/00", "A01B 1/04"]


def test_cpc_revision_matching_checks_old_and_new_symbols_and_fills_new_title():
    target = pd.DataFrame({"id": ["old", "new", "other"], "cpc": ["A01B 1/00", "A01B 1/02", "A01B 9/00"]})
    revisions = pd.DataFrame([[
        "2026.08", "D", "A01B 1/00", "A01B 1/02", "Old title", "", "Revision Concordance List",
    ]], columns=REVISION_COLUMNS)
    latest = pd.DataFrame([["A01B 1/02", "00", "A", "0051", "New title"]], columns=["CPC記号", "階層", "状態", "番号", "説明"])
    normalized, errors = normalize_column(target, "cpc")
    flagged = add_match_flags(normalized, latest, revisions)
    result = build_revision_result(flagged, revisions, latest, "id", "cpc")
    assert errors.empty
    assert flagged["CPC改正情報一致"].tolist() == ["*", "*", ""]
    assert result.columns.tolist() == REVISION_RESULT_COLUMNS
    assert result["対象データ"].tolist() == ["old", "new", "other"]
    assert result.loc[0, "改正後標題"] == "New title"
    assert result.loc[0, "改正種別（日本語）"] == "廃止"
    assert result.loc[2, "一致可否"] == "不一致"


def test_cpc_amendment_type_labels_are_translated_to_japanese():
    assert amendment_type_label("C") == "再分類を伴う分類範囲変更"
    assert amendment_type_label("E") == "分類範囲拡大（他記号から文献を受入、2019.05にTへ移行）"
    assert amendment_type_label("T") == "分類範囲拡大（他記号から文献を受入、Eの後継）"
    assert amendment_type_label("U") == "変更なし"


def test_cpc_revision_results_exclude_unchanged_rows():
    target = pd.DataFrame({"id": ["unchanged"], "cpc": ["A61F 2/06"]})
    revisions = pd.DataFrame([[
        "2026.08", "U", "A61F 2/06", "A61F 2/06", "Old title", "New title", "Compilation of Changes",
    ]], columns=REVISION_COLUMNS)
    latest = pd.DataFrame([[
        "A61F 2/06", "00", "A", "0051", "Blood vessels",
    ]], columns=["CPC記号", "階層", "状態", "番号", "説明"])
    normalized, _ = normalize_column(target, "cpc")
    flagged = add_match_flags(normalized, latest, revisions)

    result = build_revision_result(flagged, revisions, latest, "id", "cpc")

    assert flagged.loc[0, "CPC改正情報一致"] == ""
    assert flagged.loc[0, "最新CPC一致"] == "*"
    assert len(result) == 1
    assert pd.isna(result.loc[0, "改正種別"])
    assert result.loc[0, "最新CPC標題"] == "Blood vessels"


def test_cpc_revision_match_flag_excludes_unchanged_only_symbols():
    target = pd.DataFrame({"cpc": ["A01B 1/00", "A01B 1/02", "A01B 1/04"]})
    revisions = pd.DataFrame([
        ["2026.08", "U", "A01B 1/00", "A01B 1/00", "", "", "Compilation of Changes"],
        ["2026.08", "U", "A01B 1/02", "A01B 1/02", "", "", "Compilation of Changes"],
        ["2026.08", "M", "A01B 1/02", "A01B 1/02", "", "", "Compilation of Changes"],
        ["2014.10", "", "A01B 1/04", "A01B 1/04", "", "", "Compilation of Changes"],
    ], columns=REVISION_COLUMNS)
    latest = pd.DataFrame(columns=["CPC記号", "階層", "状態", "番号", "説明"])
    normalized, _ = normalize_column(target, "cpc")

    flagged = add_match_flags(normalized, latest, revisions)

    assert flagged["CPC改正情報一致"].tolist() == ["", "*", ""]


def test_cpc_revision_results_exclude_blank_amendment_types():
    target = pd.DataFrame({"id": ["blank"], "cpc": ["F21V 23/00"]})
    revisions = pd.DataFrame([[
        "2014.10", "", "F21V 23/00", "F21V 23/00", "Old title", "New title", "Compilation of Changes",
    ]], columns=REVISION_COLUMNS)
    latest = pd.DataFrame([[
        "F21V 23/00", "00", "A", "0051", "Current title",
    ]], columns=["CPC記号", "階層", "状態", "番号", "説明"])
    normalized, _ = normalize_column(target, "cpc")

    result = build_revision_result(normalized, revisions, latest, "id", "cpc")

    assert len(result) == 1
    assert pd.isna(result.loc[0, "改正種別"])
    assert result.loc[0, "最新CPC標題"] == "Current title"


def test_cpc_scheme_xml_diff_infers_added_deleted_and_modified_symbols():
    def scheme(symbol: str, title: str) -> bytes:
        return f'''<class-scheme><classification-item date-revised="2013-09-01">
            <classification-symbol>{symbol}</classification-symbol>
            <class-title><title-part><text>{title}</text></title-part></class-title>
        </classification-item></class-scheme>'''.encode()

    def scheme_zip(*documents: bytes) -> bytes:
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as archive:
            for index, document in enumerate(documents):
                archive.writestr(f"scheme-{index}.xml", document)
        return raw.getvalue()

    previous = parse_cpc_scheme_zip(scheme_zip(scheme("A01B1/00", "Old"), scheme("A01B1/02", "Deleted")))
    current = parse_cpc_scheme_zip(scheme_zip(scheme("A01B1/00", "New"), scheme("A01B1/04", "Added")))
    result = build_scheme_revision_rows(previous, current, "2013.09")
    assert result[["改正種別", "改正前CPC", "改正後CPC"]].values.tolist() == [
        ["D", "A01B 1/02", ""], ["N", "", "A01B 1/04"], ["M", "A01B 1/00", "A01B 1/00"],
    ]