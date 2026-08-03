from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from consolidator import build_result
from ipc_io import read_table, workbook_bytes
from ipc_parser import parse_ipc
from matcher import add_match_flags, normalize_column
from latest_store import (
    list_registered as list_latest_registered,
    parse_ipc8_dat,
    registered_data as registered_latest_data,
    register_latest,
    revision_from_filename as latest_revision_from_filename,
)
from revision_store import (
    list_registered,
    parse_revision_csv,
    parse_revision_zip,
    registered_data,
    register_revision,
    revision_from_filename,
)


APP_DIR = Path(__file__).resolve().parent
REVISION_STORAGE = str(APP_DIR / "data" / "ipc_revisions")
LATEST_STORAGE = str(APP_DIR / "data" / "latest_ipc")


st.set_page_config(page_title="IPC改正状況チェック", page_icon="📊", layout="wide")
st.title("IPC改正状況チェック")
st.caption("Excelマクロの正規化・IPC改正情報照合・最新IPC照合をブラウザで実行します。")


def choose_column(frame: pd.DataFrame, label: str, default: int, preferred: tuple[str, ...] = ()) -> object:
    columns = list(frame.columns)
    if not columns:
        st.error(f"{label}を選択できる列がありません。ファイルを確認してください。")
        st.stop()
    for name in preferred:
        if name in columns:
            default = columns.index(name)
            break
    return st.selectbox(label, columns, index=min(default, len(columns) - 1), key=f"column_{label}")


def normalize_uploaded_revision(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column_index in (2, 4):
        if column_index >= result.shape[1]:
            continue
        column = result.columns[column_index]
        result[column] = result[column].map(lambda value: parse_ipc(value).normalized or value)
    return result


with st.sidebar:
    st.header("共有データ管理")

    st.header("IPC改正情報")
    st.caption("特許庁サイトからダウンロードした改正情報をまとめて登録できます。")
    storage_folder = REVISION_STORAGE
    registered = list_registered(storage_folder)
    if registered.empty:
        st.info("登録済みの改正情報はありません")
    else:
        latest_registered = registered.iloc[0]
        st.success(f"{len(registered)}版を登録済み\n\n最終: {latest_registered['revision']}")
        st.dataframe(registered[["revision", "source", "rows"]], hide_index=True, use_container_width=True)
    revision_uploads = st.file_uploader(
        "ダウンロードした改正情報（ZIP/CSV）をまとめて選択",
        type=["csv", "zip"],
        accept_multiple_files=True,
        key="revision_uploads",
        help="特許庁サイトから保存したZIPを複数選択できます。ファイル名から改正時期を自動入力します。",
    )
    revision_labels: dict[str, str] = {}
    for revision_file in revision_uploads:
        default_revision = revision_from_filename(revision_file.name)
        revision_labels[revision_file.name] = st.text_input(
            f"{revision_file.name} の改正時期",
            value=default_revision,
            key=f"revision_label_{revision_file.name}",
        )
    if revision_uploads and st.button("選択した改正情報を一括登録", use_container_width=True):
        registered_count = 0
        errors: list[str] = []
        for revision_file in revision_uploads:
            revision_label = revision_labels[revision_file.name].strip()
            if not revision_label:
                errors.append(f"{revision_file.name}: 改正時期を入力してください")
                continue
            try:
                raw = revision_file.getvalue()
                revision_frame = parse_revision_zip(raw) if revision_file.name.lower().endswith(".zip") else parse_revision_csv(raw)
                register_revision(
                    revision_frame,
                    revision_label,
                    "ユーザーアップロード",
                    storage_folder,
                    file_stem=revision_file.name.rsplit(".", 1)[0],
                )
                registered_count += 1
            except Exception as exc:
                errors.append(f"{revision_file.name}: {exc}")
        if registered_count:
            st.success(f"{registered_count}件の改正情報を登録しました")
        for error in errors:
            st.error(error)
        if not errors:
            st.rerun()

    st.header("最新IPCファイル")
    st.caption("IPC8_DATを共有保存し、更新時期を表示します。")
    latest_storage_folder = LATEST_STORAGE
    latest_registered = list_latest_registered(latest_storage_folder)
    if latest_registered.empty:
        st.info("登録済みの最新IPCファイルはありません")
    else:
        st.success(f"{len(latest_registered)}件を登録済み\n\n最新: {latest_registered.iloc[0]['更新時期']}")
        st.dataframe(latest_registered[["更新時期", "source", "rows"]], hide_index=True, use_container_width=True)
    latest_uploads = st.file_uploader(
        "最新IPCファイル（IPC8_DAT）をまとめて選択",
        type=None,
        accept_multiple_files=True,
        key="latest_uploads",
        help="拡張子のないIPC8_DATもアップロードできます。",
    )
    pending_latest_frames: dict[str, pd.DataFrame] = {}
    pending_latest_errors: list[str] = []
    for latest_file in latest_uploads:
        try:
            pending_latest_frames[latest_file.name] = parse_ipc8_dat(latest_file.getvalue())
        except Exception as exc:
            pending_latest_errors.append(f"{latest_file.name}: {exc}")
    for error in pending_latest_errors:
        st.error(f"最新IPCを読み込めませんでした。{error}")
    latest_labels: dict[str, str] = {}
    for latest_file in latest_uploads:
        default_updated = latest_revision_from_filename(latest_file.name)
        latest_labels[latest_file.name] = st.text_input(
            f"{latest_file.name} の更新時期",
            value=default_updated,
            key=f"latest_label_{latest_file.name}",
        )
    if latest_uploads and st.button("選択した最新IPCを一括登録", use_container_width=True):
        registered_count = 0
        errors: list[str] = []
        for latest_file in latest_uploads:
            updated = latest_labels[latest_file.name].strip()
            if not updated:
                errors.append(f"{latest_file.name}: 更新時期を入力してください")
                continue
            try:
                frame = pending_latest_frames[latest_file.name]
                register_latest(frame, updated, "ユーザーアップロード", latest_storage_folder, latest_file.name)
                registered_count += 1
            except Exception as exc:
                errors.append(f"{latest_file.name}: {exc}")
        if registered_count:
            st.success(f"{registered_count}件の最新IPCを登録しました")
        for error in errors:
            st.error(error)
        if not errors:
            st.rerun()

target_file = st.file_uploader("対象ファイル", type=["xlsx", "xlsm", "csv"], key="target")
old_file = st.file_uploader("IPC改正情報ファイル（任意）", type=["xlsx", "xlsm", "csv"], key="old")
latest_file = st.file_uploader("最新IPCファイル（任意。未指定時は登録済みまたは上のアップロードを使用）", type=None, key="latest")
if target_file:
    try:
        target = read_table(target_file)
        latest_frames = [registered_latest_data(latest_storage_folder), *pending_latest_frames.values()]
        if latest_file:
            latest_frames.append(
                read_table(latest_file)
                if latest_file.name.lower().endswith((".xlsx", ".xlsm", ".csv"))
                else parse_ipc8_dat(latest_file.getvalue())
            )
        latest = pd.concat(latest_frames, ignore_index=True).drop_duplicates()
        stored_old = registered_data(storage_folder)
        uploaded_old = normalize_uploaded_revision(read_table(old_file)) if old_file else pd.DataFrame()
        old = pd.concat([stored_old, uploaded_old], ignore_index=True).drop_duplicates()
    except Exception as exc:
        st.error(f"ファイルを読み込めませんでした: {exc}")
        st.stop()

if "target" in locals():
    if target.empty or target.shape[1] == 0:
        st.error("対象ファイルにデータまたは列がありません。")
        st.stop()
    if old.empty or old.shape[1] == 0:
        st.error("IPC改正情報がありません。先にIPC改正情報ファイルを登録してください。")
        st.stop()
    if latest.empty or latest.shape[1] == 0:
        st.error("最新IPCがありません。先に最新IPCファイルを登録してください。")
        st.stop()
    st.subheader("列設定")
    c1, c2, c3 = st.columns(3)
    with c1:
        target_input = choose_column(target, "対象IPC入力列", 2)
        target_id = choose_column(target, "対象ID列", 1)
    with c2:
        old_key = choose_column(old, "IPC改正情報照合キー列", 2)
        old_number = choose_column(old, "改正前記号列", min(2, len(old.columns) - 1))
    with c3:
        latest_key = choose_column(latest, "最新IPC照合キー列", 2, ("IPC記号", "正規化IPC", "照合キー"))
    st.write({"対象": f"{len(target):,}行", "IPC改正情報": f"{len(old):,}行", "最新IPC": f"{len(latest):,}行"})
    if st.button("処理を実行", type="primary", use_container_width=True):
        with st.status("IPCデータを処理しています", expanded=True) as status:
            status.write("対象IPCを正規化中...")
            normalized_target, errors = normalize_column(target, target_input)
            status.write("IPC改正情報・最新IPCと照合中...")
            flagged = add_match_flags(normalized_target, old, latest, old_key, latest_key)
            status.write("一致結果を生成中...")
            result = build_result(flagged, old, latest, old_key, latest_key, old_number, target_id, target_input)
            status.update(label="処理が完了しました", state="complete")
            if result.empty:
                st.warning("一致するIPCがありません。対象・IPC改正情報・最新IPCの照合キーを確認してください。")
        st.session_state["sheets"] = {"対象": flagged, "一致結果": result, "変換エラー": errors}

if "sheets" in st.session_state:
    sheets = st.session_state["sheets"]
    target_result, result, errors = sheets["対象"], sheets["一致結果"], sheets["変換エラー"]
    metrics = st.columns(5)
    metrics[0].metric("対象件数", f"{len(target_result):,}")
    metrics[1].metric("変換エラー", f"{len(errors):,}")
    metrics[2].metric("IPC改正情報一致", f"{(target_result['IPC改正情報一致'] == '*').sum():,}")
    metrics[3].metric("最新IPC一致", f"{(target_result['最新IPC一致'] == '*').sum():,}")
    metrics[4].metric("結果件数", f"{len(result):,}")
    tab1, tab2, tab3 = st.tabs(["一致結果", "対象データ", "変換エラー"])
    with tab1:
        st.dataframe(result, use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(target_result, use_container_width=True, hide_index=True)
    with tab3:
        st.dataframe(errors, use_container_width=True, hide_index=True)
    st.download_button("結果Excelをダウンロード", workbook_bytes(sheets), "ipc_check_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")