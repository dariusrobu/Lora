from typing import Dict, Any, Tuple, Optional
import calendar
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import db.queries.mood as mood_queries
from bot.formatter import escape_md


async def generate_mood_chart(pool, year: int, month: int) -> bytes:
    """Generates a mood line chart using matplotlib and returns PNG bytes."""
    data = await mood_queries.get_monthly_mood_data(pool, year, month)

    if not data or len(data) < 3:
        return None

    days = [d["date"] for d in data]
    values = [d["value"] for d in data]

    # Style: Dark mode
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Colors for points based on value
    mood_colors = {5: "#00ff00", 4: "#0080ff", 3: "#ffff00", 2: "#ff8000", 1: "#ff0000"}
    colors = [mood_colors.get(v, "#ffffff") for v in values]

    # Plot
    ax.plot(days, values, color="#4ecca3", alpha=0.5, linestyle="--", linewidth=1)
    ax.scatter(days, values, c=colors, s=100, edgecolors="white", zorder=5)

    # Monthly average line
    avg_val = sum(values) / len(values)
    ax.axhline(
        avg_val, color="white", linestyle=":", alpha=0.3, label=f"Medie: {avg_val:.1f}"
    )

    # Y-axis labels
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["Rău", "Slab", "Ok", "Bine", "Super"], color="white")
    ax.set_ylim(0.5, 5.5)

    # X-axis labels
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(color="white")

    # Grid
    ax.grid(True, linestyle="--", alpha=0.1)

    # Title
    month_name = calendar.month_name[month]
    plt.title(f"Mood — {month_name} {year}", color="white", pad=20, fontsize=14)

    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Layout
    plt.tight_layout()

    # Save to bytes
    buf = BytesIO()
    plt.savefig(buf, format="png", transparent=False, dpi=120)
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


async def handle_mood_intent(
    pool, intent: str, data: Dict[str, Any], bot
) -> Tuple[Optional[str], Any, Optional[int]]:
    from datetime import datetime

    now = datetime.now()
    year = now.year
    month = now.month

    if intent in ["get_mood_chart", "mood_chart"]:
        png_bytes = await generate_mood_chart(pool, year, month)

        if png_bytes is None:
            return (
                "⚠️ Atenție: Nu am suficiente date de mood încă. Completează jurnalul câteva zile și reîncearcă. ✍️",
                None,
                None,
            )

        # Calculate summary
        mood_data = await mood_queries.get_monthly_mood_data(pool, year, month)
        values = [d["value"] for d in mood_data]
        avg = sum(values) / len(values)

        # Best day
        best_day = max(mood_data, key=lambda x: x["value"])
        best_date = best_day["date"].strftime("%d %b")

        photo = BytesIO(png_bytes)

        caption = (
            f"📊 *Mood {calendar.month_name[month]}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Medie: `{avg:.1f}/5`\n"
            f"🌟 Cea mai bună zi: {escape_md(best_date)}\n\n"
            "_Iată evoluția ta de luna aceasta_"
        )

        from core.config import TELEGRAM_USER_ID
        from telegram.constants import ParseMode

        await bot.send_photo(
            chat_id=TELEGRAM_USER_ID,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return None, None, None  # Already sent

    elif intent == "log_mood":
        mood = data.get("mood")
        if not mood:
            return (
                "⚠️ Atenție: Nu ai specificat starea de spirit. Ex: excelent, ok, slab.",
                None,
                None,
            )

        from db.queries.journal import save_journal_entry, get_journal_entry
        from datetime import date

        today = date.today()
        existing = await get_journal_entry(pool, today)

        reflection = (existing.get("reflection_text") or "") if existing else ""
        focus = (existing.get("tomorrow_focus") or "") if existing else ""

        await save_journal_entry(pool, today, reflection, mood, focus)
        return (
            f"✅ Starea ta de spirit (*{escape_md(mood)}*) a fost înregistrată cu succes în jurnal.",
            None,
            None,
        )

    return "❌ Eroare: Modulul mood nu recunoaște acest intent.", None, None


async def undo_last_action(pool, intent: str, item_id: int) -> Tuple[bool, str]:
    return (
        False,
        "❌ Eroare: Anularea nu este disponibilă pentru starea de spirit (este parte din jurnalul zilnic).",
    )
