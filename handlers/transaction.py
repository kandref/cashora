from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from database import (
    add_transaction, get_transactions, delete_transaction,
    check_daily_alert, check_weekly_alert, get_saldo_sisa,
)
from config import KATEGORI_PENGELUARAN, KATEGORI_PEMASUKAN

# States
PILIH_TIPE, PILIH_KATEGORI, INPUT_JUMLAH, INPUT_DESKRIPSI = range(4)


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _kategori_keyboard(tipe: str) -> InlineKeyboardMarkup:
    cats = KATEGORI_PENGELUARAN if tipe == "pengeluaran" else KATEGORI_PEMASUKAN
    buttons = [
        [InlineKeyboardButton(c, callback_data=f"kat_{c}")]
        for c in cats
    ]
    return InlineKeyboardMarkup(buttons)


async def catat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💸 Pengeluaran", callback_data="tipe_pengeluaran"),
            InlineKeyboardButton("💰 Pemasukan", callback_data="tipe_pemasukan"),
        ]
    ])
    await update.message.reply_text("Mau catat apa?", reply_markup=keyboard)
    return PILIH_TIPE


async def pilih_tipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipe = query.data.replace("tipe_", "")
    context.user_data["tipe"] = tipe
    label = "pengeluaran" if tipe == "pengeluaran" else "pemasukan"
    await query.edit_message_text(
        f"Pilih kategori {label}:",
        reply_markup=_kategori_keyboard(tipe),
    )
    return PILIH_KATEGORI


async def pilih_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kategori = query.data.replace("kat_", "")
    context.user_data["kategori"] = kategori
    await query.edit_message_text(f"Kategori: *{kategori}*\n\nMasukkan jumlah (contoh: 25000):", parse_mode="Markdown")
    return INPUT_JUMLAH


async def input_jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif, contoh: 25000")
        return INPUT_JUMLAH

    context.user_data["amount"] = amount
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Lewati", callback_data="skip_desc")]
    ])
    await update.message.reply_text(
        "Tambahkan keterangan (opsional):",
        reply_markup=keyboard,
    )
    return INPUT_DESKRIPSI


async def input_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    return await _simpan_transaksi(update, context, desc)


async def skip_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await _simpan_transaksi(query, context, "")


async def _simpan_transaksi(update_or_query, context, desc):
    ud = context.user_data
    user = getattr(update_or_query, "effective_user", None) or update_or_query.from_user
    user_id = user.id
    tipe = ud["tipe"]
    kategori = ud["kategori"]
    amount = ud["amount"]

    add_transaction(user_id, tipe, amount, kategori, desc)

    icon = "💸" if tipe == "pengeluaran" else "💰"
    msg = (
        f"{icon} *Transaksi tersimpan!*\n\n"
        f"Tipe     : {tipe.capitalize()}\n"
        f"Kategori : {kategori}\n"
        f"Jumlah   : {format_rupiah(amount)}\n"
    )
    if desc:
        msg += f"Keterangan: {desc}\n"

    alerts = []

    if tipe == "pengeluaran":
        # Cek daily budget alert
        daily_alert = check_daily_alert(user_id, kategori)
        if daily_alert:
            alerts.append(
                f"⚠️ *Budget harian {kategori} terlampaui!*\n"
                f"   Hari ini: {format_rupiah(daily_alert['spent_today'])} "
                f"dari limit {format_rupiah(daily_alert['limit'])}\n"
                f"   (over {format_rupiah(daily_alert['over_by'])})"
            )

        # Cek weekly budget alert
        weekly_alert = check_weekly_alert(user_id, kategori)
        if weekly_alert:
            alerts.append(
                f"📆 *Budget mingguan {kategori} terlampaui!*\n"
                f"   Minggu ini: {format_rupiah(weekly_alert['spent_week'])} "
                f"dari limit {format_rupiah(weekly_alert['limit'])}\n"
                f"   (over {format_rupiah(weekly_alert['over_by'])})"
            )


    # Tampilkan saldo sisa
    saldo_sisa = get_saldo_sisa(user_id)
    if saldo_sisa is not None:
        saldo_icon = "✅" if saldo_sisa >= 0 else "🔴"
        msg += f"\n{saldo_icon} Saldo sisa: *{format_rupiah(saldo_sisa)}*"

    if alerts:
        msg += "\n\n" + "\n\n".join(alerts)

    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(msg, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


# ── Riwayat ───────────────────────────────────────────────────────────────────

async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txs = get_transactions(user_id)

    if not txs:
        await update.message.reply_text("Belum ada transaksi bulan ini.")
        return

    lines = ["*Riwayat bulan ini:*\n"]
    for tx in txs[:20]:
        icon = "💸" if tx["type"] == "pengeluaran" else "💰"
        desc = f" — {tx['description']}" if tx["description"] else ""
        lines.append(
            f"{icon} `#{tx['id']}` {tx['date']} | *{tx['category']}* | {format_rupiah(tx['amount'])}{desc}"
        )

    if len(txs) > 20:
        lines.append(f"\n_...dan {len(txs) - 20} transaksi lainnya. Gunakan /export untuk data lengkap._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Penggunaan: /hapus <id>\nContoh: /hapus 5\n\nLihat ID di /riwayat")
        return

    tx_id = int(args[0])
    delete_transaction(user_id, tx_id)
    await update.message.reply_text(f"Transaksi #{tx_id} dihapus.")


# ── ConversationHandler ───────────────────────────────────────────────────────

catat_handler = ConversationHandler(
    entry_points=[CommandHandler("catat", catat_start)],
    states={
        PILIH_TIPE:     [CallbackQueryHandler(pilih_tipe, pattern="^tipe_")],
        PILIH_KATEGORI: [CallbackQueryHandler(pilih_kategori, pattern="^kat_")],
        INPUT_JUMLAH:   [MessageHandler(filters.TEXT & ~filters.COMMAND, input_jumlah)],
        INPUT_DESKRIPSI: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, input_deskripsi),
            CallbackQueryHandler(skip_deskripsi, pattern="^skip_desc$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
    per_chat=True,
)
