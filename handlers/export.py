import io
import csv
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import get_all_transactions_for_export


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    month = args[0] if args else None

    txs = get_all_transactions_for_export(user_id, month)
    if not txs:
        await update.message.reply_text("Tidak ada transaksi untuk diekspor.")
        return

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Tanggal", "Tipe", "Kategori", "Jumlah", "Keterangan"])
    for tx in txs:
        writer.writerow([
            tx["id"],
            tx["date"],
            tx["type"].capitalize(),
            tx["category"],
            tx["amount"],
            tx["description"],
        ])

    label = month or "semua"
    filename = f"money_tracker_{label}.csv"

    buf.seek(0)
    file_bytes = buf.getvalue().encode("utf-8-sig")  # utf-8-sig agar Excel terbaca dengan benar
    await update.message.reply_document(
        document=io.BytesIO(file_bytes),
        filename=filename,
        caption=f"Export data transaksi — {label}\nTotal: {len(txs)} transaksi",
    )
