from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from database import set_weekly_budget, get_weekly_budgets, get_week_spending, _week_range
from config import KATEGORI_PENGELUARAN

PILIH_KAT_WEEKLY, INPUT_WEEKLY_LIMIT = range(40, 42)


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _bar(pct, length=10):
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


def _week_label():
    monday_str, sunday_str = _week_range()
    fmt = "%d %b"
    monday = datetime.strptime(monday_str, "%Y-%m-%d")
    sunday = datetime.strptime(sunday_str, "%Y-%m-%d")
    return f"{monday.strftime(fmt)} – {sunday.strftime(fmt)}"


async def setbudgetmingguan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = get_weekly_budgets(update.effective_user.id)
    buttons = []
    for cat in KATEGORI_PENGELUARAN:
        label = cat
        if cat in existing:
            label += f" ({format_rupiah(existing[cat])}/minggu)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"wkat_{cat}")])
    await update.message.reply_text(
        "Pilih kategori untuk set budget mingguan:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return PILIH_KAT_WEEKLY


async def pilih_kat_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.replace("wkat_", "")
    context.user_data["weekly_cat"] = cat

    existing = get_weekly_budgets(update.effective_user.id)
    hint = f"\n_(Sekarang: {format_rupiah(existing[cat])}/minggu)_" if cat in existing else ""
    await query.edit_message_text(
        f"Kategori: *{cat}*\n\nMasukkan limit mingguan (contoh: 30000):{hint}",
        parse_mode="Markdown",
    )
    return INPUT_WEEKLY_LIMIT


async def input_weekly_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka positif.")
        return INPUT_WEEKLY_LIMIT

    user_id = update.effective_user.id
    cat = context.user_data["weekly_cat"]
    set_weekly_budget(user_id, cat, amount)

    await update.message.reply_text(
        f"✅ Budget mingguan *{cat}* diset ke *{format_rupiah(amount)}/minggu*.\n\n"
        f"Kamu akan dapat notifikasi otomatis kalau pengeluaran {cat} minggu ini melebihi limit.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


async def cek_budget_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    limits = get_weekly_budgets(user_id)

    if not limits:
        await update.message.reply_text(
            "Belum ada budget mingguan.\nGunakan /setbudgetmingguan untuk mengatur."
        )
        return

    week_label = _week_label()
    lines = [f"*📆 Budget Mingguan — {week_label}*\n"]

    for cat, limit in limits.items():
        spent = get_week_spending(user_id, cat)
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
            f"   {format_rupiah(spent)} / {format_rupiah(limit)}/minggu — {status}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


setbudgetmingguan_handler = ConversationHandler(
    entry_points=[CommandHandler("setbudgetmingguan", setbudgetmingguan_start)],
    states={
        PILIH_KAT_WEEKLY:   [CallbackQueryHandler(pilih_kat_weekly, pattern="^wkat_")],
        INPUT_WEEKLY_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_weekly_limit)],
    },
    fallbacks=[CommandHandler("cancel", cancel_weekly)],
    per_message=False,
    per_chat=True,
)
