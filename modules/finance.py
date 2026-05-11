from bot.callback_utils import make_callback_data
from typing import Dict, Any, Tuple, Optional
from datetime import date
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot.formatter import escape_md, safe_markdown
import db.queries.finance as finance_queries
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def handle_finance_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    """
    Main router for finance-related intents.
    """
    if intent == "finance_log":
        return await _handle_log_expense(pool, data)

    elif intent == "finance_summary" or intent == "view_finance":
        res_text, res_markup = await _generate_finance_summary_text(pool)
        return res_text, res_markup, None

    elif intent == "finance_chart":
        res_text, res_markup = await _generate_finance_chart(pool)
        return res_text, res_markup, None

    elif intent == "list_categories":
        res_text, res_markup = await _list_categories(pool)
        return res_text, res_markup, None

    elif intent == "add_category":
        res_text, res_markup = await _add_category(pool, data)
        return res_text, res_markup, None

    elif intent == "delete_category":
        res_text, res_markup = await _delete_category(pool, data)
        return res_text, res_markup, None

    elif intent == "set_budget":
        res_text, res_markup = await _set_budget(pool, data)
        return res_text, res_markup, None

    elif intent == "finance_undo":
        # item_id might come from data if we are being specific, or we can try to get it from state
        from db.queries.finance import get_last_transaction_id

        last_id = (
            data.get("item_id") or data.get("id") or await get_last_transaction_id(pool)
        )
        if last_id:
            return await undo_last_action(pool, int(last_id))
        return "Nu am găsit nicio tranzacție recentă de anulat.", None, None

    elif intent == "delete_finance" or intent == "delete_transaction":
        tx_id = data.get("id") or data.get("item_id")
        if not tx_id:
            return "Te rog să specifici ID-ul tranzacției de șters.", None, None
        from db.queries.finance import delete_transaction

        success = await delete_transaction(pool, int(tx_id))
        if success:
            return f"✅ Tranzacția cu ID {tx_id} a fost ștearsă.", None, tx_id
        return f"❌ Nu am găsit tranzacția cu ID {tx_id}.", None, None


async def _handle_log_expense(
    pool, data: Dict[str, Any]
) -> Tuple[str, Any, Optional[int]]:
    # 1. Handle Bulk Entries (Agentic)
    entries = data.get("entries")
    if entries and isinstance(entries, list):
        results = []
        last_id = None
        for entry in entries:
            amount = entry.get("amount")
            category = entry.get("category", "altele")
            description = entry.get("description", "")
            tx_type = entry.get("type", "expense")

            if amount is not None:
                last_id = await finance_queries.log_transaction(
                    pool,
                    tx_type=tx_type,
                    amount=amount,
                    category=category,
                    description=description,
                )
                desc_str = f" — *{description}*" if description else ""
                results.append(f"✅ {amount} RON{desc_str} ({category})")

        if not results:
            return "Nu am reușit să extrag nicio cheltuială validă. 💸", None, None

        daily_total = await finance_queries.get_daily_total(pool, date.today())
        final_msg = "\n".join(results)
        final_msg += f"\n\n💸 *Cheltuieli azi:* {daily_total:.2f} RON"
        return final_msg, None, last_id

    # 2. Handle Single Entry (Legacy/Simple)
    amount = data.get("amount")
    category = data.get("category", "altele")
    description = data.get("description", "")
    tx_type = data.get("type", "expense")

    if amount is None:
        return "Te rog să specifici suma (ex: 50 RON). 💸", None, None

    tx_id = await finance_queries.log_transaction(
        pool, tx_type=tx_type, amount=amount, category=category, description=description
    )

    msg = f"✅ {amount} RON la *{category}* înregistrat\\."
    if description:
        msg = f"✅ {amount} RON — *{description}* ({category}) înregistrat\\."

    daily_total = await finance_queries.get_daily_total(pool, date.today())
    msg += f"\n💸 *Cheltuieli azi:* {daily_total:.2f} RON"

    return msg, None, tx_id


async def _list_categories(pool) -> Tuple[str, Any]:
    """Lists all finance categories."""
    categories = await finance_queries.list_categories(pool)
    if not categories:
        return "Nu ai nicio categorie. 💸", None, None

    lines = ["📁 *Categorii de cheltuieli:*\n"]
    for cat in categories:
        icon = cat.get("icon", "💰")
        lines.append(f"{icon} {cat['name']}")

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Categorie Nouă",
                    callback_data=make_callback_data("finance", "add", "category"),
                )
            ],
            [
                InlineKeyboardButton(
                    "◀️ Înapoi", callback_data=make_callback_data("finance", "summary")
                )
            ],
        ]
    )
    return safe_markdown(text), keyboard


async def _add_category(pool, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Adds a new finance category."""
    name = data.get("name")
    icon = data.get("icon", "💰")
    keywords = data.get("keywords", [])

    if not name:
        return "Ce nume pentru categorie?", None, None

    try:
        await finance_queries.add_category(pool, name, icon, keywords)
        return f"✅ Categorie *{escape_md(name)}* adăugată!", None
    except Exception as e:
        return f"Eroare: {str(e)}", None


async def _delete_category(pool, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Deletes a finance category."""
    name = data.get("name")
    if not name:
        return "Ce categorie să șterg?", None, None

    success = await finance_queries.delete_category(pool, name)
    if success:
        return f"✅ Categorie *{escape_md(name)}* ștearsă!", None
    return f"Nu am găsit categoria *{escape_md(name)}*.", None


async def _set_budget(pool, data: Dict[str, Any]) -> Tuple[str, Any]:
    """Sets a budget for a category."""
    category = data.get("category")
    limit = data.get("limit") or data.get("amount")

    if not category or not limit:
        return (
            "Specifică categoria și limita (ex: 'setează buget 500 RON pentru mâncare').",
            None,
        )

    try:
        limit = float(limit)
    except (ValueError, TypeError):
        return "Suma trebuie să fie un număr.", None, None

    from db.queries.finance import set_budget_limit

    await set_budget_limit(pool, category, limit)
    return f"✅ Buget de *{limit} RON* setat pentru *{escape_md(category)}*.", None


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
                    "➕ Cheltuială",
                    callback_data=make_callback_data("finance", "add", "expense"),
                ),
                InlineKeyboardButton(
                    "➕ Venit",
                    callback_data=make_callback_data("finance", "add", "income"),
                ),
            ],
            [
                InlineKeyboardButton(
                    "📈 Grafic Trend",
                    callback_data=make_callback_data("finance", "chart"),
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 Statistici DETALIATE",
                    callback_data=make_callback_data("finance", "stats"),
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Categorii",
                    callback_data=make_callback_data("finance", "categories"),
                )
            ],
        ]
    )

    return text, keyboard


async def _generate_finance_chart(pool) -> Tuple[str, Any]:
    history = await finance_queries.get_finance_history(pool, 30)
    if len(history) < 2:
        return (
            safe_markdown(
                "Am nevoie de măcar 2 zile cu cheltuieli pentru a genera un trend. 📈"
            ),
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

        reply, _, _ = await handle_finance_intent(pool, "finance_log", data)
        await update.message.reply_text(reply, parse_mode="MarkdownV2")
        await clear_state(pool)

    except Exception as e:
        print(f"ERROR in handle_finance_message: {e}")
        traceback.print_exc()
        await update.message.reply_text("A apărut o eroare la logarea finanțelor.")
        await clear_state(pool)


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    """Rolls back the last transaction."""
    if not item_id:
        return False, "ID invalid."

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT amount, category, description FROM finances WHERE id = $1", item_id
        )
        if not row:
            return False, "Tranzacția nu mai există."

    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM finances WHERE id = $1", item_id)
        
        desc = f" ({row['description']})" if row.get("description") else ""
        return True, f"tranzacția: {row['amount']} RON la {row['category']}{desc}"
    except Exception as e:
        return False, str(e)
