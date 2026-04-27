from aiohttp import web
from api.auth import require_auth
from datetime import datetime, date
import db.queries.projects as project_queries
import db.queries.tasks as task_queries
import db.queries.finance as finance_queries
import db.queries.memory as memory_queries
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
        for p in projects:
            serialize_dic(p)
        return web.json_response(projects)
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

        serialize_dic(project)
        for t in tasks:
            serialize_dic(t)

        project["tasks"] = tasks
        project["goals"] = []  # schema doesn't support goals per project right now

        return web.json_response(project)
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

        for t in tasks:
            serialize_dic(t)

        return web.json_response(tasks)
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

        for f in facts:
            serialize_dic(f)

        return web.json_response(facts)
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


def setup_api_routes(app):
    app.router.add_get("/api/projects", get_projects)
    app.router.add_get("/api/projects/{project_id}", get_project_by_id)
    app.router.add_get("/api/tasks", get_tasks)
    app.router.add_get("/api/finances/summary", get_finance_summary)
    app.router.add_get("/api/context", get_context)
    app.router.add_get("/api/memory", get_memory)
    app.router.add_post("/api/memory", post_memory)
