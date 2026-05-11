from datetime import datetime
from config import now_wib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from database import add_transaction, set_saldo_awal, get_conn

# States
INPUT_GAJI, KELOLA_POTONGAN, INPUT_NAMA, INPUT_NOMINAL, INPUT_NOTES = range(50, 55)


def fmt(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _total_potongan(potongan: list) -> float:
    return sum(p["nominal"] for p in potongan)


def _build_list_keyboard(potongan: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, p in enumerate(potongan):
        label = f"❌ {p['nama']} — {fmt(p['nominal'])}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"gj_del_{i}")])
    buttons.append([InlineKeyboardButton("➕ Tambah potongan", callback_data="gj_tambah")])
    buttons.append([
        InlineKeyboardButton("✅ Konfirmasi", callback_data="gj_konfirmasi"),
        InlineKeyboardButton("🚫 Batal", callback_data="gj_batal"),
    ])
    return InlineKeyboardMarkup(buttons)


def _list_text(gaji: float, potongan: list) -> str:
    total = _total_potongan(potongan)
    saldo_bersih = gaji - total

    lines = [f"💸 *Gajian — {now_wib().strftime('%B %Y')}*\n"]
    lines.append(f"Gaji masuk: *{fmt(gaji)}*\n")

    if potongan:
        lines.append("*Potongan:*")
        for p in potongan:
            notes = f" _{p['notes']}_" if p.get("notes") else ""
            lines.append(f"• {p['nama']}: {fmt(p['nominal'])}{notes}")
        lines.append(f"\nTotal potongan: {fmt(total)}")
        lines.append(f"{'─' * 28}")
        icon = "✅" if saldo_bersih >= 0 else "🔴"
        lines.append(f"{icon} *Saldo bersih: {fmt(saldo_bersih)}*")
    else:
        lines.append("_Belum ada potongan. Tekan ➕ untuk tambah._")

    lines.append("\n_Tekan ❌ pada item untuk hapus._")
    return "\n".join(lines)


async def gajian_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Masukkan total gaji bulan ini (contoh: 6000000):")
    return INPUT_GAJI


async def input_gaji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        gaji = float(text)
        if gaji <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif.")
        return INPUT_GAJI

    context.user_data["gaji"] = gaji
    context.user_data["potongan"] = []

    msg = await update.message.reply_text(
        _list_text(gaji, []),
        reply_markup=_build_list_keyboard([]),
        parse_mode="Markdown",
    )
    context.user_data["list_msg_id"] = msg.message_id
    return KELOLA_POTONGAN


async def kelola_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    gaji = context.user_data["gaji"]
    potongan = context.user_data["potongan"]

    if data == "gj_tambah":
        await query.message.reply_text("Nama potongan (contoh: Cicilan motor, BPJS, dll):")
        return INPUT_NAMA

    if data.startswith("gj_del_"):
        idx = int(data.replace("gj_del_", ""))
        if 0 <= idx < len(potongan):
            potongan.pop(idx)
        await query.edit_message_text(
            _list_text(gaji, potongan),
            reply_markup=_build_list_keyboard(potongan),
            parse_mode="Markdown",
        )
        return KELOLA_POTONGAN

    if data == "gj_konfirmasi":
        return await _simpan_gajian(query, context)

    if data == "gj_batal":
        context.user_data.clear()
        await query.edit_message_text("Gajian dibatalkan.")
        return ConversationHandler.END

    return KELOLA_POTONGAN


async def input_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama_temp"] = update.message.text.strip()
    await update.message.reply_text(f"Nominal potongan untuk *{context.user_data['nama_temp']}*:", parse_mode="Markdown")
    return INPUT_NOMINAL


async def input_nominal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        nominal = float(text)
        if nominal <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif.")
        return INPUT_NOMINAL

    context.user_data["nominal_temp"] = nominal

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Lewati", callback_data="gj_skip_notes")]
    ])
    await update.message.reply_text("Notes (opsional):", reply_markup=keyboard)
    return INPUT_NOTES


async def input_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    _tambah_potongan(context, notes)
    return await _refresh_list(update.message, context, use_reply=True)


async def skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _tambah_potongan(context, "")
    await query.delete_message()
    return await _refresh_list(None, context, chat_id=query.message.chat_id)


def _tambah_potongan(context, notes):
    context.user_data["potongan"].append({
        "nama": context.user_data.pop("nama_temp"),
        "nominal": context.user_data.pop("nominal_temp"),
        "notes": notes,
    })


async def _refresh_list(message, context, use_reply=False, chat_id=None):
    """Kirim ulang list potongan yang diperbarui (tanpa pesan konfirmasi)."""
    gaji = context.user_data["gaji"]
    potongan = context.user_data["potongan"]

    if use_reply and message:
        msg = await message.reply_text(
            _list_text(gaji, potongan),
            reply_markup=_build_list_keyboard(potongan),
            parse_mode="Markdown",
        )
    else:
        from telegram import Bot
        bot = context.bot
        msg = await bot.send_message(
            chat_id=chat_id,
            text=_list_text(gaji, potongan),
            reply_markup=_build_list_keyboard(potongan),
            parse_mode="Markdown",
        )
    context.user_data["list_msg_id"] = msg.message_id
    return KELOLA_POTONGAN


async def _simpan_gajian(query, context):
    gaji = context.user_data["gaji"]
    potongan = context.user_data["potongan"]
    user_id = query.from_user.id
    today = now_wib().strftime("%Y-%m-%d")
    month = now_wib().strftime("%Y-%m")

    # Catat gaji sebagai pemasukan
    add_transaction(user_id, "pemasukan", gaji, "Gaji", "Gaji masuk", today)

    # Catat setiap potongan sebagai pengeluaran
    for p in potongan:
        add_transaction(user_id, "pengeluaran", p["nominal"], p["nama"], p.get("notes", ""), today)

    # Simpan saldo bersih
    total_potongan = _total_potongan(potongan)
    saldo_bersih = gaji - total_potongan
    set_saldo_awal(user_id, saldo_bersih, month)

    lines = [
        "✅ *Gajian tersimpan!*\n",
        f"Gaji masuk     : {fmt(gaji)}",
        f"Total potongan : {fmt(total_potongan)}",
        f"{'─' * 28}",
        f"💰 Saldo bersih : *{fmt(saldo_bersih)}*",
    ]
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_gajian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


gajian_handler = ConversationHandler(
    entry_points=[CommandHandler("gajian", gajian_start)],
    states={
        INPUT_GAJI:      [MessageHandler(filters.TEXT & ~filters.COMMAND, input_gaji)],
        KELOLA_POTONGAN: [CallbackQueryHandler(kelola_callback, pattern="^gj_")],
        INPUT_NAMA:      [MessageHandler(filters.TEXT & ~filters.COMMAND, input_nama)],
        INPUT_NOMINAL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, input_nominal)],
        INPUT_NOTES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, input_notes),
            CallbackQueryHandler(skip_notes, pattern="^gj_skip_notes$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_gajian)],
    per_message=False,
    per_chat=True,
)
