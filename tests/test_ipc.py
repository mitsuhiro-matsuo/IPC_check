import pandas as pd

from consolidator import build_result
from matcher import add_match_flags, normalize_column
from ipc_parser import format_ipc_symbol, ipc_main_group_prefix, normalize_ipc_key, parse_ipc


def test_parse_matches_vba_padding():
    assert parse_ipc("2023E01/456").normalized == "20230E01456000"
    assert parse_ipc("2023 E01 / 4 56").normalized == "20230E01456000"
    variants = ["2023 1/456", "20230001/456", "2023 0001 / 000456", "２０２３　１／４５６"]
    variants.append("20230001000456")
    assert {normalize_ipc_key(value) for value in variants} == {"20230001456000"}


def test_parse_standard_ipc_symbol():
    variants = ["A01B 1/00", "A01B1/00", "A 01 B 1 / 00", "Ａ０１Ｂ　１／００"]
    parsed = [normalize_ipc_key(value) for value in variants]
    assert len(set(parsed)) == 1
    assert parsed[0] == "A01B1/0"


def test_file_specific_ipc_formats_share_one_comparison_key():
    target = parse_ipc("A61F  2/06")
    assert target.normalized == "A61F0002/06"
    assert normalize_ipc_key(target.normalized) == "A61F2/06"
    assert normalize_ipc_key("A61F0002060000") == "A61F2/06"
    assert normalize_ipc_key("A61F0002/060000") == "A61F2/06"


def test_trailing_subgroup_zero_padding_is_ignored():
    variants = ["A01B 1/00", "A01B0001000000", "A01B0001/000000"]
    assert {normalize_ipc_key(value) for value in variants} == {"A01B1/0"}


def test_fixed_width_ipc_is_formatted_for_display():
    assert format_ipc_symbol("H01L0027140000") == "H01L 27/14"
    assert format_ipc_symbol("H10F0099000000") == "H10F 99/00"
    assert format_ipc_symbol("H10F0019500000") == "H10F 19/50"


def test_slashless_main_group_is_supported():
    assert parse_ipc("H01L0027").normalized == "H01L0027/00"
    assert normalize_ipc_key("H01L0027") == "H01L27/0"
    assert ipc_main_group_prefix("H01L0027") == "H01L27/"


def test_invalid_value_is_reported():
    parsed = parse_ipc("2023/E01 456")
    assert parsed.normalized is None
    assert parsed.error


def test_matching_and_result_aggregation():
    target = pd.DataFrame({"id": ["A"], "ipc": ["2023E01/456"]})
    old = pd.DataFrame({"a": ["x", "y"], "b": ["x", "y"], "key": ["20230E01456000"] * 2, "number": ["O1", "O2"]})
    latest = pd.DataFrame({"a": ["L"], "b": ["x"], "key": ["20230E01456000"]})
    normalized, errors = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "key", "key")
    result = build_result(flagged, old, latest, "key", "key", "number", "id", "ipc")
    assert errors.empty
    assert flagged.loc[0, "IPC改正情報一致"] == "*"
    assert flagged.loc[0, "最新IPC一致"] == "*"
    assert result.loc[0, "対象データ"] == "A"


def test_matching_normalizes_reference_key_variants():
    target = pd.DataFrame({"ipc": ["2023 1/456"]})
    old = pd.DataFrame({"key": ["20230001/456"]})
    latest = pd.DataFrame({"key": ["2023 0001 / 000456"]})
    normalized, _ = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "key", "key")
    assert flagged.loc[0, "IPC改正情報一致"] == "*"
    assert flagged.loc[0, "最新IPC一致"] == "*"


def test_raw_latest_key_builds_result():
    target = pd.DataFrame({"id": ["A"], "ipc": ["A01B 1/00"]})
    old = pd.DataFrame({"key": ["A01B1/00"], "number": ["O1"]})
    latest = pd.DataFrame({"key": ["A 01 B 1 / 00"], "label": ["L"]})
    normalized, _ = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "key", "key")
    result = build_result(flagged, old, latest, "key", "key", "number", "id", "ipc")
    assert len(result) == 1
    assert result.loc[0, "対象データ"] == "A"


def test_abolished_ipc_builds_rows_for_all_replacement_symbols():
    target = pd.DataFrame({"id": ["A"], "ipc": ["H01L 21/027"]})
    old = pd.DataFrame({
        "改正前バージョン": ["20250101", "20250101"],
        "改正後バージョン": ["20260101", "20260101"],
        "改正前記号": ["H01L0021/027000", "H01L0021/027000"],
        "属性1": ["d", "d"],
        "改正後記号": ["H10P0076/000000", "H10P0076/200000"],
        "属性2": ["n", "n"],
    })
    latest = pd.DataFrame({
        "IPC記号": ["H01L 21/027", "H10P 76/00", "H10P 76/20"],
        "状態": ["D", "A", "A"],
        "説明": ["廃止された分類", "マスクの製造または処理", "有機材料からなるマスク"],
    })
    normalized, _ = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "改正前記号", "IPC記号")
    result = build_result(
        flagged, old, latest, "改正前記号", "IPC記号", "改正前記号", "id", "ipc"
    )
    assert result.columns.tolist() == [
        "対象データ", "改正前のバージョン", "改正後のバージョン", "改正前の分類記号", "改正前のカテゴリ",
        "改正後の分類記号", "改正後のカテゴリ", "改正後の標題",
    ]
    assert result["改正後の分類記号"].tolist() == ["H10P 76/00", "H10P 76/20"]
    assert result["改正後の標題"].tolist() == ["マスクの製造または処理", "有機材料からなるマスク"]
    assert result["改正前のカテゴリ"].tolist() == ["d：廃止", "d：廃止"]
    assert result["改正後のカテゴリ"].tolist() == ["n：新設", "n：新設"]


def test_only_newest_revision_is_shown_for_each_symbol():
    target = pd.DataFrame({"id": ["A"], "ipc": ["H01L 27/142"]})
    old = pd.DataFrame({
        "from-version": ["20130101", "20240101"],
        "to-version": ["20140101", "20250101"],
        "from-symbol": ["H01L0027142000", "H01L0027142000"],
        "modification": ["c", "d"],
        "to-symbol": ["H01L0031044300", "H10F0019500000"],
        "modification2": ["n", "n"],
    })
    latest = pd.DataFrame({
        "IPC記号": ["H01L 31/0443", "H10F 19/50"],
        "説明": ["古い移行先", "2025年の移行先"],
    })
    normalized, _ = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "from-symbol", "IPC記号")
    result = build_result(flagged, old, latest, "from-symbol", "IPC記号", None, "id", "ipc")
    assert len(result) == 1
    assert result.loc[0, "改正後のバージョン"] == "20250101"
    assert result.loc[0, "改正前の分類記号"] == "H01L 27/142"
    assert result.loc[0, "改正後の分類記号"] == "H10F 19/50"


def test_main_group_input_expands_all_matching_revisions():
    target = pd.DataFrame({"id": ["A"], "ipc": ["H01L0027"]})
    old = pd.DataFrame({
        "from-version": ["20240101", "20240101", "20240101"],
        "to-version": ["20250101", "20250101", "20250101"],
        "from-symbol": ["H01L0027140000", "H01L0027142000", "H01L0027144000"],
        "modification": ["d", "d", "d"],
        "to-symbol": ["H10F0099000000", "H10F0019500000", "H10F0039100000"],
        "modification2": ["n", "n", "n"],
    })
    latest = pd.DataFrame({
        "IPC記号": ["H10F 99/00", "H10F 19/50", "H10F 39/10"],
        "説明": ["第1の移行先", "第2の移行先", "第3の移行先"],
    })
    normalized, errors = normalize_column(target, "ipc")
    assert errors.empty
    flagged = add_match_flags(normalized, old, latest, "from-symbol", "IPC記号")
    result = build_result(flagged, old, latest, "from-symbol", "IPC記号", None, "id", "ipc")
    assert result["改正後の分類記号"].tolist() == ["H10F 99/00", "H10F 19/50", "H10F 39/10"]


def test_duplicate_destination_symbols_are_shown_once():
    target = pd.DataFrame({"id": ["A", "B"], "ipc": ["H01L 27/140", "H01L 27/142"]})
    old = pd.DataFrame({
        "from-version": ["20240101", "20240101"],
        "to-version": ["20250101", "20250101"],
        "from-symbol": ["H01L0027140000", "H01L0027142000"],
        "modification": ["d", "d"],
        "to-symbol": ["H10F0019500000", "H10F0019500000"],
        "modification2": ["n", "n"],
    })
    latest = pd.DataFrame({"IPC記号": ["H10F 19/50"], "説明": ["移行先"]})
    normalized, _ = normalize_column(target, "ipc")
    flagged = add_match_flags(normalized, old, latest, "from-symbol", "IPC記号")

    result = build_result(flagged, old, latest, "from-symbol", "IPC記号", None, "id", "ipc")

    assert len(result) == 1
    assert result.loc[0, "対象データ"] == "A"
    assert result.loc[0, "改正後の分類記号"] == "H10F 19/50"