from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.finance as finance_queries
from bot.formatter import escape_md

async def handle_finance_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent in ["log_expense", "log_income", "add_expense", "add_income"]:
        type_ = "expense" if "expense" in intent else "income"
        amount = data.get("amount")
        category = data.get("category", "other").lower()
        
        if not amount: return "How much was it?", None
        
        await finance_queries.add_finance(pool, type=type_, amount=float(amount), category=category, description=data.get("description"))
        
        # Budget check for expenses
        warning = ""
        if type_ == "expense":
            budget = await finance_queries.get_budget_status(pool, category)
            if budget and budget['monthly_limit']:
                limit = float(budget['monthly_limit'])
                now = datetime.now()
                summary = await finance_queries.get_monthly_summary(pool, now.month, now.year)
                cat_total = next((c['total'] for c in summary['breakdown'] if c['category'] == category), 0)
                
                alerted_80 = budget['alerted_80']
                alerted_100 = budget['alerted_100']
                
                if cat_total >= limit and not alerted_100:
                    warning = f"\n🔴 *Ai depășit bugetul* de {escape_md(category)}! ({int(cat_total)} / {int(limit)} RON)"
                    await finance_queries.update_budget_alert_flags(pool, category, alerted_80, True)
                elif cat_total >= limit * 0.8 and not alerted_80:
                    warning = f"\n⚠️ *Ai cheltuit 80%* din bugetul de {escape_md(category)} luna asta ({int(cat_total)} / {int(limit)} RON)"
                    await finance_queries.update_budget_alert_flags(pool, category, True, alerted_100)
 
        emoji = "💸" if type_ == "expense" else "💰"
        return f"Logged {emoji} `{amount} RON` — {escape_md(category)}{warning}", None
 
    elif intent in ["finance_summary", "list_finance", "show_finances"]:
        if intent == "list_finance":
            recent = await finance_queries.get_recent_finances(pool, limit=10)
            if not recent:
                return "Nu am găsit nicio tranzacție recentă\\.", None
            
            lines = ["📜 *Tranzacții Recente:*"]
            for tx in recent:
                date_str = tx['tx_date'].strftime("%d %b")
                emoji = "💸" if tx['type'] == 'expense' else "💰"
                desc = f" ({escape_md(tx['description'])})" if tx['description'] else ""
                lines.append(f"• `{date_str}` {emoji} `{tx['amount']} RON` — {escape_md(tx['category'])}{desc}")
            
            return "\n".join(lines), None

        now = datetime.now()
        s = await finance_queries.get_monthly_summary(pool, now.month, now.year)
        
        lines = [f"📊 *Finance Summary ({now.strftime('%B')}):*"]
        lines.append(f"• Income: `{s['income']} RON`")
        lines.append(f"• Expenses: `{s['expense']} RON`")
        lines.append(f"• Net: `{s['income'] - s['expense']} RON`")
        
        if s['breakdown']:
            lines.append("\n*Top Expenses:*")
            for c in s['breakdown'][:3]:
                lines.append(f"• {escape_md(c['category'])}: `{c['total']} RON`")
                
        return "\n".join(lines), None

    elif intent == "set_budget":
        amount = data.get("amount") or data.get("limit")
        category = data.get("category", "other").lower()
        if not amount: return "What is the budget limit?", None
        
        await finance_queries.set_budget(pool, category, float(amount))
        return f"✅ Budget set for *{escape_md(category)}*: `{int(amount)} RON`/month.", None

    return "Finance module is active\\!", None
