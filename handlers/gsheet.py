import json
import logging
import os

import gspread

from config import now_wib

logger = logging.getLogger(__name__)

HEADERS = ["Timestamp", "Tanggal", "Tipe", "Kategori", "Jumlah", "Keterangan"]

_sheet = None


def _get_sheet():
    global _sheet
    if _sheet is not None:
        return _sheet

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GSHEET_ID")

    if not creds_json or not sheet_id:
        return None

    try:
        creds_dict = json.loads(creds_json)
        client = gspread.service_account_from_dict(creds_dict)
        spreadsheet = client.open_by_key(sheet_id)
        _sheet = spreadsheet.sheet1
        _ensure_headers(_sheet)
        return _sheet
    except Exception as e:
        logger.error("GSheet init error: %s", e)
        return None


def _ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if first_row != HEADERS:
        sheet.insert_row(HEADERS, index=1)


def append_transaction(tipe: str, kategori: str, amount: float, description: str, date: str = None):
    sheet = _get_sheet()
    if sheet is None:
        return

    try:
        timestamp = now_wib().strftime("%Y-%m-%d %H:%M:%S")
        tanggal = date or now_wib().strftime("%Y-%m-%d")
        row = [timestamp, tanggal, tipe.capitalize(), kategori, amount, description]
        sheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.error("GSheet append error: %s", e)
        global _sheet
        _sheet = None
