from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from consolidator import build_result
from cpc_consolidator import build_result as build_cpc_result
from cpc_latest_store import list_registered as list_cpc_latest_registered
from cpc_latest_store import parse_cpc_dat, registered_data as registered_cpc_latest_data
from cpc_latest_store import register_latest as register_cpc_latest
from cpc_matcher import add_match_flags as add_cpc_match_flags, normalize_column as normalize_cpc_column
from fi_consolidator import build_result as build_fi_result
from fi_latest_store import list_registered as list_fi_latest_registered
from fi_latest_store import parse_fi_dat, registered_data as registered_fi_latest_data
from fi_latest_store import register_latest as register_fi_latest
from fi_latest_store import revision_from_filename as fi_latest_revision_from_filename
from fi_matcher import add_match_flags as add_fi_match_flags, normalize_column as normalize_fi_column
from fi_revision_store import list_registered as list_fi_registered, parse_revision_workbook
from fi_revision_store import registered_data as registered_fi_data, register_revision as register_fi_revision
from fi_revision_store import revision_from_filename as fi_revision_from_filename
from ipc_io import read_table, read_target_table, workbook_bytes
from ipc_parser import parse_ipc
from latest_store import list_registered as list_latest_registered, parse_ipc8_dat
from latest_store import registered_data as registered_latest_data, register_latest
from latest_store import revision_from_filename as latest_revision_from_filename
from matcher import add_match_flags, normalize_column
from revision_store import list_registered, parse_revision_csv, parse_revision_zip
from revision_store import registered_data, register_revision, revision_from_filename


APP_DIR = Path(__file__).resolve().parent
REVISION_STORAGE = APP_DIR / "data" / "ipc_revisions"
LATEST_STORAGE = APP_DIR / "data" / "latest_ipc"
FI_REVISION_STORAGE = APP_DIR / "data" / "fi_revisions"
FI_LATEST_STORAGE = APP_DIR / "data" / "latest_fi"
CPC_LATEST_STORAGE = APP_DIR / "data" / "latest_cpc"
FI_MATCHING_VERSION = "2026-08-05.2"

st.set_page_config(page_title="IPC・FI・CPC改正状況チェック", page_icon="📊", layout="wide")
st.title("IPC・FI・CPC改正状況チェック")
st.caption("IPC・FIの改正情報、または最新CPCデータを照合します。")


def choose_column(frame: pd.DataFrame, label: str, default: int, preferred: tuple[str, ...] = ()) -> object:
    columns = list(frame.columns)
    if not columns:
        st.error(f"{label}を選択できる列がありません。")
        st.stop()
    for name in preferred:
        if name in columns:
            default = columns.index(name)
            break
    return st.selectbox(label, columns, index=min(default, len(columns) - 1), key=f"column_{label}")


def normalize_uploaded_revision(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column_index in (2, 4):
        if column_index < result.shape[1]:
            column = result.columns[column_index]
            result[column] = result[column].map(lambda value: parse_ipc(value).normalized or value)
    return result


def register_ipc_data() -> dict[str, pd.DataFrame]:
    st.header("IPC改正情報")
    records = list_registered(REVISION_STORAGE)
    if records.empty:
        st.info("登録済みのIPC改正情報はありません")
    else:
        st.dataframe(records[["revision", "source", "rows"]], hide_index=True, use_container_width=True)
    revisions = st.file_uploader("IPC改正情報（ZIP/CSV）", type=["csv", "zip"], accept_multiple_files=True, key="ipc_revision_uploads")
    if revisions and st.button("IPC改正情報を登録", use_container_width=True):
        failures = []
        for file in revisions:
            revision = revision_from_filename(file.name)
            try:
                frame = parse_revision_zip(file.getvalue()) if file.name.lower().endswith(".zip") else parse_revision_csv(file.getvalue())
                register_revision(frame, revision or "uploaded", "ユーザーアップロード", REVISION_STORAGE, file_stem=file.name.rsplit(".", 1)[0])
            except Exception as exc:
                failures.append(f"{file.name}: {exc}")
        for failure in failures:
            st.error(failure)
        if not failures:
            st.rerun()

    st.header("最新IPCファイル")
    records = list_latest_registered(LATEST_STORAGE)
    if records.empty:
        st.info("登録済みの最新IPCファイルはありません")
    else:
        st.dataframe(records[["更新時期", "source", "rows"]], hide_index=True, use_container_width=True)
    uploads = st.file_uploader("最新IPCファイル（IPC8_DAT）", type=None, accept_multiple_files=True, key="ipc_latest_uploads")
    pending: dict[str, pd.DataFrame] = {}
    for file in uploads:
        try:
            pending[file.name] = parse_ipc8_dat(file.getvalue())
        except Exception as exc:
            st.error(f"{file.name}: {exc}")
    if uploads and st.button("最新IPCを登録", use_container_width=True):
        for file in uploads:
            if file.name in pending:
                register_latest(pending[file.name], latest_revision_from_filename(file.name) or "latest", "ユーザーアップロード", LATEST_STORAGE, file.name)
        st.rerun()
    return pending


def register_fi_data() -> dict[str, pd.DataFrame]:
    st.header("FI改正情報")
    records = list_fi_registered(FI_REVISION_STORAGE)
    if records.empty:
        st.info("登録済みのFI改正情報はありません")
    else:
        st.dataframe(records[["revision", "source", "rows"]], hide_index=True, use_container_width=True)
    revisions = st.file_uploader("FI改正情報（XLS）", type=["xls"], accept_multiple_files=True, key="fi_revision_uploads")
    if revisions and st.button("FI改正情報を登録", use_container_width=True):
        failures = []
        for file in revisions:
            revision = fi_revision_from_filename(file.name)
            try:
                frame = parse_revision_workbook(file.getvalue(), revision or "uploaded")
                register_fi_revision(frame, revision or "uploaded", "ユーザーアップロード", FI_REVISION_STORAGE, file.name.rsplit(".", 1)[0])
            except Exception as exc:
                failures.append(f"{file.name}: {exc}")
        for failure in failures:
            st.error(failure)
        if not failures:
            st.rerun()

    st.header("最新FIファイル")
    records = list_fi_latest_registered(FI_LATEST_STORAGE)
    if records.empty:
        st.info("登録済みの最新FIファイルはありません")
    else:
        st.dataframe(records[["更新時期", "source", "rows"]], hide_index=True, use_container_width=True)
    uploads = st.file_uploader("最新FIファイル（FI_DAT）", type=None, accept_multiple_files=True, key="fi_latest_uploads")
    pending: dict[str, pd.DataFrame] = {}
    for file in uploads:
        try:
            pending[file.name] = parse_fi_dat(file.getvalue())
        except Exception as exc:
            st.error(f"{file.name}: {exc}")
    if uploads and st.button("最新FIを登録", use_container_width=True):
        for file in uploads:
            if file.name in pending:
                register_fi_latest(pending[file.name], fi_latest_revision_from_filename(file.name) or "latest", "ユーザーアップロード", FI_LATEST_STORAGE, file.name)
        st.rerun()
    return pending


def register_cpc_data() -> dict[str, pd.DataFrame]:
    st.header("最新CPCファイル")
    records = list_cpc_latest_registered(CPC_LATEST_STORAGE)
    if records.empty:
        st.info("登録済みの最新CPCファイルはありません")
    else:
        st.dataframe(records[["更新時期", "source", "rows"]], hide_index=True, use_container_width=True)
    upload = st.file_uploader("最新CPCファイル（CPC_DAT）", type=None, key="cpc_latest_upload")
    pending: dict[str, pd.DataFrame] = {}
    if upload:
        try:
            pending[upload.name] = parse_cpc_dat(upload.getvalue())
        except Exception as exc:
            st.error(f"{upload.name}: {exc}")
    if upload and st.button("最新CPCを登録", use_container_width=True) and upload.name in pending:
        register_cpc_latest(pending[upload.name], "latest", "ユーザーアップロード", CPC_LATEST_STORAGE, upload.name)
        st.rerun()
    return pending


def display_results(prefix: str, sheets: dict[str, pd.DataFrame], revision_flag: str, latest_flag: str, filename: str) -> None:
    target, result, errors = sheets["対象"], sheets["一致結果"], sheets["変換エラー"]
    download_sheets = {"対象": target, "一致結果": result, "変換エラー": errors}
    metrics = st.columns(5)
    metrics[0].metric("対象件数", f"{len(target):,}")
    metrics[1].metric("変換エラー", f"{len(errors):,}")
    metrics[2].metric(revision_flag, f"{(target[revision_flag] == '*').sum():,}")
    metrics[3].metric(latest_flag, f"{(target[latest_flag] == '*').sum():,}")
    metrics[4].metric("結果件数", f"{len(result):,}")
    result_tab, target_tab, error_tab = st.tabs(["一致結果", "対象データ", "変換エラー"])
    with result_tab:
        st.dataframe(result, use_container_width=True, hide_index=True)
    with target_tab:
        st.dataframe(target, use_container_width=True, hide_index=True)
    with error_tab:
        st.dataframe(errors, use_container_width=True, hide_index=True)
    st.download_button(f"{prefix}結果Excelをダウンロード", workbook_bytes(download_sheets), filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")


def display_cpc_results(sheets: dict[str, pd.DataFrame]) -> None:
    target, result, errors = sheets["対象"], sheets["一致結果"], sheets["変換エラー"]
    metrics = st.columns(4)
    metrics[0].metric("対象件数", f"{len(target):,}")
    metrics[1].metric("変換エラー", f"{len(errors):,}")
    metrics[2].metric("最新CPC一致", f"{(target['最新CPC一致'] == '*').sum():,}")
    metrics[3].metric("結果件数", f"{len(result):,}")
    result_tab, target_tab, error_tab = st.tabs(["一致結果", "対象データ", "変換エラー"])
    with result_tab:
        st.dataframe(result, use_container_width=True, hide_index=True)
    with target_tab:
        st.dataframe(target, use_container_width=True, hide_index=True)
    with error_tab:
        st.dataframe(errors, use_container_width=True, hide_index=True)
    st.download_button(
        "CPC結果Excelをダウンロード",
        workbook_bytes({"対象": target, "一致結果": result, "変換エラー": errors}),
        "cpc_check_result.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


def render_ipc_flow(pending_latest: dict[str, pd.DataFrame]) -> None:
    target_file = st.file_uploader("IPC対象ファイル", type=["xlsx", "xlsm", "csv"], key="ipc_target")
    old_file = st.file_uploader("IPC改正情報ファイル（任意）", type=["xlsx", "xlsm", "csv"], key="ipc_old")
    latest_file = st.file_uploader("最新IPCファイル（任意）", type=None, key="ipc_latest")
    if not target_file:
        return
    try:
        target = read_target_table(target_file)
        latest_frames = [registered_latest_data(LATEST_STORAGE), *pending_latest.values()]
        if latest_file:
            latest_frames.append(read_table(latest_file) if latest_file.name.lower().endswith((".xlsx", ".xlsm", ".csv")) else parse_ipc8_dat(latest_file.getvalue()))
        latest = pd.concat(latest_frames, ignore_index=True).drop_duplicates()
        uploaded_old = normalize_uploaded_revision(read_table(old_file)) if old_file else pd.DataFrame()
        old = pd.concat([registered_data(REVISION_STORAGE), uploaded_old], ignore_index=True).drop_duplicates()
    except Exception as exc:
        st.error(f"ファイルを読み込めませんでした: {exc}")
        return
    if target.empty or old.empty or latest.empty:
        st.error("対象、IPC改正情報、最新IPCのすべてを用意してください。")
        return
    first, second, third = st.columns(3)
    with first:
        target_input = choose_column(target, "対象IPC入力列", 2)
        target_id = choose_column(target, "対象ID列", 1)
    with second:
        old_key = choose_column(old, "IPC改正情報照合キー列", 2)
        old_number = choose_column(old, "改正前記号列", min(2, len(old.columns) - 1))
    with third:
        latest_key = choose_column(latest, "最新IPC照合キー列", 2, ("IPC記号", "正規化IPC", "照合キー"))
    if st.button("IPC処理を実行", type="primary", use_container_width=True):
        normalized, errors = normalize_column(target, target_input)
        flagged = add_match_flags(normalized, old, latest, old_key, latest_key)
        result = build_result(flagged, old, latest, old_key, latest_key, old_number, target_id, target_input)
        st.session_state["ipc_sheets"] = {"対象": flagged, "一致結果": result, "変換エラー": errors}
    if "ipc_sheets" in st.session_state:
        display_results("IPC", st.session_state["ipc_sheets"], "IPC改正情報一致", "最新IPC一致", "ipc_check_result.xlsx")


def render_fi_flow(pending_latest: dict[str, pd.DataFrame]) -> None:
    target_file = st.file_uploader("FI対象ファイル", type=["xlsx", "xlsm", "xls", "csv"], key="fi_target")
    revision_files = st.file_uploader(
        "FI改正情報ファイル（任意、複数選択可）",
        type=["xls"],
        accept_multiple_files=True,
        key="fi_revision",
    )
    latest_file = st.file_uploader("最新FIファイル（任意）", type=None, key="fi_latest")
    if not target_file:
        return
    revision_labels: dict[str, str] = {}
    for revision_file in revision_files:
        revision_labels[revision_file.name] = st.text_input(
            f"{revision_file.name} の改正時期",
            value=fi_revision_from_filename(revision_file.name),
            key=f"fi_revision_label_{revision_file.name}",
        )
    try:
        target = read_target_table(target_file)
        revision_frames = [registered_fi_data(FI_REVISION_STORAGE)]
        for revision_file in revision_files:
            revision_label = revision_labels[revision_file.name].strip()
            if not revision_label:
                st.error(f"{revision_file.name} の改正時期を入力してください。")
                return
            revision_frames.append(parse_revision_workbook(revision_file.getvalue(), revision_label.strip()))
        revisions = pd.concat(revision_frames, ignore_index=True).drop_duplicates()
        latest_frames = [registered_fi_latest_data(FI_LATEST_STORAGE), *pending_latest.values()]
        if latest_file:
            uploaded_latest = parse_fi_dat(latest_file.getvalue())
            latest_frames.append(uploaded_latest)
        latest = pd.concat(latest_frames, ignore_index=True).drop_duplicates()
    except Exception as exc:
        st.error(f"ファイルを読み込めませんでした: {exc}")
        return
    if target.empty or revisions.empty or latest.empty:
        st.error("対象、FI改正情報、最新FIのすべてを用意してください。")
        return
    first, second = st.columns(2)
    with first:
        target_input = choose_column(target, "対象FI入力列", 2)
    with second:
        target_id = choose_column(target, "FI対象ID列", 1)
    st.caption("FI記号の例: `C09K 3/10 C`、`A01D 37/00 A`、`A01B 69/00 303A`。空白の有無は問いません。")
    if st.button("FI処理を実行", type="primary", use_container_width=True):
        normalized, errors = normalize_fi_column(target, target_input)
        flagged = add_fi_match_flags(normalized, revisions, latest)
        result = build_fi_result(flagged, revisions, latest, target_id)
        st.session_state["fi_sheets"] = {
            "対象": flagged,
            "一致結果": result,
            "変換エラー": errors,
            "照合バージョン": FI_MATCHING_VERSION,
        }
    if st.session_state.get("fi_sheets", {}).get("照合バージョン") != FI_MATCHING_VERSION:
        st.session_state.pop("fi_sheets", None)
        st.info("FI記号の照合規則を更新しました。FI処理を実行して結果を再計算してください。")
        return
    if "fi_sheets" in st.session_state:
        display_results("FI", st.session_state["fi_sheets"], "FI改正情報一致", "最新FI一致", "fi_check_result.xlsx")


def render_cpc_flow(pending_latest: dict[str, pd.DataFrame]) -> None:
    target_file = st.file_uploader("CPC対象ファイル", type=["xlsx", "xlsm", "xls", "csv"], key="cpc_target")
    latest_file = st.file_uploader("最新CPCファイル（任意）", type=None, key="cpc_latest")
    if not target_file:
        return
    try:
        target = read_target_table(target_file)
        latest_frames = [registered_cpc_latest_data(CPC_LATEST_STORAGE), *pending_latest.values()]
        if latest_file:
            latest_frames.append(parse_cpc_dat(latest_file.getvalue()))
        latest = pd.concat(latest_frames, ignore_index=True).drop_duplicates()
    except Exception as exc:
        st.error(f"ファイルを読み込めませんでした: {exc}")
        return
    if target.empty or latest.empty:
        st.error("対象ファイルと最新CPCファイルを用意してください。")
        return
    first, second = st.columns(2)
    with first:
        target_input = choose_column(target, "対象CPC入力列", 2)
    with second:
        target_id = choose_column(target, "CPC対象ID列", 1)
    st.caption("CPCは改正履歴を持たないため、最新CPCファイルとの一致のみを確認します。")
    if st.button("CPC処理を実行", type="primary", use_container_width=True):
        normalized, errors = normalize_cpc_column(target, target_input)
        flagged = add_cpc_match_flags(normalized, latest)
        result = build_cpc_result(flagged, latest, target_id, target_input)
        st.session_state["cpc_sheets"] = {"対象": flagged, "一致結果": result, "変換エラー": errors}
    if "cpc_sheets" in st.session_state:
        display_cpc_results(st.session_state["cpc_sheets"])


with st.sidebar:
    st.header("共有データ管理")
    pending_ipc_latest = register_ipc_data()
    pending_fi_latest = register_fi_data()
    pending_cpc_latest = register_cpc_data()

ipc_tab, fi_tab, cpc_tab = st.tabs(["IPC", "FI", "CPC"])
with ipc_tab:
    render_ipc_flow(pending_ipc_latest)
with fi_tab:
    render_fi_flow(pending_fi_latest)
with cpc_tab:
    render_cpc_flow(pending_cpc_latest)