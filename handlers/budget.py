from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from database import set_budget, get_budget_status
from config import KATEGORI_PENGELUARAN

PILIH_KATEGORI_BUDGET, INPUT_LIMIT = range(10, 12)


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


async def budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(c, callback_data=f"bkat_{c}")]
        for c in KATEGORI_PENGELUARAN
    ]
    await update.message.reply_text(
        "Pilih kategori untuk set budget:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return PILIH_KATEGORI_BUDGET


async def pilih_kategori_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kategori = query.data.replace("bkat_", "")
    context.user_data["budget_kategori"] = kategori
    await query.edit_message_text(
        f"Kategori: *{kategori}*\n\nMasukkan limit budget bulan ini (contoh: 500000):",
        parse_mode="Markdown",
    )
    return INPUT_LIMIT


async def input_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif.")
        return INPUT_LIMIT

    user_id = update.effective_user.id
    kategori = context.user_data["budget_kategori"]
    set_budget(user_id, kategori, amount)

    await update.message.reply_text(
        f"✅ Budget *{kategori}* diset ke *{format_rupiah(amount)}* untuk bulan ini.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


async def cek_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status = get_budget_status(user_id)

    if not status:
        await update.message.reply_text(
            "Belum ada data budget atau pengeluaran bulan ini.\n"
            "Set budget dengan /setbudget"
        )
        return

    lines = ["*Status Budget Bulan Ini:*\n"]
    for s in status:
        spent = format_rupiah(s["spent"])
        if s["limit"] is not None:
            limit = format_rupiah(s["limit"])
            pct = (s["spent"] / s["limit"] * 100) if s["limit"] else 0
            bar = _progress_bar(pct)
            icon = "🔴" if s["over"] else ("🟡" if pct >= 80 else "🟢")
            lines.append(
                f"{icon} *{s['category']}*\n"
                f"   {bar} {pct:.0f}%\n"
                f"   {spent} / {limit}\n"
            )
        else:
            lines.append(f"⚪ *{s['category']}*\n   {spent} (tidak ada limit)\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _progress_bar(pct: float, length: int = 10) -> str:
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


budget_handler = ConversationHandler(
    entry_points=[CommandHandler("setbudget", budget_start)],
    states={
        PILIH_KATEGORI_BUDGET: [CallbackQueryHandler(pilih_kategori_budget, pattern="^bkat_")],
        INPUT_LIMIT:           [MessageHandler(filters.TEXT & ~filters.COMMAND, input_limit)],
    },
    fallbacks=[CommandHandler("cancel", cancel_budget)],
    per_message=False,
    per_chat=True,
)
