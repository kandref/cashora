from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os

load_dotenv()

WIB = timezone(timedelta(hours=7))

def now_wib() -> datetime:
    return datetime.now(WIB)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_PATH = os.getenv("DB_PATH", "money_tracker.db")

KATEGORI_PENGELUARAN = [
    "Makan & Minum",
    "Jajan",
    "Transport",
    "Belanja",
    "Hiburan",
    "Kesehatan",
    "Pendidikan",
    "Kosan",
    "Cicilan",
    "Cicilan HP",
    "Tagihan",
    "Lainnya",
]

KATEGORI_PEMASUKAN = [
    "Gaji",
    "Freelance",
    "Hadiah",
    "Lainnya",
]

KATEGORI_INVESTASI = [
    "Reksadana",
    "Saham",
    "Deposito",
    "Obligasi",
    "Lainnya",
]
