from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from database import set_daily_budget, get_daily_budgets, get_today_spending
from config import KATEGORI_PENGELUARAN

PILIH_KAT_DAILY, INPUT_DAILY_LIMIT = range(30, 32)


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


async def setbudgetharian_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = get_daily_budgets(update.effective_user.id)
    buttons = []
    for cat in KATEGORI_PENGELUARAN:
        label = cat
        if cat in existing:
            label += f" ({format_rupiah(existing[cat])}/hari)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dkat_{cat}")])
    await update.message.reply_text(
        "Pilih kategori untuk set budget harian:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return PILIH_KAT_DAILY


async def pilih_kat_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.replace("dkat_", "")
    context.user_data["daily_cat"] = cat

    existing = get_daily_budgets(update.effective_user.id)
    hint = f"\n_(Sekarang: {format_rupiah(existing[cat])}/hari)_" if cat in existing else ""
    await query.edit_message_text(
        f"Kategori: *{cat}*\n\nMasukkan limit harian (contoh: 50000):{hint}",
        parse_mode="Markdown",
    )
    return INPUT_DAILY_LIMIT


async def input_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif.")
        return INPUT_DAILY_LIMIT

    user_id = update.effective_user.id
    cat = context.user_data["daily_cat"]
    set_daily_budget(user_id, cat, amount)

    await update.message.reply_text(
        f"✅ Budget harian *{cat}* diset ke *{format_rupiah(amount)}/hari*.\n\n"
        f"Kamu akan dapat notifikasi otomatis kalau pengeluaran {cat} hari ini melebihi limit ini.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


async def cek_budget_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    limits = get_daily_budgets(user_id)

    if not limits:
        await update.message.reply_text(
            "Belum ada budget harian.\nGunakan /setbudgetharian untuk mengatur."
        )
        return

    lines = ["*📅 Budget Harian Hari Ini:*\n"]
    for cat, limit in limits.items():
        spent = get_today_spending(user_id, cat)
        sisa = limit - spent
        pct = (spent / limit * 100) if limit else 0
        bar = _bar(pct)
        if spent > limit:
            icon = "🔴"
            status = f"OVER {format_rupiah(abs(sisa))}"
        elif pct >= 80:
            icon = "🟡"
            status = f"sisa {format_rupiah(sisa)}"
        else:
            icon = "🟢"
            status = f"sisa {format_rupiah(sisa)}"

        lines.append(
            f"{icon} *{cat}*\n"
            f"   {bar} {pct:.0f}%\n"
            f"   {format_rupiah(spent)} / {format_rupiah(limit)}/hari — {status}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _bar(pct, length=10):
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


setbudgetharian_handler = ConversationHandler(
    entry_points=[CommandHandler("setbudgetharian", setbudgetharian_start)],
    states={
        PILIH_KAT_DAILY:   [CallbackQueryHandler(pilih_kat_daily, pattern="^dkat_")],
        INPUT_DAILY_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_daily_limit)],
    },
    fallbacks=[CommandHandler("cancel", cancel_daily)],
    per_message=False,
    per_chat=True,
)
