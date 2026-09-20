from datetime import datetime
import pytz
from fastapi import APIRouter, Depends
from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.serializers import clean_dict
from core.config import TIMEZONE

router = APIRouter(prefix="/api/widget", tags=["widget"])
LOCAL_TZ = pytz.timezone(TIMEZONE)


@router.get("/summary")
async def widget_summary(user=Depends(get_current_user)):
    """Consolidated endpoint for iOS Home Screen / Lock Screen widgets."""
    pool = await get_pool()
    now = datetime.now(LOCAL_TZ)
    today = now.date()

    # 1. Pending & Done Tasks
    import db.queries.tasks as task_q
    tasks_raw = await task_q.list_tasks(pool, status="pending")
    pending_tasks = []
    for t in tasks_raw:
        td = clean_dict(dict(t))
        pending_tasks.append({
            "id": td["id"],
            "title": td["title"],
            "priority": td.get("priority", "medium"),
            "due_date": td.get("due_date"),
            "project": td.get("project_name") or "",
        })

    tasks_done_today = 0
    async with pool.acquire() as conn:
        done_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE status = 'done' AND completed_at::date = $1", today
        )
        tasks_done_today = done_count or 0

    # 2. Today's Events & Schedule
    upcoming_events = []
    async with pool.acquire() as conn:
        events_raw = await conn.fetch(
            "SELECT title, event_time, event_type FROM events WHERE event_date = $1 ORDER BY event_time ASC NULLS LAST",
            today,
        )
        for e in events_raw:
            ed = clean_dict(dict(e))
            upcoming_events.append({
                "title": ed["title"],
                "time": str(ed["event_time"])[:5] if ed.get("event_time") else "All-day",
                "type": ed.get("event_type", "event"),
            })

    # 3. Health & Water
    water_ml = 0
    water_target = 2500
    sleep_hours = None
    async with pool.acquire() as conn:
        health_row = await conn.fetchrow(
            "SELECT water_ml, sleep_hours, weight_kg FROM health_logs WHERE log_date = $1", today
        )
        if health_row:
            water_ml = health_row["water_ml"] or 0
            sleep_hours = float(health_row["sleep_hours"]) if health_row["sleep_hours"] else None

        user_row = await conn.fetchrow("SELECT water_target_ml, preferred_tone FROM user_profile LIMIT 1")
        if user_row and user_row.get("water_target_ml"):
            water_target = user_row["water_target_ml"]

    # 4. Finance (Today, Month, Last Transaction)
    today_spent = 0.0
    month_spent = 0.0
    last_tx = None
    async with pool.acquire() as conn:
        spent_row = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM finances WHERE tx_date = $1 AND type = 'expense'", today
        )
        if spent_row:
            today_spent = float(spent_row)

        month_start = today.replace(day=1)
        m_spent_row = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM finances WHERE tx_date >= $1 AND type = 'expense'", month_start
        )
        if m_spent_row:
            month_spent = float(m_spent_row)

        tx_row = await conn.fetchrow(
            "SELECT amount, category, description, created_at FROM finances WHERE type = 'expense' ORDER BY id DESC LIMIT 1"
        )
        if tx_row:
            last_tx = {
                "amount": float(tx_row["amount"]),
                "category": tx_row["category"],
                "description": tx_row.get("description") or tx_row["category"],
            }

    # 5. Skills & Habits
    import db.queries.skills as skill_q
    skills_raw = await skill_q.get_all_skills(pool)
    habits = []
    for s in skills_raw:
        sd = clean_dict(dict(s))
        habits.append({
            "name": sd["name"],
            "unit": sd.get("unit", ""),
            "last_value": sd.get("last_value"),
            "done_today": sd.get("last_log_date") == str(today),
        })

    # Day formatting
    day_ro = {
        "Monday": "Luni", "Tuesday": "Marți", "Wednesday": "Miercuri",
        "Thursday": "Joi", "Friday": "Vineri", "Saturday": "Sâmbătă", "Sunday": "Duminică"
    }
    day_name = day_ro.get(now.strftime("%A"), now.strftime("%A"))

    # Month translation
    month_ro = {
        "January": "Ian", "February": "Feb", "March": "Mar", "April": "Apr",
        "May": "Mai", "June": "Iun", "July": "Iul", "August": "Aug",
        "September": "Sep", "October": "Oct", "November": "Noi", "December": "Dec"
    }
    month_name_ro = month_ro.get(now.strftime("%B"), now.strftime("%B"))

    return {
        "date": now.strftime("%d %B %Y"),
        "day_name": day_name,
        "day_short": day_name[:3].upper(),
        "day_number": now.strftime("%d"),
        "month_short": month_name_ro.upper(),
        "time": now.strftime("%H:%M"),
        "tasks": {
            "total_pending": len(pending_tasks),
            "done_today": tasks_done_today,
            "items": pending_tasks[:8],
        },
        "health": {
            "water_ml": water_ml,
            "water_target": water_target,
            "water_percent": min(100, int((water_ml / max(1, water_target)) * 100)),
            "sleep_hours": sleep_hours or 0.0,
            "sleep_target": 8.0,
        },
        "finance": {
            "today_spent": today_spent,
            "month_spent": month_spent,
            "daily_budget": 100.0,
            "currency": "RON",
            "last_transaction": last_tx,
        },
        "events": upcoming_events[:6],
        "habits": habits[:4],
    }


SCRIPT_JS_CODE = """// Variables used by Scriptable.
// icon-color: purple; icon-glyph: bolt;

/**
 * ⚡ LORA ULTRA-MINIMALIST TRANSPARENT WIDGETS
 * Fundal 100% Transparent — Plutește direct peste wallpaper-ul telefonului.
 * 
 * Setează parametrul widget-ului în iOS (Edit Widget ➔ Parameter):
 * - 'tasks'    ➔ 🎯 Medium: Lista de task-uri active & priorități pe 2 coloane
 * - 'rings'    ➔ ⭕ Small: Apple Activity Rings (Buget, Task-uri, Somn)
 * - 'calendar' ➔ 📅 Small: Calendar de zi & Evenimentele de azi
 */

const LORA_URL = "https://adina-acosmistic-pathologically.ngrok-free.dev";

// 🎨 Palette
const COLOR_RED = new Color("#fa2d48");     // Apple Activity Coral
const COLOR_GREEN = new Color("#a3e635");   // Apple Activity Neon Green
const COLOR_BLUE = new Color("#22d3ee");    // Apple Activity Cyan
const COLOR_PURPLE = new Color("#a78bfa");  // Lora Soft Purple
const TEXT_MUTED = new Color("#9ca3af");    // Light Muted Gray

async function fetchLoraData() {
  const req = new Request(`${LORA_URL}/api/widget/summary`);
  req.headers = {
    "ngrok-skip-browser-warning": "true",
    "Bypass-Tunnel-Reminder": "true",
  };
  req.timeoutInterval = 8;
  try {
    return await req.loadJSON();
  } catch {
    return null;
  }
}

const data = await fetchLoraData();
const widget = new ListWidget();
widget.setPadding(10, 10, 10, 10);

// 🪟 FUNDAL 100% TRANSPARENT
widget.backgroundColor = new Color("#000000", 0.0);
widget.url = LORA_URL;

const widgetSize = config.widgetFamily || "medium";
const param = (args.widgetParameter || "").toLowerCase().trim();

if (!data) {
  const err = widget.addText("⚡ LORA OFFLINE");
  err.font = Font.boldSystemFont(12);
  err.textColor = COLOR_RED;
} else if (param === "rings") {
  renderRingsWidget(widget, data);
} else if (param === "calendar") {
  renderCalendarWidget(widget, data);
} else {
  if (widgetSize === "small") {
    renderSmallTasksWidget(widget, data);
  } else {
    renderMediumTasksWidget(widget, data);
  }
}

// ─────────────────────────────────────────────
// 1. 🎯 MEDIUM WIDGET: TASKS LIST (TRANSPARENT)
// ─────────────────────────────────────────────
function renderMediumTasksWidget(w, d) {
  const h = w.addStack();
  h.layoutHorizontally();
  h.centerAlignContent();

  const logo = h.addText("🎯 TASKS");
  logo.font = Font.boldSystemFont(11);
  logo.textColor = COLOR_PURPLE;

  h.addSpacer(6);
  const sub = h.addText(`• ${d.tasks.total_pending} active · ${d.tasks.done_today} done`);
  sub.font = Font.mediumSystemFont(10);
  sub.textColor = TEXT_MUTED;

  h.addSpacer();
  const time = h.addText(d.time);
  time.font = Font.boldSystemFont(10);
  time.textColor = Color.white();

  w.addSpacer(8);

  const main = w.addStack();
  main.layoutHorizontally();

  const col1 = main.addStack();
  col1.layoutVertically();

  const col2 = main.addStack();
  col2.layoutVertically();

  const items = d.tasks.items.slice(0, 6);
  if (items.length === 0) {
    const empty = w.addText("Toate task-urile sunt gata! ✨");
    empty.font = Font.italicSystemFont(11);
    empty.textColor = TEXT_MUTED;
    return;
  }

  items.forEach((t, i) => {
    const targetCol = i < 3 ? col1 : col2;
    const row = targetCol.addStack();
    row.layoutHorizontally();
    row.centerAlignContent();

    const dot = row.addText("● ");
    dot.font = Font.boldSystemFont(8);
    dot.textColor = t.priority === "high" ? COLOR_RED : (t.priority === "medium" ? COLOR_BLUE : TEXT_MUTED);

    let str = t.title;
    if (str.length > 20) str = str.substring(0, 19) + "…";
    const txt = row.addText(str);
    txt.font = Font.systemFont(10);
    txt.textColor = Color.white();

    if (t.project) {
      row.addSpacer(3);
      const tag = row.addText(`[${t.project}]`);
      tag.font = Font.systemFont(8);
      tag.textColor = TEXT_MUTED;
    }

    targetCol.addSpacer(3);
  });

  if (items.length > 3) {
    main.addSpacer(8);
  }
}

function renderSmallTasksWidget(w, d) {
  const h = w.addStack();
  h.layoutHorizontally();
  const logo = h.addText("🎯 TASKS");
  logo.font = Font.boldSystemFont(11);
  logo.textColor = COLOR_PURPLE;
  h.addSpacer();
  const cnt = h.addText(`${d.tasks.total_pending}`);
  cnt.font = Font.boldSystemFont(11);
  cnt.textColor = Color.white();

  w.addSpacer(6);

  const items = d.tasks.items.slice(0, 3);
  if (items.length === 0) {
    const empty = w.addText("Toate task-urile gata! ✨");
    empty.font = Font.italicSystemFont(10);
    empty.textColor = TEXT_MUTED;
    return;
  }

  for (const t of items) {
    const row = w.addStack();
    row.layoutHorizontally();
    const dot = row.addText("● ");
    dot.font = Font.boldSystemFont(8);
    dot.textColor = t.priority === "high" ? COLOR_RED : COLOR_BLUE;

    let str = t.title;
    if (str.length > 17) str = str.substring(0, 16) + "…";
    const txt = row.addText(str);
    txt.font = Font.systemFont(10);
    txt.textColor = Color.white();
    w.addSpacer(3);
  }
}

// ─────────────────────────────────────────────
// 2. ⭕ SMALL WIDGET: APPLE WATCH RINGS (TRANSPARENT)
// ─────────────────────────────────────────────
function renderRingsWidget(w, d) {
  const totalTasks = (d.tasks.done_today || 0) + (d.tasks.total_pending || 0);
  const tasksProgress = totalTasks > 0 ? (d.tasks.done_today / totalTasks) : 0;
  const budgetProgress = (d.finance.today_spent || 0) / (d.finance.daily_budget || 100);
  const sleepProgress = (d.health.sleep_hours || 0) / (d.health.sleep_target || 8);

  const ringsData = [
    { color: COLOR_RED, progress: budgetProgress },   // Outer: Buget
    { color: COLOR_GREEN, progress: tasksProgress },  // Middle: Task-uri
    { color: COLOR_BLUE, progress: sleepProgress },   // Inner: Somn
  ];

  const content = w.addStack();
  content.layoutHorizontally();
  content.centerAlignContent();

  const ringsImg = drawConcentricRings(ringsData, 74, 74);
  const imgElem = content.addImage(ringsImg);
  imgElem.imageSize = new Size(74, 74);

  content.addSpacer(8);

  const statsCol = content.addStack();
  statsCol.layoutVertically();

  // 1. Buget
  const r1 = statsCol.addStack();
  r1.layoutHorizontally();
  const d1 = r1.addText("● ");
  d1.font = Font.boldSystemFont(9);
  d1.textColor = COLOR_RED;
  const t1 = r1.addText(`${d.finance.today_spent.toFixed(0)} ${d.finance.currency}`);
  t1.font = Font.boldSystemFont(10);
  t1.textColor = Color.white();
  statsCol.addSpacer(3);

  // 2. Tasks
  const r2 = statsCol.addStack();
  r2.layoutHorizontally();
  const d2 = r2.addText("● ");
  d2.font = Font.boldSystemFont(9);
  d2.textColor = COLOR_GREEN;
  const t2 = r2.addText(`${d.tasks.done_today}/${totalTasks || 0} done`);
  t2.font = Font.boldSystemFont(10);
  t2.textColor = Color.white();
  statsCol.addSpacer(3);

  // 3. Sleep
  const r3 = statsCol.addStack();
  r3.layoutHorizontally();
  const d3 = r3.addText("● ");
  d3.font = Font.boldSystemFont(9);
  d3.textColor = COLOR_BLUE;
  const t3 = r3.addText(`${d.health.sleep_hours ? d.health.sleep_hours + 'h' : '--'} somn`);
  t3.font = Font.boldSystemFont(10);
  t3.textColor = Color.white();
}

function drawConcentricRings(rings, width, height) {
  const dc = new DrawContext();
  dc.size = new Size(width, height);
  dc.opaque = false;
  dc.respectScreenScale = true;

  const center = new Point(width / 2, height / 2);
  const strokeWidth = 5.5;
  const spacing = 2.5;

  rings.forEach((r, idx) => {
    const radius = (width / 2) - strokeWidth / 2 - (idx * (strokeWidth + spacing));
    if (radius <= 0) return;

    // Track (full circle using addEllipse)
    dc.setStrokeColor(new Color(r.color.hex, 0.20));
    dc.setLineWidth(strokeWidth);
    const bgPath = new Path();
    bgPath.addEllipse(new Rect(center.x - radius, center.y - radius, radius * 2, radius * 2));
    dc.addPath(bgPath);
    dc.strokePath();

    // Progress arc
    const p = Math.min(Math.max(r.progress, 0), 1.0);
    if (p > 0) {
      dc.setStrokeColor(r.color);
      dc.setLineWidth(strokeWidth);

      const startAngle = -Math.PI / 2;
      const totalAngle = p * 2 * Math.PI;
      const steps = Math.max(8, Math.floor(totalAngle * 16));
      const fgPath = new Path();

      const startX = center.x + radius * Math.cos(startAngle);
      const startY = center.y + radius * Math.sin(startAngle);
      fgPath.move(new Point(startX, startY));

      for (let i = 1; i <= steps; i++) {
        const a = startAngle + (totalAngle * (i / steps));
        const x = center.x + radius * Math.cos(a);
        const y = center.y + radius * Math.sin(a);
        fgPath.addLine(new Point(x, y));
      }

      dc.addPath(fgPath);
      dc.strokePath();
    }
  });

  return dc.getImage();
}

// ─────────────────────────────────────────────
// 3. 📅 SMALL WIDGET: DAY CALENDAR & EVENTS (TRANSPARENT)
// ─────────────────────────────────────────────
function renderCalendarWidget(w, d) {
  const top = w.addStack();
  top.layoutHorizontally();
  top.centerAlignContent();

  const dayBadge = top.addStack();
  dayBadge.setPadding(2, 6, 2, 6);
  dayBadge.backgroundColor = new Color(COLOR_RED.hex, 0.18);
  dayBadge.cornerRadius = 6;

  const dayTxt = dayBadge.addText(`${d.day_short}, ${d.day_number} ${d.month_short}`);
  dayTxt.font = Font.boldSystemFont(9);
  dayTxt.textColor = COLOR_RED;

  top.addSpacer();
  const time = top.addText(d.time);
  time.font = Font.boldSystemFont(10);
  time.textColor = TEXT_MUTED;

  w.addSpacer(6);

  const events = d.events || [];
  if (events.length === 0) {
    w.addSpacer(8);
    const noEv = w.addText("Niciun eveniment rămas azi ✨");
    noEv.font = Font.italicSystemFont(10);
    noEv.textColor = TEXT_MUTED;
  } else {
    events.slice(0, 3).forEach((ev) => {
      const row = w.addStack();
      row.layoutHorizontally();
      row.centerAlignContent();

      const icon = row.addText("• ");
      icon.font = Font.boldSystemFont(9);
      icon.textColor = COLOR_RED;

      let str = `${ev.time} ${ev.title}`;
      if (str.length > 20) str = str.substring(0, 19) + "…";
      const txt = row.addText(str);
      txt.font = Font.mediumSystemFont(10);
      txt.textColor = Color.white();

      w.addSpacer(3);
    });
  }
}

widget.refreshAfterDate = new Date(Date.now() + 1000 * 60 * 15);

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentMedium();
}
Script.complete();
"""


@router.get("/script")
async def get_widget_script_page():
    from fastapi.responses import HTMLResponse
    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>⚡ Lora Scriptable Widget</title>
  <style>
    body {{
      background: #090a10;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 24px;
      margin: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .container {{
      max-width: 600px;
      width: 100%;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 800;
      color: #8b5cf6;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    p {{
      font-size: 14px;
      color: #8e92a8;
      line-height: 1.5;
      margin-bottom: 20px;
    }}
    .btn {{
      display: block;
      width: 100%;
      padding: 16px;
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      color: #fff;
      border: none;
      border-radius: 14px;
      font-size: 16px;
      font-weight: 700;
      text-align: center;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
      transition: transform 0.1s, opacity 0.2s;
      margin-bottom: 20px;
    }}
    .btn:active {{
      transform: scale(0.98);
      opacity: 0.9;
    }}
    pre {{
      background: #141624;
      border: 1px solid rgba(255,255,255,0.1);
      padding: 16px;
      border-radius: 12px;
      font-size: 12px;
      color: #06b6d4;
      overflow-x: auto;
      white-space: pre-wrap;
      max-height: 350px;
    }}
    .toast {{
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: #10b981;
      color: #fff;
      padding: 12px 24px;
      border-radius: 30px;
      font-weight: 700;
      font-size: 14px;
      display: none;
      box-shadow: 0 8px 25px rgba(0,0,0,0.5);
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>⚡ Lora iOS Widget</h1>
    <p>Apasă butonul de mai jos pentru a copia codul în clipboard, apoi deschide <b>Scriptable</b> și dă <b>Paste</b>.</p>
    
    <button class="btn" onclick="copyCode()">📋 Copiază Scriptul în Clipboard</button>

    <pre id="codeBlock">{SCRIPT_JS_CODE}</pre>
  </div>

  <div id="toast" class="toast">✓ Copiat în Clipboard!</div>

  <script>
    function copyCode() {{
      const code = document.getElementById('codeBlock').innerText;
      navigator.clipboard.writeText(code).then(() => {{
        const toast = document.getElementById('toast');
        toast.style.display = 'block';
        setTimeout(() => {{ toast.style.display = 'none'; }}, 2500);
      }}).catch(err => {{
        alert('Selectează textul din casetă și apasă Copy.');
      }});
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/raw-script")
async def get_raw_widget_script():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=SCRIPT_JS_CODE)

