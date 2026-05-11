from config import now_wib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import get_conn


def _current_month():
    return now_wib().strftime("%Y-%m")


async def reset_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Reset saldo bulan ini", callback_data="reset_saldo")],
        [InlineKeyboardButton("🗑️ Reset transaksi bulan ini", callback_data="reset_transaksi")],
        [InlineKeyboardButton("⚙️ Reset budget harian", callback_data="reset_budget_harian")],
        [InlineKeyboardButton("⚙️ Reset budget bulanan", callback_data="reset_budget_bulanan")],
        [InlineKeyboardButton("💣 Reset SEMUA data", callback_data="reset_semua")],
        [InlineKeyboardButton("❌ Batal", callback_data="reset_batal")],
    ])
    await update.message.reply_text(
        "🔄 *Reset Data*\n\nPilih yang mau direset:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "reset_batal":
        await query.edit_message_text("Dibatalkan.")
        return

    labels = {
        "reset_saldo":          "saldo bulan ini",
        "reset_transaksi":      "semua transaksi bulan ini",
        "reset_budget_harian":  "semua budget harian",
        "reset_budget_bulanan": "budget bulanan bulan ini",
        "reset_semua":          "SEMUA data (transaksi, saldo, budget)",
    }
    label = labels.get(action, action)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ya, reset", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ Batal", callback_data="reset_batal"),
        ]
    ])
    await query.edit_message_text(
        f"⚠️ *Yakin mau reset {label}?*\n\nData yang direset tidak bisa dikembalikan.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def reset_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.replace("confirm_", "")
    user_id = query.from_user.id
    month = _current_month()

    if action == "reset_batal":
        await query.edit_message_text("Dibatalkan.")
        return

    with get_conn() as conn:
        if action == "reset_saldo":
            conn.execute("DELETE FROM saldo_awal WHERE user_id=? AND month=?", (user_id, month))
            msg = "✅ Saldo bulan ini berhasil direset.\nGunakan /setsaldo untuk isi ulang."

        elif action == "reset_transaksi":
            conn.execute(
                "DELETE FROM transactions WHERE user_id=? AND strftime('%Y-%m', date)=?",
                (user_id, month),
            )
            msg = "✅ Semua transaksi bulan ini berhasil dihapus."

        elif action == "reset_budget_harian":
            conn.execute("DELETE FROM daily_budgets WHERE user_id=?", (user_id,))
            msg = "✅ Budget harian berhasil direset.\nGunakan /setbudgetharian untuk set ulang."

        elif action == "reset_budget_bulanan":
            conn.execute("DELETE FROM budgets WHERE user_id=? AND month=?", (user_id, month))
            msg = "✅ Budget bulanan bulan ini berhasil direset.\nGunakan /setbudget untuk set ulang."

        elif action == "reset_semua":
            conn.execute("DELETE FROM transactions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM saldo_awal WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM budgets WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM daily_budgets WHERE user_id=?", (user_id,))
            msg = "✅ Semua data berhasil dihapus. Mulai fresh! 🆕"

        else:
            msg = "Aksi tidak dikenali."

    await query.edit_message_text(msg)


reset_command = CommandHandler("reset", reset_start)

reset_callbacks = [
    CallbackQueryHandler(reset_confirm, pattern="^reset_"),
    CallbackQueryHandler(reset_execute, pattern="^confirm_reset_"),
]
