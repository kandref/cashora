import io
import calendar
from config import now_wib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from telegram import Update
from telegram.ext import ContextTypes

from database import get_summary, get_spending_by_category, get_transactions


def format_rupiah(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _current_month_label():
    now = now_wib()
    bulan = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    return f"{bulan[now.month]} {now.year}"


async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    month = args[0] if args else now_wib().strftime("%Y-%m")

    summary = get_summary(user_id, month)
    spending = get_spending_by_category(user_id, month)

    label = month
    try:
        y, m = month.split("-")
        bulan = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember",
        ]
        label = f"{bulan[int(m)]} {y}"
    except Exception:
        pass

    text = (
        f"*Laporan {label}*\n\n"
        f"💰 Pemasukan  : {format_rupiah(summary['pemasukan'])}\n"
        f"💸 Pengeluaran: {format_rupiah(summary['pengeluaran'])}\n"
        f"{'➕' if summary['saldo'] >= 0 else '➖'} Saldo       : {format_rupiah(abs(summary['saldo']))}"
        + (" (surplus)" if summary['saldo'] >= 0 else " (defisit)")
    )

    if not spending:
        await update.message.reply_text(text + "\n\n_Belum ada pengeluaran bulan ini._", parse_mode="Markdown")
        return

    # Detail per kategori
    text += "\n\n*Pengeluaran per kategori:*"
    for s in spending:
        pct = (s["total"] / summary["pengeluaran"] * 100) if summary["pengeluaran"] else 0
        text += f"\n• {s['category']}: {format_rupiah(s['total'])} ({pct:.1f}%)"

    await update.message.reply_text(text, parse_mode="Markdown")

    # Kirim chart pie
    chart_buf = _make_pie_chart(spending, label)
    if chart_buf:
        await update.message.reply_photo(photo=chart_buf, caption=f"Grafik pengeluaran {label}")

    # Kirim chart harian
    txs = get_transactions(user_id, month)
    bar_buf = _make_daily_bar(txs, month, label)
    if bar_buf:
        await update.message.reply_photo(photo=bar_buf, caption=f"Pengeluaran harian {label}")


def _make_pie_chart(spending: list, label: str) -> io.BytesIO | None:
    if not spending:
        return None

    cats = [s["category"] for s in spending]
    vals = [s["total"] for s in spending]

    colors = plt.cm.Set3.colors[:len(cats)]

    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, texts, autotexts = ax.pie(
        vals,
        labels=None,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.75,
    )
    for at in autotexts:
        at.set_fontsize(9)

    patches = [mpatches.Patch(color=colors[i], label=cats[i]) for i in range(len(cats))]
    ax.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8)
    ax.set_title(f"Pengeluaran {label}", fontsize=12, fontweight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_daily_bar(txs: list, month: str, label: str) -> io.BytesIO | None:
    pengeluaran = [t for t in txs if t["type"] == "pengeluaran"]
    if not pengeluaran:
        return None

    try:
        y, m = int(month.split("-")[0]), int(month.split("-")[1])
        days_in_month = calendar.monthrange(y, m)[1]
    except Exception:
        return None

    daily = {}
    for tx in pengeluaran:
        day = int(tx["date"].split("-")[2])
        daily[day] = daily.get(day, 0) + tx["amount"]

    days = list(range(1, days_in_month + 1))
    amounts = [daily.get(d, 0) for d in days]

    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(days, amounts, color="#FF6B6B", alpha=0.8, width=0.7)
    ax.set_xlabel("Tanggal", fontsize=10)
    ax.set_ylabel("Jumlah (Rp)", fontsize=10)
    ax.set_title(f"Pengeluaran Harian — {label}", fontsize=12, fontweight="bold")
    ax.set_xticks(days)
    ax.tick_params(axis="x", labelsize=7)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e3:.0f}K" if x < 1e6 else f"{x/1e6:.1f}M"))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
