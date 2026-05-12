from datetime import datetime
from config import now_wib
from database import (
    get_all_user_ids, get_summary, get_saldo_sisa,
    get_budget_status, get_daily_budgets, get_today_spending,
    get_weekly_budgets, get_week_spending, _week_range,
    get_today_transactions,
)

BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _bar(pct, length=10):
    filled = min(int(pct / 100 * length), length)
    return "█" * filled + "░" * (length - filled)


def _build_summary_lines(user_id, now):
    month = now.strftime("%Y-%m")
    label_bulan = f"{BULAN[now.month]} {now.year}"
    label_hari = now.strftime("%d %b %Y")
    summary = get_summary(user_id, month)
    saldo_sisa = get_saldo_sisa(user_id, month)

    lines = [
        f"📊 *Ringkasan Harian — {label_hari}*\n",
        f"💰 Pemasukan   : {format_rupiah(summary['pemasukan'])}",
        f"💸 Pengeluaran : {format_rupiah(summary['pengeluaran'])}",
        f"{'─' * 28}",
    ]

    if saldo_sisa is not None:
        icon = "✅" if saldo_sisa >= 0 else "🔴"
        lines.append(f"{icon} *Saldo sisa  : {format_rupiah(saldo_sisa)}*")

    budgets = [b for b in get_budget_status(user_id, month) if b["limit"] is not None]
    if budgets:
        lines.append(f"\n*📦 Budget Bulanan — {label_bulan}:*")
        for b in budgets:
            pct = (b["spent"] / b["limit"] * 100) if b["limit"] else 0
            icon2 = "🔴" if b["over"] else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{icon2} {b['category']}: {format_rupiah(b['spent'])} / {format_rupiah(b['limit'])}")
            lines.append(f"   {_bar(pct)} {pct:.0f}%")

    daily_limits = get_daily_budgets(user_id)
    if daily_limits:
        lines.append("\n*📅 Budget Harian Hari Ini:*")
        for cat, limit in daily_limits.items():
            spent = get_today_spending(user_id, cat)
            pct = (spent / limit * 100) if limit else 0
            icon2 = "🔴" if spent > limit else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{icon2} {cat}: {format_rupiah(spent)} / {format_rupiah(limit)}")
            lines.append(f"   {_bar(pct)} {pct:.0f}%")

    weekly_limits = get_weekly_budgets(user_id)
    if weekly_limits:
        monday_str, sunday_str = _week_range()
        monday_label = datetime.strptime(monday_str, "%Y-%m-%d").strftime("%d %b")
        sunday_label = datetime.strptime(sunday_str, "%Y-%m-%d").strftime("%d %b")
        lines.append(f"\n*📆 Budget Mingguan ({monday_label}–{sunday_label}):*")
        for cat, limit in weekly_limits.items():
            spent = get_week_spending(user_id, cat)
            pct = (spent / limit * 100) if limit else 0
            icon2 = "🔴" if spent > limit else ("🟡" if pct >= 80 else "🟢")
            lines.append(f"{icon2} {cat}: {format_rupiah(spent)} / {format_rupiah(limit)}")
            lines.append(f"   {_bar(pct)} {pct:.0f}%")

    # Transaksi hari ini
    txs = get_today_transactions(user_id)
    if txs:
        lines.append("\n*🧾 Transaksi Hari Ini:*")
        for tx in txs:
            arrow = "➕" if tx["type"] == "pemasukan" else "➖"
            desc = f" — {tx['description']}" if tx.get("description") else ""
            lines.append(f"{arrow} {tx['category']}: {format_rupiah(tx['amount'])}{desc}")
    else:
        lines.append("\n_Belum ada transaksi hari ini._")

    return "\n".join(lines)


async def daily_summary_job(context):
    now = now_wib()
    for user_id in get_all_user_ids():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=_build_summary_lines(user_id, now),
                parse_mode="Markdown",
            )
        except Exception:
            pass


