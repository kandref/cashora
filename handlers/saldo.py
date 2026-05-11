import calendar
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
from database import (
    set_saldo_awal, get_saldo_awal, get_saldo_sisa,
    get_summary, get_daily_budgets, get_today_spending,
    get_weekly_budgets, get_week_spending, _week_range,
)

INPUT_SALDO = range(20, 21)


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _days_left_in_month():
    now = now_wib()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return last_day - now.day + 1


async def setsaldo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    month = now_wib().strftime("%Y-%m")
    existing = get_saldo_awal(update.effective_user.id, month)
    hint = f"\n_(Saldo sekarang: {format_rupiah(existing)})_" if existing else ""
    await update.message.reply_text(
        f"Masukkan saldo kamu saat ini (contoh: 2800000):{hint}",
        parse_mode="Markdown",
    )
    return INPUT_SALDO


async def input_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    try:
        amount = float(text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Jumlah tidak valid. Masukkan angka, contoh: 2800000")
        return INPUT_SALDO

    user_id = update.effective_user.id
    set_saldo_awal(user_id, amount)

    days_left = _days_left_in_month()
    daily_available = amount / days_left if days_left > 0 else 0

    await update.message.reply_text(
        f"✅ Saldo *{format_rupiah(amount)}* tersimpan!\n\n"
        f"Sisa hari bulan ini: *{days_left} hari*\n"
        f"Rata-rata per hari agar cukup: *{format_rupiah(daily_available)}*",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END


async def cek_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = now_wib()
    month = now.strftime("%Y-%m")

    saldo_awal = get_saldo_awal(user_id, month)
    if saldo_awal is None:
        await update.message.reply_text(
            "Saldo awal belum diset bulan ini.\nGunakan /setsaldo untuk mengisi saldo kamu."
        )
        return

    summary = get_summary(user_id, month)
    saldo_sisa = get_saldo_sisa(user_id, month)
    days_left = _days_left_in_month()
    daily_available = saldo_sisa / days_left if days_left > 0 and saldo_sisa > 0 else 0

    bulan_list = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                  "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    label_bulan = f"{bulan_list[now.month]} {now.year}"

    timestamp = now.strftime("%d %b %Y, %H:%M")
    lines = [
        f"*💰 Saldo — {label_bulan}*",
        f"_Diperbarui: {timestamp}_\n",
        f"Saldo awal   : {format_rupiah(saldo_awal)}",
        f"Pengeluaran  : -{format_rupiah(summary['pengeluaran'])}",
    ]
    if summary["pemasukan"] > 0:
        lines.append(f"Pemasukan    : +{format_rupiah(summary['pemasukan'])}")
    lines.append(f"{'─' * 28}")

    icon = "✅" if saldo_sisa >= 0 else "🔴"
    lines.append(f"{icon} *Saldo sisa  : {format_rupiah(saldo_sisa)}*")
    lines.append(f"\nSisa {days_left} hari | Rata-rata/hari: *{format_rupiah(daily_available)}*")

    # Info budget harian hari ini
    daily_limits = get_daily_budgets(user_id)
    if daily_limits:
        lines.append("\n*📅 Budget harian hari ini:*")
        for cat, limit in daily_limits.items():
            spent = get_today_spending(user_id, cat)
            pct = (spent / limit * 100) if limit else 0
            bar = _bar(pct)
            icon2 = "🔴" if spent > limit else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{icon2} {cat}: {format_rupiah(spent)} / {format_rupiah(limit)}")
            lines.append(f"   {bar} {pct:.0f}%")

    # Info budget mingguan minggu ini
    weekly_limits = get_weekly_budgets(user_id)
    if weekly_limits:
        monday_str, sunday_str = _week_range()
        monday_label = datetime.strptime(monday_str, "%Y-%m-%d").strftime("%d %b")
        sunday_label = datetime.strptime(sunday_str, "%Y-%m-%d").strftime("%d %b")
        lines.append(f"\n*📆 Budget mingguan ({monday_label}–{sunday_label}):*")
        for cat, limit in weekly_limits.items():
            spent = get_week_spending(user_id, cat)
            pct = (spent / limit * 100) if limit else 0
            bar = _bar(pct)
            icon2 = "🔴" if spent > limit else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{icon2} {cat}: {format_rupiah(spent)} / {format_rupiah(limit)}")
            lines.append(f"   {bar} {pct:.0f}%")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _bar(pct, length=10):
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


setsaldo_handler = ConversationHandler(
    entry_points=[CommandHandler("setsaldo", setsaldo_start)],
    states={
        INPUT_SALDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_saldo)],
    },
    fallbacks=[CommandHandler("cancel", cancel_saldo)],
    per_message=False,
    per_chat=True,
)
