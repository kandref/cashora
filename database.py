import sqlite3
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                type        TEXT NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                description TEXT DEFAULT '',
                date        TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount   REAL NOT NULL,
                month    TEXT NOT NULL,
                UNIQUE(user_id, category, month)
            );

            CREATE TABLE IF NOT EXISTS saldo_awal (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount  REAL NOT NULL,
                month   TEXT NOT NULL,
                UNIQUE(user_id, month)
            );

            CREATE TABLE IF NOT EXISTS daily_budgets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                category    TEXT NOT NULL,
                daily_limit REAL NOT NULL,
                UNIQUE(user_id, category)
            );

            CREATE TABLE IF NOT EXISTS weekly_budgets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                category     TEXT NOT NULL,
                weekly_limit REAL NOT NULL,
                UNIQUE(user_id, category)
            );
        """)


# ── Transactions ──────────────────────────────────────────────────────────────

def add_transaction(user_id, tipe, amount, category, description, date=None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (user_id, type, amount, category, description, date) VALUES (?,?,?,?,?,?)",
            (user_id, tipe, amount, category, description, date),
        )


def get_transactions(user_id, month=None):
    """Return transactions for a user. month format: 'YYYY-MM'"""
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id=? AND strftime('%Y-%m', date)=? ORDER BY date DESC",
            (user_id, month),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_transaction(user_id, tx_id):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM transactions WHERE id=? AND user_id=?",
            (tx_id, user_id),
        )


def get_summary(user_id, month=None):
    """Return total pemasukan, pengeluaran, dan saldo untuk bulan tertentu."""
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT type, SUM(amount) as total
            FROM transactions
            WHERE user_id=? AND strftime('%Y-%m', date)=?
            GROUP BY type
            """,
            (user_id, month),
        ).fetchall()
    result = {"pemasukan": 0.0, "pengeluaran": 0.0}
    for r in rows:
        result[r["type"]] = r["total"]
    result["saldo"] = result["pemasukan"] - result["pengeluaran"]
    return result


def get_spending_by_category(user_id, month=None):
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id=? AND type='pengeluaran' AND strftime('%Y-%m', date)=?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, month),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_transactions_for_export(user_id, month=None):
    if month:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id=? AND strftime('%Y-%m', date)=? ORDER BY date DESC",
                (user_id, month),
            ).fetchall()
    else:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


# ── Budgets ───────────────────────────────────────────────────────────────────

def set_budget(user_id, category, amount, month=None):
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO budgets (user_id, category, amount, month) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id, category, month) DO UPDATE SET amount=excluded.amount",
            (user_id, category, amount, month),
        )


def get_budgets(user_id, month=None):
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM budgets WHERE user_id=? AND month=?",
            (user_id, month),
        ).fetchall()
    return [dict(r) for r in rows]


def get_budget_status(user_id, month=None):
    """Gabungkan budget dengan pengeluaran aktual per kategori."""
    month = month or datetime.now().strftime("%Y-%m")
    budgets = {b["category"]: b["amount"] for b in get_budgets(user_id, month)}
    spending = {s["category"]: s["total"] for s in get_spending_by_category(user_id, month)}

    all_cats = set(budgets) | set(spending)
    result = []
    for cat in all_cats:
        limit = budgets.get(cat)
        spent = spending.get(cat, 0.0)
        result.append({
            "category": cat,
            "limit": limit,
            "spent": spent,
            "over": (spent > limit) if limit is not None else False,
        })
    return sorted(result, key=lambda x: x["spent"], reverse=True)


# ── Saldo Awal ────────────────────────────────────────────────────────────────

def set_saldo_awal(user_id, amount, month=None):
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO saldo_awal (user_id, amount, month) VALUES (?,?,?) "
            "ON CONFLICT(user_id, month) DO UPDATE SET amount=excluded.amount",
            (user_id, amount, month),
        )


def get_saldo_awal(user_id, month=None):
    month = month or datetime.now().strftime("%Y-%m")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT amount FROM saldo_awal WHERE user_id=? AND month=?",
            (user_id, month),
        ).fetchone()
    return row["amount"] if row else None


def get_saldo_sisa(user_id, month=None):
    """Hitung saldo sisa = saldo_awal - pengeluaran + pemasukan bulan ini."""
    month = month or datetime.now().strftime("%Y-%m")
    saldo_awal = get_saldo_awal(user_id, month)
    summary = get_summary(user_id, month)
    if saldo_awal is None:
        return None
    return saldo_awal - summary["pengeluaran"] + summary["pemasukan"]


# ── Daily Budgets ─────────────────────────────────────────────────────────────

def set_daily_budget(user_id, category, daily_limit):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_budgets (user_id, category, daily_limit) VALUES (?,?,?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET daily_limit=excluded.daily_limit",
            (user_id, category, daily_limit),
        )


def get_daily_budgets(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, daily_limit FROM daily_budgets WHERE user_id=?",
            (user_id,),
        ).fetchall()
    return {r["category"]: r["daily_limit"] for r in rows}


def get_today_spending(user_id, category):
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE user_id=? AND category=? AND type='pengeluaran' AND date=?",
            (user_id, category, today),
        ).fetchone()
    return row["total"] if row else 0.0


def check_daily_alert(user_id, category):
    """Kembalikan info alert jika pengeluaran hari ini melebihi daily budget."""
    limits = get_daily_budgets(user_id)
    if category not in limits:
        return None
    limit = limits[category]
    spent_today = get_today_spending(user_id, category)
    if spent_today > limit:
        return {
            "category": category,
            "limit": limit,
            "spent_today": spent_today,
            "over_by": spent_today - limit,
        }
    return None


# ── Weekly Budgets ────────────────────────────────────────────────────────────

def _week_range():
    """Kembalikan (senin, minggu) dalam format YYYY-MM-DD untuk minggu ini."""
    from datetime import timedelta
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def set_weekly_budget(user_id, category, weekly_limit):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO weekly_budgets (user_id, category, weekly_limit) VALUES (?,?,?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET weekly_limit=excluded.weekly_limit",
            (user_id, category, weekly_limit),
        )


def get_weekly_budgets(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, weekly_limit FROM weekly_budgets WHERE user_id=?",
            (user_id,),
        ).fetchall()
    return {r["category"]: r["weekly_limit"] for r in rows}


def get_week_spending(user_id, category):
    monday, sunday = _week_range()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE user_id=? AND category=? AND type='pengeluaran' AND date BETWEEN ? AND ?",
            (user_id, category, monday, sunday),
        ).fetchone()
    return row["total"] if row else 0.0


def get_week_spending_all(user_id):
    """Total semua pengeluaran minggu ini per kategori."""
    monday, sunday = _week_range()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) as total FROM transactions "
            "WHERE user_id=? AND type='pengeluaran' AND date BETWEEN ? AND ? "
            "GROUP BY category",
            (user_id, monday, sunday),
        ).fetchall()
    return {r["category"]: r["total"] for r in rows}


def check_weekly_alert(user_id, category):
    """Kembalikan info alert jika pengeluaran minggu ini melebihi weekly budget."""
    limits = get_weekly_budgets(user_id)
    if category not in limits:
        return None
    limit = limits[category]
    spent = get_week_spending(user_id, category)
    if spent > limit:
        return {
            "category": category,
            "limit": limit,
            "spent_week": spent,
            "over_by": spent - limit,
        }
    return None
