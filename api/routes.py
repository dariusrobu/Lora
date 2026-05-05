from aiohttp import web
from api.auth import require_auth
from datetime import datetime, date
import db.queries.projects as project_queries
import db.queries.tasks as task_queries
import db.queries.finance as finance_queries
import db.queries.memory as memory_queries
import db.queries.workout as workout_queries
import db.queries.focus as focus_queries
import db.queries.skills as skills_queries
import db.queries.university as uni_queries
from core.context import build_context


def serialize_dic(d: dict) -> dict:
    """Return a copy of d with date/datetime values converted to ISO strings."""
    return {
        k: v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in d.items()
    }


@require_auth
async def get_projects(request):
    try:
        pool = request.app["pool"]
        projects = await project_queries.list_projects(pool)
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
async def get_tasks(request):
    try:
        pool = request.app["pool"]
        project_id = request.query.get("project_id")
        if project_id:
            project_id = int(project_id)

        tasks = await task_queries.list_tasks(pool, project_id=project_id)
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
        avg = await uni_queries.get_general_average(pool)

        return web.json_response(
            {
                "subjects": [serialize_dic(s) for s in subjects],
                "upcoming_exams": [serialize_dic(e) for e in exams],
                "average_grade": avg,
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
        action = data.get("action")

        import db.queries.shopping as shop_queries
        if action == "buy":
            await shop_queries.mark_item_bought(pool, item_id)
        elif action == "delete":
            # No direct delete by ID in schema yet, but we can mark as bought or similar
            await shop_queries.mark_item_bought(pool, item_id) 
        
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
        data = [{"date": r["date"].isoformat(), "amount": float(r["total"])} for r in rows]
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_insights(request):
    try:
        pool = request.app["pool"]
        # Gather data for Gemini
        tasks = await task_queries.list_tasks(pool)
        finance = await finance_queries.get_monthly_summary(pool, datetime.now().month, datetime.now().year)
        
        # Simple rule-based insights for now, can be LLM-powered later
        insights = []
        if finance["expense"] > finance["income"] * 0.8:
            insights.append({"type": "warning", "text": "Ai cheltuit cam mult luna asta, slow down a bit! 💸"})
        
        high_priority = [t for t in tasks if t["priority"] == "high"]
        if high_priority:
            insights.append({"type": "task", "text": f"Ai {len(high_priority)} task-uri critice care așteaptă. Let's do this! ⚡"})
        
        if not insights:
            insights.append({"type": "info", "text": "Totul arată bine! Ești on track cu obiectivele tale. 🌟"})
            
        return web.json_response(insights[:3])
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
                float(lat), float(lon)
            )
            
        return web.json_response({"status": "success"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_auth
async def get_weather(request):
    try:
        lat = request.query.get("lat")
        lon = request.query.get("lon")
        
        from core.config import OPENWEATHER_API_KEY
        import httpx
        
        if not lat or not lon:
            return web.json_response({"error": "Missing coordinates"}, status=400)
            
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            if res.status_code == 200:
                return web.json_response(res.json())
            else:
                return web.json_response({"error": "Weather API error"}, status=res.status_code)
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
        finance = await finance_queries.get_monthly_summary(pool, datetime.now().month, datetime.now().year)
        shopping = await shopping_queries.list_shopping_items(pool)
        
        # Get user location for weather and nearby insights
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT current_lat, current_lon FROM user_profile LIMIT 1")
            
        insights = []
        
        # 1. Finance Insight
        if finance["expense"] > finance["income"] * 0.8:
            insights.append({"type": "warning", "text": "Ai cheltuit cam mult luna asta, slow down a bit! 💸"})
        
        # 2. Task Insight
        high_priority = [t for t in tasks if t["priority"] == "high"]
        if high_priority:
            insights.append({"type": "task", "text": f"Ai {len(high_priority)} task-uri critice care așteaptă. Let's do this! ⚡"})
            
        # 3. Weather/Location Insight
        if user and user["current_lat"]:
            lat, lon = float(user["current_lat"]), float(user["current_lon"])
            
            # Weather
            from core.config import OPENWEATHER_API_KEY
            import httpx
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            async with httpx.AsyncClient() as client:
                w_res = await client.get(url)
                if w_res.status_code == 200:
                    w_data = w_res.json()
                    main_desc = w_data["weather"][0]["main"].lower()
                    if "rain" in main_desc or "drizzle" in main_desc:
                        insights.append({"type": "warning", "text": "Se anunță ploaie azi. Nu uita umbrela! ☔"})
            
            # Shopping Geofencing Insight
            pending_shopping = [s for s in shopping if not s["is_bought"]]
            if pending_shopping:
                from core.overpass import get_nearby_places
                nearby = await get_nearby_places(lat, lon, radius=500)
                shops = [n for n in nearby if n["type"] in ["supermarket", "convenience", "grocery"]]
                if shops:
                    closest_shop = shops[0]["name"]
                    insights.append({"type": "info", "text": f"Ești lângă {closest_shop}! Ai {len(pending_shopping)} produse de luat. 🛒"})
        
        if not insights:
            insights.append({"type": "info", "text": "Totul arată bine! Ești on track cu obiectivele tale. 🌟"})
            
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
            return web.json_response({"error": "Missing name or coordinates"}, status=400)
            
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO saved_places (name, lat, lon, category)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO UPDATE SET lat = $2, lon = $3, category = $4
                """,
                name, float(lat), float(lon), category
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
        if not title: return web.json_response({"error": "Missing title"}, status=400)
        await task_queries.add_task(pool, title, priority=data.get("priority", "medium"), project_id=data.get("project_id"), due_date=data.get("due_date"))
        return web.json_response({"status": "success"})
    except Exception as e: return web.json_response({"error": str(e)}, status=500)

@require_auth
async def post_finance(request):
    try:
        pool = request.app["pool"]
        data = await request.json()
        amount = data.get("amount")
        if not amount: return web.json_response({"error": "Missing amount"}, status=400)
        await finance_queries.log_transaction(pool, float(amount), data.get("category", "altele"), data.get("description", ""), data.get("type", "expense"))
        return web.json_response({"status": "success"})
    except Exception as e: return web.json_response({"error": str(e)}, status=500)

@require_auth
async def get_workout_stats(request):
    try:
        pool = request.app["pool"]
        stats = await workout_queries.get_workout_stats(pool)
        return web.json_response(stats)
    except Exception as e: return web.json_response({"error": str(e)}, status=500)

@require_auth
async def get_focus_status(request):
    try:
        pool = request.app["pool"]
        # Simplified focus status
        return web.json_response({"active": False, "session_count": 0})
    except Exception as e: return web.json_response({"error": str(e)}, status=500)

@require_auth
async def get_skills_status(request):
    try:
        pool = request.app["pool"]
        skills = await skills_queries.list_skills(pool)
        return web.json_response([dict(s) for s in skills])
    except Exception as e: return web.json_response({"error": str(e)}, status=500)

def setup_api_routes(app):
    app.router.add_get("/api/projects", get_projects)
    app.router.add_get("/api/projects/{project_id}", get_project_by_id)
    app.router.add_get("/api/tasks", get_tasks)
    app.router.add_post("/api/tasks", post_task)
    app.router.add_patch("/api/tasks/{task_id}", patch_task)
    app.router.add_get("/api/finances/summary", get_finance_summary)
    app.router.add_get("/api/finances/chart", get_finance_chart)
    app.router.add_post("/api/finances", post_finance)
    app.router.add_get("/api/university/summary", get_uni_summary)
    app.router.add_get("/api/shopping", get_shopping)
    app.router.add_patch("/api/shopping/{item_id}", patch_shopping)
    app.router.add_get("/api/insights", get_insights)
    app.router.add_post("/api/location", post_location)
    app.router.add_get("/api/weather", get_weather)
    app.router.add_get("/api/nearby", get_nearby)
    app.router.add_get("/api/places", get_places)
    app.router.add_post("/api/places", post_place)
    app.router.add_get("/api/context", get_context)
    app.router.add_get("/api/memory", get_memory)
    app.router.add_post("/api/memory", post_memory)
    app.router.add_get("/api/workout/stats", get_workout_stats)
    app.router.add_get("/api/focus/status", get_focus_status)
    app.router.add_get("/api/skills", get_skills_status)
