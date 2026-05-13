import warnings
import logging
warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.WARNING)

from datetime import time as dtime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import Conflict, NetworkError

from config import BOT_TOKEN, WIB
from database import init_db
from handlers.daily_summary import daily_summary_job
from handlers.transaction import catat_handler, riwayat, hapus
from handlers.report import laporan
from handlers.budget import budget_handler, cek_budget
from handlers.export import export_csv
from handlers.saldo import setsaldo_handler, cek_saldo
from handlers.gajian import gajian_handler
from handlers.daily_budget import setbudgetharian_handler, cek_budget_harian
from handlers.weekly_budget import setbudgetmingguan_handler, cek_budget_mingguan
from handlers.reset import reset_command, reset_callbacks
from handlers.gsheet import syncsheet


HELP_TEXT = """
*Money Tracker Bot* 💰

*Transaksi:*
/catat — Catat pemasukan atau pengeluaran
/riwayat — Lihat riwayat transaksi bulan ini
/hapus <id> — Hapus transaksi berdasarkan ID

*Laporan:*
/laporan — Laporan & grafik bulan ini
/laporan 2025-03 — Laporan bulan tertentu

*Saldo:*
/gajian — Input gaji + potongan, hitung saldo bersih otomatis
/setsaldo — Set saldo manual
/saldo — Cek saldo sisa + ringkasan hari ini

*Budget Harian:*
/setbudgetharian — Set limit pengeluaran per hari per kategori
/budgetharian — Cek status budget harian hari ini

*Budget Mingguan:*
/setbudgetmingguan — Set limit pengeluaran per minggu per kategori
/budgetmingguan — Cek status budget mingguan (Senin–Minggu)

*Budget Bulanan:*
/setbudget — Set limit budget per kategori per bulan
/budget — Cek status budget bulanan

*Export:*
/export — Export semua transaksi ke CSV
/export 2025-03 — Export bulan tertentu

*Lainnya:*
/reset — Reset data (pilih mau reset apa)

/help — Tampilkan bantuan ini
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Halo, *{name}!* 👋\n\nSelamat datang di *Money Tracker Bot*.\n"
        "Bot ini membantu kamu mencatat dan memantau keuangan harian.\n\n"
        + HELP_TEXT,
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, (Conflict, NetworkError)):
        return
    logging.error("Error: %s", context.error)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tidak ditemukan! Isi file .env terlebih dahulu.")

    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(catat_handler)
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(CommandHandler("hapus", hapus))
    app.add_handler(CommandHandler("laporan", laporan))
    app.add_handler(budget_handler)
    app.add_handler(CommandHandler("budget", cek_budget))
    app.add_handler(CommandHandler("export", export_csv))
    app.add_handler(gajian_handler)
    app.add_handler(setsaldo_handler)
    app.add_handler(CommandHandler("saldo", cek_saldo))
    app.add_handler(setbudgetharian_handler)
    app.add_handler(CommandHandler("budgetharian", cek_budget_harian))
    app.add_handler(setbudgetmingguan_handler)
    app.add_handler(CommandHandler("budgetmingguan", cek_budget_mingguan))
    app.add_handler(reset_command)
    for cb in reset_callbacks:
        app.add_handler(cb)
    app.add_handler(CommandHandler("syncsheet", syncsheet))
    app.add_error_handler(error_handler)

    app.job_queue.run_daily(
        daily_summary_job,
        time=dtime(23, 59, 0, tzinfo=WIB),
        name="daily_summary",
    )

    print("Bot berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
