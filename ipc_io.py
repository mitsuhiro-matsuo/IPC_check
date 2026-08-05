"""Excel/CSV input and downloadable workbook creation."""

from __future__ import annotations

from io import BytesIO
import pandas as pd


def read_excel_sheets(uploaded_file: object) -> dict[str, pd.DataFrame]:
    return pd.read_excel(uploaded_file, sheet_name=None, dtype=str, engine="openpyxl")


def read_table(uploaded_file: object) -> pd.DataFrame:
    name = getattr(uploaded_file, "name", "").lower()
    if name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        return pd.read_excel(uploaded_file, dtype=str, engine="openpyxl")
    if name.endswith(".xls"):
        return pd.read_excel(uploaded_file, dtype=str, engine="xlrd")
    return pd.read_csv(uploaded_file, dtype=str)


def read_target_table(uploaded_file: object) -> pd.DataFrame:
    """Read a target file without treating its first row as a header."""
    name = getattr(uploaded_file, "name", "").lower()
    if name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        frame = pd.read_excel(uploaded_file, dtype=str, header=None, engine="openpyxl")
    elif name.endswith(".xls"):
        frame = pd.read_excel(uploaded_file, dtype=str, header=None, engine="xlrd")
    else:
        frame = pd.read_csv(uploaded_file, dtype=str, header=None)
    frame.columns = [f"列{index + 1}" for index in range(frame.shape[1])]
    return frame


def workbook_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            safe_name = str(name)[:31] or "結果"
            frame.to_excel(writer, sheet_name=safe_name, index=False)
            worksheet = writer.book[safe_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column in worksheet.columns:
                width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 10), 40)
                worksheet.column_dimensions[column[0].column_letter].width = width
    return output.getvalue()