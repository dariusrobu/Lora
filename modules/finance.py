from typing import Dict, Any, Tuple
from datetime import date
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot.formatter import escape_md, safe_markdown
import db.queries.finance as finance_queries
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def handle_finance_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any]:
    """
    Main router for finance-related intents.
    """
    if intent == "finance_log":
        return await _handle_log_expense(pool, data)

    elif intent == "finance_summary" or intent == "view_finance":
        return await _generate_finance_summary_text(pool)

    elif intent == "finance_chart":
        return await _generate_finance_chart(pool)

    return escape_md(
        "Nu sunt sigură cum să procesez această cerere pentru finanțe. 💸"
    ), None


async def _handle_log_expense(pool, data: Dict[str, Any]) -> Tuple[str, Any]:
    amount = data.get("amount")
    category = data.get("category", "other")
    description = data.get("description", "")
    tx_type = data.get("type", "expense")

    if amount is None:
        return "Te rog să specifici suma (ex: 50 RON). 💸", None

    await finance_queries.log_transaction(
        pool, tx_type=tx_type, amount=amount, category=category, description=description
    )

    msg = f"✅ {amount} RON la *{category}* înregistrat\\."
    if description:
        msg = f"✅ {amount} RON — *{description}* ({category}) înregistrat\\."

    daily_total = await finance_queries.get_daily_total(pool, date.today())
    msg += f"\n💸 *Cheltuieli azi:* {daily_total:.2f} RON"

    return msg, None


async def _generate_finance_summary_text(pool) -> Tuple[str, Any]:
    today = date.today()
    daily_total = await finance_queries.get_daily_total(pool, today)
    daily_txs = await finance_queries.get_daily_transactions(pool, today)
    budget_status = await finance_queries.get_budget_status(pool)

    # Header
    text = f"💰 *Finanțe — {today.strftime('%d %b %Y')}*\n\n"
    text += f"💸 *Cheltuieli azi:* {daily_total:.2f} RON\n\n"

    # Today's breakdown
    if daily_txs:
        text += "📝 *Tranzacții azi:*\n"
        for tx in daily_txs:
            icon = "🔻" if tx["type"] == "expense" else "🔹"
            desc = f" — {tx['description']}" if tx["description"] else ""
            text += f"{icon} {tx['amount']:.2f} RON | {tx['category']}{desc}\n"
        text += "\n"

    # Budget status (last 30 days / monthly)
    if budget_status:
        text += "📊 *Buget lunar:*\n"
        for b in budget_status:
            spent = float(b["current_spent"])
            limit = float(b["monthly_limit"])
            pct = (spent / limit) * 100 if limit > 0 else 0
            bar = "🟩" if pct < 80 else "🟧" if pct < 100 else "🟥"
            text += (
                f"{bar} *{b['category']}:* {spent:.0f}/{limit:.0f} RON ({pct:.1f}%)\n"
            )

    text = safe_markdown(text)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Cheltuială", callback_data="finance_add_expense"
                ),
                InlineKeyboardButton("➕ Venit", callback_data="finance_add_income"),
            ],
            [InlineKeyboardButton("📈 Grafic Trend", callback_data="finance_chart")],
            [
                InlineKeyboardButton(
                    "📊 Statistici DETALIATE", callback_data="finance_stats"
                )
            ],
        ]
    )

    return text, keyboard


async def _generate_finance_chart(pool) -> Tuple[str, Any]:
    history = await finance_queries.get_finance_history(pool, 30)
    if len(history) < 2:
        return (
            "Am nevoie de măcar 2 zile cu cheltuieli pentru a genera un trend. 📈",
            None,
        )

    dates = [row["tx_date"] for row in history]
    totals = [float(row["total"]) for row in history]

    # If there are gaps in dates, matplotlib will handle them, but let's ensure it looks good
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        dates,
        totals,
        marker="o",
        linestyle="-",
        color="#e74c3c",
        linewidth=2,
        label="Cheltuieli Zilnice",
    )
    ax.fill_between(dates, totals, color="#e74c3c", alpha=0.1)

    ax.set_title("Trend Cheltuieli (Ultimele 30 zile)", fontsize=14, pad=15)
    ax.set_ylabel("RON", fontsize=12)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.xticks(rotation=45)

    # Median line
    median = sum(totals) / len(totals)
    ax.axhline(
        median,
        color="#3498db",
        linestyle="--",
        alpha=0.5,
        label=f"Medie: {median:.0f} RON",
    )
    ax.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    plt.close(fig)

    return buf, "photo"


async def handle_finance_message(update, pool, state: dict, text: str) -> None:
    """Parse text input for finance logging when in waiting state."""
    from core.state import clear_state
    import re
    import traceback

    try:
        data = {}

        amount_match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", "."))
        if amount_match:
            data["amount"] = float(amount_match.group(1).replace(",", "."))

        low = text.lower()
        category = "altele"
        if any(
            w in low
            for w in ["mancare", "mâncare", "restaurant", "pizza", "shaorma", "burger"]
        ):
            category = "mâncare"
        elif any(
            w in low for w in ["uber", "taxi", "benzin", "metrou", "bus", "transport"]
        ):
            category = "transport"
        elif any(w in low for w in ["chirie", "internet", "curent", "gaz", "utilitat"]):
            category = "utilități"
        elif any(w in low for w in ["medicament", "doctor", "farmacie", "sanatate"]):
            category = "sănătate"
        elif any(w in low for w in ["haine", "magazin", "amazon", "shopping"]):
            category = "shopping"
        elif any(w in low for w in ["cinema", "bar", "concert", "iesire"]):
            category = "distracție"
        elif any(w in low for w in ["carti", "carte", "amazon"]):
            category = "educație"

        data["category"] = category
        data["description"] = text
        data["type"] = (
            "income"
            if any(w in low for w in ["venit", "salariu", "am primit", "incasat"])
            else "expense"
        )

        reply, _ = await handle_finance_intent(pool, "finance_log", data)
        await update.message.reply_text(reply, parse_mode="MarkdownV2")
        await clear_state(pool)

    except Exception as e:
        print(f"ERROR in handle_finance_message: {e}")
        traceback.print_exc()
        await update.message.reply_text("A apărut o eroare la logarea finanțelor.")
        await clear_state(pool)
