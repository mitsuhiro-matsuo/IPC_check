import pandas as pd

from cpc_consolidator import RESULT_COLUMNS, build_result
from cpc_latest_store import list_registered, parse_cpc_dat, register_latest, registered_data
from cpc_matcher import add_match_flags, normalize_column


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