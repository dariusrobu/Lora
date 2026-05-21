from aiohttp import web
from api.auth import require_auth
from datetime import datetime, date, time, timedelta
import decimal
import db.queries.projects as project_queries
import db.queries.tasks as task_queries
import db.queries.finance as finance_queries
import db.queries.memory as memory_queries
import db.queries.shopping as shop_queries
from core.context import build_context


def serialize_dic(d: dict) -> dict:
    """Return a copy of d with date/datetime/time/decimal values converted to strings/floats."""
    res = {}
    for k, v in d.items():
        if isinstance(v, (datetime, date, time)):
            res[k] = v.isoformat()
        elif isinstance(v, decimal.Decimal):
            res[k] = float(v)
        else:
            res[k] = v
    return res


@require_auth
async def get_projects(request):
    try:
        pool = request.app["pool"]
        projects = await project_queries.get_projects_with_counts(pool)
        serialized_projects = [serialize_dic(dict(p)) for p in projects]
        return web.json_response(serialized_projects)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_project_by_id(request):
    try:
        pool = request.app["pool"]
        project_id = int(request.match_info["project_id"])
        project = await project_queries.get_project(pool, project_id)
        if not project:
            return web.json_response({"error": "Project not found"}, status=404)

        # Get tasks
        tasks = await task_queries.list_tasks(pool, project_id=project_id)

        project_dict = serialize_dic(dict(project))
        project_dict["tasks"] = [serialize_dic(dict(t)) for t in tasks]
        project_dict["goals"] = []  # schema doesn't support goals per project right now

        return web.json_response(project_dict)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_profile(request):
    try:
        pool = request.app["pool"]
        from db.queries.profile import get_user_profile
        from core.config import TELEGRAM_USER_ID

        profile = await get_user_profile(pool, TELEGRAM_USER_ID)
        return web.json_response(serialize_dic(profile))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_tasks(request):
    try:
        pool = request.app["pool"]
        project_id = request.query.get("project_id")
        status = request.query.get("status", "pending")

        if status == "all":
            status = None

        if project_id:
            project_id = int(project_id)

        tasks = await task_queries.list_tasks(
            pool, status=status, project_id=project_id
        )
        serialized_tasks = [serialize_dic(dict(t)) for t in tasks]
        return web.json_response(serialized_tasks)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_finance_summary(request):
    try:
        pool = request.app["pool"]
        now = datetime.now()
        month = now.month
        year = now.year

        summary = await finance_queries.get_monthly_summary(pool, month, year)
        categories = await finance_queries.get_monthly_category_totals(
            pool, month, year
        )
        budget_alerts_db = await finance_queries.get_budget_status(pool)

        top_categories = [
            {"category": c["category"], "amount": float(c["total"])}
            for c in categories[:5]
        ]

        budget_alerts = []
        for b in budget_alerts_db:
            if (
                b["current_spent"] > 0 or b["monthly_limit"] > 0
            ):  # just returning all that have a limit
                budget_alerts.append(
                    {
                        "category": b["category"],
                        "limit": float(b["monthly_limit"]),
                        "spent": float(b["current_spent"]),
                    }
                )

        return web.json_response(
            {
                "month": f"{year}-{month:02d}",
                "total_income": summary["income"],
                "total_expenses": summary["expense"],
                "balance": summary["income"] - summary["expense"],
                "top_categories": top_categories,
                "budget_alerts": budget_alerts,
            }
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_finance_history(request):
    try:
        pool = request.app["pool"]
        limit = int(request.query.get("limit", 20))
        transactions = await finance_queries.get_recent_transactions(pool, limit=limit)
        serialized = [serialize_dic(dict(t)) for t in transactions]
        return web.json_response(serialized)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_context(request):
    try:
        pool = request.app["pool"]
        snapshot = await build_context(pool)
        return web.json_response(
            {"snapshot": snapshot, "generated_at": datetime.now().isoformat()}
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_memory(request):
    try:
        pool = request.app["pool"]
        limit = int(request.query.get("limit", 20))
        facts = await memory_queries.list_all_memories(pool)
        facts = facts[:limit]
        serialized_facts = [serialize_dic(dict(f)) for f in facts]
        return web.json_response(serialized_facts)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_memory(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        fact_text = data.get("fact")
        if not fact_text:
            return web.json_response(
                {"error": "Missing 'fact' in request body"}, status=400
            )

        fact_id = await memory_queries.save_memory_fact(
            pool=pool,
            category="personal",
            fact=fact_text,
            source="council_bot",
            confidence=1.0,
        )

        return web.json_response(
            {"id": fact_id, "fact": fact_text, "created_at": datetime.now().isoformat()}
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def patch_task(request):
    try:
        pool = request.app["pool"]
        task_id = int(request.match_info["task_id"])
        data = await request.json()
        action = data.get("action")

        if action == "complete":
            await task_queries.complete_task(pool, task_id)
        elif action == "reopen":
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tasks SET status = 'pending', completed_at = NULL WHERE id = $1",
                    task_id,
                )
        elif action == "delete":
            await task_queries.delete_task(pool, task_id)
        else:
            return web.json_response({"error": "Invalid action"}, status=400)

        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_uni_summary(request):
    try:
        pool = request.app["pool"]
        import db.queries.university as uni_queries

        subjects = await uni_queries.list_subjects(pool)
        exams = await uni_queries.get_upcoming_exams(pool)
        restante = await uni_queries.get_restante(pool)
        avg = await uni_queries.get_general_average(pool)

        return web.json_response(
            {
                "subjects": [serialize_dic(s) for s in subjects],
                "upcoming_exams": [serialize_dic(e) for e in exams],
                "restante": [serialize_dic(r) for r in restante],
                "average_grade": avg,
            }
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_notes(request):
    try:
        pool = request.app["pool"]
        import db.queries.notes as notes_queries

        notes = await notes_queries.list_notes(pool)
        return web.json_response([serialize_dic(n) for n in notes])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_health_summary(request):
    try:
        pool = request.app["pool"]
        import db.queries.health as health_queries

        # Use get_health_history and sort DESC for the dashboard
        logs = await health_queries.get_health_history(pool, days=14)
        sorted_logs = sorted(logs, key=lambda x: x["log_date"], reverse=True)
        return web.json_response([serialize_dic(log) for log in sorted_logs])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_calendar_today(request):
    try:
        pool = request.app["pool"]
        import db.queries.events as event_queries
        import db.queries.schedule as schedule_queries
        from datetime import date

        events = await event_queries.list_events(
            pool, start_date=date.today(), end_date=date.today()
        )
        schedule = await schedule_queries.get_schedule_for_date(pool, date.today())
        return web.json_response(
            {
                "events": [serialize_dic(e) for e in events],
                "schedule": [serialize_dic(s) for s in schedule],
            }
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_shopping(request):
    try:
        pool = request.app["pool"]
        import db.queries.shopping as shop_queries

        items = await shop_queries.list_shopping_items(pool)
        return web.json_response([serialize_dic(i) for i in items])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def patch_shopping(request):
    try:
        pool = request.app["pool"]
        item_id = int(request.match_info["item_id"])
        data = await request.json()

        import db.queries.shopping as shop_queries

        if "is_bought" in data:
            await shop_queries.toggle_item_status(
                pool, item_id, bool(data["is_bought"])
            )
        elif data.get("action") == "buy":
            await shop_queries.toggle_item_status(pool, item_id, True)

        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def clear_shopping(request):
    try:
        pool = request.app["pool"]
        import db.queries.shopping as shop_queries

        await shop_queries.clear_bought_items(pool)
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_finance_chart(request):
    try:
        pool = request.app["pool"]
        # Get last 7 days of spending
        now = datetime.now()
        start_date = (now - timedelta(days=7)).date()

        rows = await finance_queries.get_daily_expenses(pool, start_date, now.date())
        data = [
            {"date": r["date"].isoformat(), "amount": float(r["total"])} for r in rows
        ]
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_location(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        lat = data.get("lat")
        lon = data.get("lon")

        if lat is None or lon is None:
            return web.json_response({"error": "Missing coordinates"}, status=400)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_profile 
                SET current_lat = $1, current_lon = $2, current_location_at = NOW()
                WHERE telegram_id = (SELECT telegram_id FROM user_profile LIMIT 1)
                """,
                float(lat),
                float(lon),
            )

        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_weather(request):
    try:
        lat = request.query.get("lat")
        lon = request.query.get("lon")

        from core.config import OPENWEATHER_API_KEY, WEATHER_CITY
        from db.queries.profile import get_user_profile
        from core.config import TELEGRAM_USER_ID
        import httpx

        if not lat or not lon:
            # Try to get from profile
            pool = request.app["pool"]
            profile = await get_user_profile(pool, TELEGRAM_USER_ID)
            lat = profile.get("latitude")
            lon = profile.get("longitude")

        if lat and lon:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"
        else:
            # Fallback to city
            url = f"https://api.openweathermap.org/data/2.5/weather?q={WEATHER_CITY}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"

        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=10.0)
            if res.status_code == 200:
                return web.json_response(res.json())
            else:
                return web.json_response(
                    {"error": "Weather API error"}, status=res.status_code
                )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_nearby(request):
    try:
        lat = request.query.get("lat")
        lon = request.query.get("lon")
        if not lat or not lon:
            return web.json_response({"error": "Missing coords"}, status=400)

        from core.overpass import get_nearby_places

        places = await get_nearby_places(float(lat), float(lon))
        return web.json_response(places)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_insights(request):
    try:
        pool = request.app["pool"]
        # Gather data for Gemini
        tasks = await task_queries.list_tasks(pool)
        finance = await finance_queries.get_monthly_summary(
            pool, datetime.now().month, datetime.now().year
        )
        shopping = await shop_queries.list_shopping_items(pool)

        # Get user location for weather and nearby insights
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT current_lat, current_lon FROM user_profile LIMIT 1"
            )

        insights = []

        # 1. Finance Insight
        if finance["expense"] > finance["income"] * 0.8:
            insights.append(
                {
                    "type": "warning",
                    "text": "Ai cheltuit cam mult luna asta, slow down a bit! 💸",
                }
            )

        # 2. Task Insight
        high_priority = [t for t in tasks if t["priority"] == "high"]
        if high_priority:
            insights.append(
                {
                    "type": "task",
                    "text": f"Ai {len(high_priority)} task-uri critice care așteaptă. Let's do this! ⚡",
                }
            )

        # 3. Weather/Location Insight
        if user and user["current_lat"]:
            lat, lon = float(user["current_lat"]), float(user["current_lon"])

            # Weather
            from core.config import OPENWEATHER_API_KEY
            import httpx

            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            async with httpx.AsyncClient() as client:
                try:
                    w_res = await client.get(url, timeout=3.0)
                    if w_res.status_code == 200:
                        w_data = w_res.json()
                        main_desc = w_data["weather"][0]["main"].lower()
                        if "rain" in main_desc or "drizzle" in main_desc:
                            insights.append(
                                {
                                    "type": "warning",
                                    "text": "Se anunță ploaie azi. Nu uita umbrela! ☔",
                                }
                            )
                except Exception as e:
                    print(f"Weather insight error: {e}")

            # Shopping Geofencing Insight
            pending_shopping = [s for s in shopping if not s["is_bought"]]
            if pending_shopping:
                from core.overpass import get_nearby_places

                nearby = await get_nearby_places(lat, lon, radius=500)
                shops = [
                    n
                    for n in nearby
                    if n["type"] in ["supermarket", "convenience", "grocery"]
                ]
                if shops:
                    closest_shop = shops[0]["name"]
                    insights.append(
                        {
                            "type": "info",
                            "text": f"Ești lângă {closest_shop}! Ai {len(pending_shopping)} produse de luat. 🛒",
                        }
                    )

        if not insights:
            insights.append(
                {
                    "type": "info",
                    "text": "Totul arată bine! Ești on track cu obiectivele tale. 🌟",
                }
            )

        return web.json_response(insights[:3])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_places(request):
    try:
        pool = request.app["pool"]
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM saved_places ORDER BY name ASC")
            return web.json_response([serialize_dic(dict(r)) for r in rows])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_place(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        name = data.get("name")
        lat = data.get("lat")
        lon = data.get("lon")
        category = data.get("category", "other")

        if not name or lat is None or lon is None:
            return web.json_response(
                {"error": "Missing name or coordinates"}, status=400
            )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO saved_places (name, lat, lon, category)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO UPDATE SET lat = $2, lon = $3, category = $4
                """,
                name,
                float(lat),
                float(lon),
                category,
            )

        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_task(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        title = data.get("title")
        if not title:
            return web.json_response({"error": "Missing title"}, status=400)
        await task_queries.add_task(
            pool,
            title,
            priority=data.get("priority", "medium"),
            project_id=data.get("project_id"),
            due_date=data.get("due_date"),
        )
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_finance(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        amount = data.get("amount")
        if not amount:
            return web.json_response({"error": "Missing amount"}, status=400)
        await finance_queries.log_transaction(
            pool,
            float(amount),
            data.get("category", "altele"),
            data.get("description", ""),
            data.get("type", "expense"),
        )
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_workout_stats(request):
    try:
        pool = request.app["pool"]
        import db.queries.workout as workout_queries

        # Get basic stats (total, avg duration, etc)
        stats = await workout_queries.get_workout_stats(pool, days=30)

        # Get recent workouts with exercises
        recent = await workout_queries.get_recent_workouts(pool, days=14)

        # Get PRs
        prs = await workout_queries.get_personal_records(pool)

        return web.json_response(
            {
                "summary": serialize_dic(stats),
                "recent_workouts": [serialize_dic(w) for w in recent],
                "prs": [serialize_dic(p) for p in prs],
            }
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_focus_status(request):
    try:
        # Simplified focus status
        return web.json_response({"active": False, "session_count": 0})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_skills_status(request):
    try:
        pool = request.app["pool"]
        import db.queries.skills as skill_queries

        # Get all skills
        skills = await skill_queries.get_all_skills(pool)

        rich_skills = []
        for s in skills:
            streak = await skill_queries.get_skill_streak(pool, s["id"])

            # Calculate Level and Progress
            # Simple RPG logic: Level 1 (0-100), Level 2 (100-300), Level 3 (300-600)
            # Level = sqrt(total / 100)
            async with pool.acquire() as conn:
                total_val = (
                    await conn.fetchval(
                        "SELECT SUM(value) FROM skill_logs WHERE skill_id = $1", s["id"]
                    )
                    or 0
                )

            total_val = float(total_val)
            # Quadratic scaling for levels
            # level 1: 0, level 2: 100, level 3: 400, level 4: 900
            level = int(total_val**0.5 / 10) + 1
            current_level_base = ((level - 1) * 10) ** 2
            next_level_base = (level * 10) ** 2

            progress = 0
            if next_level_base > current_level_base:
                progress = int(
                    (
                        (total_val - current_level_base)
                        / (next_level_base - current_level_base)
                    )
                    * 100
                )

            rich_skills.append(
                {
                    **serialize_dic(s),
                    "streak": streak,
                    "level": level,
                    "progress": min(max(progress, 0), 100),
                    "total_exp": total_val,
                }
            )

        return web.json_response(rich_skills)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def post_skill_log(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        skill_id = data.get("skill_id")
        value = data.get("value")
        if not skill_id or value is None:
            return web.json_response({"error": "Missing skill_id or value"}, status=400)

        import db.queries.skills as skill_queries

        await skill_queries.log_skill_value(
            pool, int(skill_id), float(value), metric=data.get("metric")
        )
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_travel_lists(request):
    try:
        pool = request.app["pool"]
        import db.queries.travel as travel_queries

        lists = await travel_queries.get_all_travel_lists(pool)
        print(f"📡 API: Travel lists found: {lists}", flush=True)
        return web.json_response(lists)
    except Exception as e:
        print(f"❌ API ERROR (travel_lists): {e}", flush=True)
        import traceback

        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_travel_items_api(request):
    try:
        pool = request.app["pool"]
        list_name = request.query.get("list_name")
        if not list_name:
            return web.json_response({"error": "Missing list_name"}, status=400)

        import db.queries.travel as travel_queries

        items = await travel_queries.get_travel_items(pool, list_name)
        return web.json_response([serialize_dic(dict(i)) for i in items])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def patch_travel_item(request):
    try:
        pool = request.app["pool"]
        item_id = int(request.match_info["item_id"])
        data = await request.json()

        import db.queries.travel as travel_queries

        if "is_packed" in data:
            await travel_queries.toggle_packed_status(
                pool, item_id, bool(data["is_packed"])
            )

        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def get_ping(request):
    return web.json_response({"status": "ok", "message": "pong"})


def setup_api_routes(app):
    app.router.add_get("/api/projects", get_projects)
    app.router.add_get("/api/projects/{project_id}", get_project_by_id)
    app.router.add_get("/api/tasks", get_tasks)
    app.router.add_get("/api/profile", get_profile)
    app.router.add_post("/api/tasks", post_task)
    app.router.add_patch("/api/tasks/{task_id}", patch_task)
    app.router.add_get("/api/finances/summary", get_finance_summary)
    app.router.add_get("/api/finances/chart", get_finance_chart)
    app.router.add_get("/api/finances/history", get_finance_history)
    app.router.add_post("/api/finances", post_finance)
    app.router.add_get("/api/university/summary", get_uni_summary)
    app.router.add_get("/api/shopping", get_shopping)
    app.router.add_patch("/api/shopping/{item_id}", patch_shopping)
    app.router.add_delete("/api/shopping/clear", clear_shopping)
    app.router.add_get("/api/insights", get_insights)
    app.router.add_post("/api/location", post_location)
    app.router.add_get("/api/weather", get_weather)
    app.router.add_get("/api/nearby", get_nearby)
    app.router.add_get("/api/places", get_places)
    app.router.add_post("/api/places", post_place)
    app.router.add_get("/api/context", get_context)
    app.router.add_get("/api/memory", get_memory)
    app.router.add_post("/api/memory", post_memory)
    app.router.add_get("/api/notes", get_notes)
    app.router.add_get("/api/health/summary", get_health_summary)
    app.router.add_get("/api/calendar/today", get_calendar_today)
    app.router.add_get("/ping", get_ping)
    app.router.add_get("/api/workout/stats", get_workout_stats)
    app.router.add_get("/api/focus/status", get_focus_status)
    app.router.add_get("/api/skills", get_skills_status)
    app.router.add_post("/api/skills/log", post_skill_log)
    app.router.add_get("/api/travel/lists", get_travel_lists)
    app.router.add_get("/api/travel/items", get_travel_items_api)
    app.router.add_patch("/api/travel/items/{item_id}", patch_travel_item)
