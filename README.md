# Cashora

A personal finance Telegram bot for tracking income, expenses, and investments — built to remove the friction from daily budgeting.

## Features

- **Transaction tracking** — Log income, expenses, and investments with categorized entries via inline keyboard
- **Balance tracking** — Set an opening balance and see it update in real-time after every transaction
- **Budget management** — Set daily, weekly, and monthly limits per category with automatic overspend alerts
- **Monthly reports** — Interactive dashboard via Looker Studio, linked directly from the monthly report
- **Google Sheets sync** — All transactions and closing balances exported automatically to a linked spreadsheet
- **Daily digest** — Automated end-of-day summary with budget progress bars and today's transactions

## Tech Stack

- Python 3.x
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- SQLite
- Looker Studio
- gspread (Google Sheets API)
- APScheduler
- Railway (deployment)

## Setup

### Prerequisites

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- (Optional) A Google Service Account with Sheets API access

### Installation

```bash
git clone https://github.com/kandref/cashora.git
cd cashora
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `DB_PATH` | Path to SQLite database file |
| `GSHEET_ID` | Google Spreadsheet ID (optional) |
| `GOOGLE_CREDENTIALS_JSON` | Google Service Account credentials as JSON string (optional) |

### Running Locally

```bash
python bot.py
```

### Deploy to Railway

1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.app) and connect the repo
3. Add the environment variables in the Railway dashboard
4. Add a persistent volume and set `DB_PATH` to point to it

## Bot Commands

| Command | Description |
|---|---|
| `/catat` | Log a transaction (income / expense / investment) |
| `/saldo` | Check current balance |
| `/laporan` | Monthly report with charts |
| `/riwayat` | Transaction history |
| `/hapus <id>` | Delete a transaction by ID |
| `/budget` | Set monthly budget per category |
| `/dailybudget` | Set daily budget per category |
| `/weeklybudget` | Set weekly budget per category |
| `/gajian` | Quick shortcut to record salary |
| `/export` | Export transactions to CSV |
| `/syncsheet` | Sync all data to Google Sheets |
| `/reset` | Reset data for the current month |

## License

MIT
