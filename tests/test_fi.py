import pandas as pd

from fi_parser import format_fi_symbol, normalize_fi_key, parse_fi
from fi_revision_store import _standard_rows, list_registered, register_revision, registered_data
from fi_latest_store import register_latest, registered_data as registered_latest_data, parse_fi_dat
from fi_matcher import add_match_flags, normalize_column
from fi_consolidator import build_result


def test_fi_symbols_keep_expansion_and_booklet_tokens():
    variants = ["A01B   3/04 A", "Ａ０１Ｂ　３／０４　Ａ", "A01B3/04 A"]
    assert {normalize_fi_key(value) for value in variants} == {"A01B3/04 A"}
    assert normalize_fi_key("A01B 69/00 303A") == "A01B69/00 303A"


def test_fi_subgroup_trailing_zero_and_attached_expansion_are_preserved():
    assert normalize_fi_key("C09K 3/10 C") == "C09K3/10 C"
    assert normalize_fi_key("A01D 37/00A") == "A01D37/00 A"
    assert format_fi_symbol("C09K 3/10 C") == "C09K 3/10 C"


def test_latest_fi_match_uses_the_preserved_c09k_subgroup_key():
    target = pd.DataFrame({"fi": ["C09K  3/10      C"]})
    latest = pd.DataFrame({"FI記号": ["C09K 3/10 C"]})
    revisions = pd.DataFrame(columns=["改正前FI", "改正後FI"])
    normalized, errors = normalize_column(target, "fi")
    flagged = add_match_flags(normalized, revisions, latest)
    assert errors.empty
    assert flagged.loc[0, "正規化FI"] == "C09K3/10 C"
    assert flagged.loc[0, "最新FI一致"] == "*"


def test_fi_attached_and_separated_booklet_identifiers_share_a_key():
    assert normalize_fi_key("A63C9/00 101 E") == "A63C9/00 101 E"
    assert normalize_fi_key("A63C 9/00 101E") == "A63C9/00 101 E"
    target = pd.DataFrame({"fi": ["A63C9/00 101 E"]})
    latest = pd.DataFrame({"FI記号": ["A63C 9/00 101E"]})
    revisions = pd.DataFrame(columns=["改正前FI", "改正後FI"])
    normalized, _ = normalize_column(target, "fi")
    flagged = add_match_flags(normalized, revisions, latest)
    assert flagged.loc[0, "最新FI一致"] == "*"


def test_fi_symbol_without_optional_tokens_is_supported():
    parsed = parse_fi("A61F 13/00")
    assert parsed.normalized == "A61F13/00"
    assert format_fi_symbol("A61F0013/000000") == "A61F 13/00"


def test_invalid_fi_symbol_is_reported():
    parsed = parse_fi("not an FI symbol")
    assert parsed.normalized is None
    assert parsed.error


def test_fi_revision_sheets_are_standardized_and_persisted(tmp_path):
    abolished = pd.DataFrame([
        ["廃止FI", "", "", "", "廃止時移行先"],
        ["項番", "グループ", "展開記号", "分冊識別記号", "タイトル", "グループ", "展開記号", "分冊識別記号", "タイトル"],
        ["1", "H01G 1/02", "G", "", "旧タイトル", "H01G 9/02", "311", "C", "新タイトル"],
    ])
    rows = _standard_rows(abolished, "2026.01", "廃止")
    frame = pd.DataFrame(rows)
    assert frame.loc[0, "改正前FI"] == "H01G 1/02 G"
    assert frame.loc[0, "改正後FI"] == "H01G 9/02 311 C"
    assert frame.loc[0, "改正前タイトル"] == "旧タイトル"
    register_revision(frame, "2026.01", "test", tmp_path)
    assert registered_data(tmp_path).loc[0, "改正後FI"] == "H01G 9/02 311 C"


def test_fi_revision_metadata_recovers_from_trailing_json_data(tmp_path):
    metadata = tmp_path / "metadata.json"
    metadata.write_text('[{"revision": "2026.01", "source": "test", "rows": 1, "file": "test.csv"}] }] ', encoding="utf-8")
    records = list_registered(tmp_path)
    assert records.loc[0, "revision"] == "2026.01"
    assert metadata.read_text(encoding="utf-8").rstrip().endswith("]")


def test_fi_dat_and_unified_revision_results():
    raw = "A01B   3/04       A 02[DATE:20060101-99991231 STS:A]0010展開記号付き\n".encode("cp932")
    latest = parse_fi_dat(raw)
    assert latest.loc[0, "FI記号"] == "A01B 3/04 A"
    target = pd.DataFrame({"id": ["A", "B"], "fi": ["A01B 3/04 A", "A61F 13/00 501"]})
    revisions = pd.DataFrame([
        ["2026.01", "廃止", "A01B 3/04 A", "A01B 3/04 Z", "旧", ""],
        ["2026.01", "新設", "", "A61F 13/00 501", "", "新"],
    ], columns=["改正時期", "改正種別", "改正前FI", "改正後FI", "改正前タイトル", "改正後タイトル"])
    normalized, errors = normalize_column(target, "fi")
    flagged = add_match_flags(normalized, revisions, latest)
    result = build_result(flagged, revisions, latest, "id")
    assert errors.empty
    assert flagged["FI改正情報一致"].tolist() == ["*", "*"]
    assert result["改正種別"].tolist() == ["廃止", "新設"]


def test_fi_dat_accepts_variable_width_expansion_fields():
    raw = "A01B  69/00    303A 01[DATE:20060101-99991231 STS:A]0010可変長FI\n".encode("cp932")
    frame = parse_fi_dat(raw)
    assert frame.loc[0, "FI記号"] == "A01B 69/00 303A"
    assert frame.loc[0, "階層"] == "01"


def test_fi_dat_preserves_c09k_subgroup_ten():
    raw = "C09K   3/10      C 02[DATE:00000000-99991231 STS:A]0010ゴム一般用\n".encode("cp932")
    frame = parse_fi_dat(raw)
    assert frame.loc[0, "FI記号"] == "C09K 3/10 C"


def test_registered_latest_fi_migrates_known_legacy_symbol(tmp_path):
    legacy = pd.DataFrame([["C09K 3/01 C", "02", "00000000-99991231", "A", "0010", "ゴム一般用[FTM:4H017]"]], columns=["FI記号", "階層", "適用期間", "状態", "番号", "説明"])
    register_latest(legacy, "latest", "test", tmp_path)
    loaded = registered_latest_data(tmp_path)
    assert loaded.loc[0, "FI記号"] == "C09K 3/10 C"


def test_fi_dat_keeps_nonstandard_lines_as_description_continuations():
    raw = (
        "A01B   3/04       A 02[DATE:20060101-99991231 STS:A]0010有効行\n"
        "invalid FI_DAT line\n"
    ).encode("cp932")
    frame = parse_fi_dat(raw)
    assert len(frame) == 1
    assert frame.loc[0, "説明"] == "有効行 invalid FI_DAT line"