import io
import zipfile

import pandas as pd

from revision_store import normalize_revision_frame, parse_revision_zip, register_revision, list_registered, registered_data, revision_from_filename
from latest_store import parse_ipc8_dat, register_latest, list_registered as list_latest_registered, registered_data as registered_latest_data


def test_revision_is_inferred_from_filename():
    assert revision_from_filename("rcl_202601.zip") == "2026.01"
    assert revision_from_filename("ipc_202501.csv") == "2025.01"
    assert revision_from_filename("unknown.zip") == ""


def test_parse_and_persist_ipc8_dat(tmp_path):
    raw = "A01B   1/00     00[DATE:20060101-99991231 STS:A]0046手作業具\n".encode("cp932")
    frame = parse_ipc8_dat(raw)
    assert frame.loc[0, "IPC記号"] == "A01B 1/00"
    assert frame.loc[0, "適用期間"] == "20060101-99991231"
    register_latest(frame, "2026.01", "test", tmp_path)
    assert list_latest_registered(tmp_path).iloc[0]["更新時期"] == "2026.01"
    assert len(registered_latest_data(tmp_path)) == 1


def test_ipc8_dat_discards_content_from_character_17():
    raw = "A01B   1/00     02[DATE:20060101-99991231 STS:A]0020説明".encode("cp932")
    frame = parse_ipc8_dat(raw)
    assert frame.loc[0, "IPC記号"] == "A01B 1/00"
    assert "DATE" not in frame.loc[0, "IPC記号"]


def test_extensionless_ipc8_dat_upload_is_supported():
    raw = "A01B   1/00     00[DATE:20060101-99991231 STS:A]0046手作業具\n".encode("cp932")
    frame = parse_ipc8_dat(raw)
    assert not frame.empty


def test_parse_revision_zip_and_persist(tmp_path):
    csv = "2007.01,2008.01,A01,c,B02,n\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("revision.csv", csv.encode("utf-8"))
    frame = parse_revision_zip(output.getvalue())
    assert list(frame.columns) == ["改正前バージョン", "改正後バージョン", "改正前記号", "属性1", "改正後記号", "属性2"]
    record = register_revision(frame, "2026.01", "test", tmp_path)
    assert record["rows"] == 1
    assert list_registered(tmp_path).iloc[0]["revision"] == "2026.01"
    assert len(registered_data(tmp_path)) == 1


def test_revision_ipc_columns_get_a_slash():
    frame = pd.DataFrame([["2006", "2007", "A62D0003000000", "c", "A62D0003020000", "n"]])
    normalized = normalize_revision_frame(frame)
    assert normalized.iloc[0, 2] == "A62D0003/000000"
    assert normalized.iloc[0, 4] == "A62D0003/020000"