from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.finance as finance_queries
from bot.formatter import escape_md
import logging

logger = logging.getLogger(__name__)

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
                cat_total = await finance_queries.get_monthly_total_by_category(pool, category)
                
                alerted_80 = budget['alerted_80']
                alerted_100 = budget['alerted_100']
                
                pct = (float(cat_total) / float(limit)) * 100
                logger.info(f"💰 BUDGET CHECK [{category}]: {cat_total}/{limit} ({pct:.1f}%) | Alerts: 80={alerted_80}, 100={alerted_100}")

                if float(cat_total) >= float(limit) and not alerted_100:
                    warning = f"\n🔴 *Ai depășit bugetul* de {escape_md(category)}! ({int(float(cat_total))} / {int(float(limit))} RON)"
                    await finance_queries.update_budget_alert_flags(pool, category, alerted_80, True)
                elif float(cat_total) >= float(limit) * 0.8 and not alerted_80:
                    warning = f"\n⚠️ *Ai cheltuit 80%* din bugetul de {escape_md(category)} luna asta ({int(float(cat_total))} / {int(float(limit))} RON)"
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
                desc = f" \\({escape_md(tx['description'])}\\)" if tx['description'] else ""
                lines.append(f"• `{date_str}` {emoji} `{tx['amount']} RON` — {escape_md(tx['category'])}{desc}")
            
            return "\n".join(lines), None

        now = datetime.now()
        s = await finance_queries.get_monthly_summary(pool, now.month, now.year)
        
        lines = [f"📊 *Finance Summary ({now.strftime('%B')}):*"]
        lines.append(f"• Income: `{s['income']} RON`")
        lines.append(f"• Expenses: `{s['expense']} RON`")
        lines.append(f"• Net: `{float(s['income']) - float(s['expense'])} RON`")
        
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

    elif intent == "budget_forecast":
        return await generate_forecast(pool)

    return "Finance module is active\\!", None

async def generate_forecast(pool) -> tuple[str, None]:
    from db.queries.finance import get_budget_forecast, get_days_left_in_month
    from bot.formatter import escape_md
    
    forecasts = await get_budget_forecast(pool)
    days_left = await get_days_left_in_month(pool)
    
    if not forecasts:
        return "Nu sunt suficiente date pentru forecast \\(minim câteva zile de cheltuieli\\).", None
    
    lines = [
        f"📈 *Budget Forecast — {days_left} zile rămase în lună*\n"
    ]
    
    has_warnings = False
    for f in forecasts:
        category = escape_md(f['category'] or 'Altele')
        spent = float(f['spent'] or 0)
        projected = float(f['projected_total'] or 0)
        limit = float(f['monthly_limit']) if f.get('monthly_limit') else None
        
        if limit:
            pct = (projected / limit) * 100
            if pct >= 100:
                icon = "🔴"
                has_warnings = True
            elif pct >= 85:
                icon = "🟡"
                has_warnings = True
            else:
                icon = "🟢"
            
            bar_filled = min(int(pct / 10), 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            
            lines.append(
                f"{icon} *{category}*\n"
                f"   Cheltuit: `{int(spent)} RON` · Proiectat: `{int(projected)} RON` / `{int(limit)} RON`\n"
                f"   `{bar}` {int(pct)}%"
            )
        else:
            lines.append(
                f"• *{category}*: `{int(spent)} RON` cheltuit · proiectat `{int(projected)} RON`"
            )
    
    if not has_warnings:
        lines.append("\n✅ Toate categoriile sunt în buget\\.")
    
    return "\n".join(lines), None
