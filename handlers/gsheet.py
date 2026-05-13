import json
import logging
import os

import gspread
from telegram import Update
from telegram.ext import ContextTypes

from config import now_wib

logger = logging.getLogger(__name__)

HEADERS = ["Timestamp", "Tanggal", "Tipe", "Kategori", "Jumlah", "Keterangan"]

_sheet = None
_last_error = None


def _get_sheet():
    global _sheet, _last_error
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
        _last_error = str(e)
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


def _sync_all_to_sheet(transactions: list):
    sheet = _get_sheet()
    if sheet is None:
        return -1, _last_error

    try:
        sheet.clear()
        sheet.append_row(HEADERS, value_input_option="USER_ENTERED")

        rows = [
            [
                tx.get("created_at") or tx["date"],
                tx["date"],
                tx["type"].capitalize(),
                tx["category"],
                tx["amount"],
                tx.get("description", ""),
            ]
            for tx in reversed(transactions)
        ]

        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")

        return len(rows), None
    except Exception as e:
        logger.error("GSheet sync error: %s", e)
        global _sheet
        _sheet = None
        return -1, str(e)


async def syncsheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import get_all_transactions_for_export

    user_id = update.effective_user.id
    await update.message.reply_text("Sedang sync ke Google Sheets...")

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GSHEET_ID")

    if not creds_json:
        await update.message.reply_text("❌ Env var GOOGLE_CREDENTIALS_JSON tidak ditemukan.")
        return
    if not sheet_id:
        await update.message.reply_text("❌ Env var GSHEET_ID tidak ditemukan.")
        return

    try:
        import json
        json.loads(creds_json)
    except Exception as e:
        await update.message.reply_text(f"❌ GOOGLE_CREDENTIALS_JSON tidak valid JSON:\n`{e}`", parse_mode="Markdown")
        return

    txs = get_all_transactions_for_export(user_id)
    count, err = _sync_all_to_sheet(txs)

    if count == -1:
        msg = "❌ Gagal koneksi ke Google Sheets."
        if err:
            msg += f"\n\nError: `{err}`"
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif count == 0:
        await update.message.reply_text("Tidak ada transaksi untuk di-sync.")
    else:
        await update.message.reply_text(f"✅ Berhasil sync *{count} transaksi* ke Google Sheets.", parse_mode="Markdown")
