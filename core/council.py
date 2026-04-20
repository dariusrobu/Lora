"""
Council API Integration.
Fetches decisions, projects, and translations from the Council multi-agent system.
"""

import httpx
from typing import Any, Dict, List
from core.config import COUNCIL_API_URL


async def get_projects() -> List[Dict[str, Any]]:
    """Fetches strategic projects from the Council API."""
    if not COUNCIL_API_URL:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{COUNCIL_API_URL}/projects")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Council API error: {e}")

    return []


async def get_decisions(project_id: int) -> List[Dict[str, Any]]:
    """Fetches decisions for a specific project from Council API."""
    if not COUNCIL_API_URL:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{COUNCIL_API_URL}/decisions/{project_id}")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Council decisions API error: {e}")

    return []


async def get_recent_decisions(limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches recent decisions across all projects."""
    if not COUNCIL_API_URL:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{COUNCIL_API_URL}/decisions?limit={limit}")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Council recent decisions API error: {e}")

    return []


async def get_strategy_summary() -> str:
    """Gets a summary of current strategic priorities from Council."""
    projects = await get_projects()
    if not projects:
        return ""

    priority_projects = [
        p for p in projects if p.get("priority") in ["high", "critical"]
    ]
    if not priority_projects:
        priority_projects = projects[:3]

    lines = ["🎯 *Strategic Priorities:*"]
    for p in priority_projects:
        name = p.get("name", "Unnamed")
        status = p.get("status", "unknown")
        emoji = (
            "🔴" if status == "blocked" else "🟡" if status == "in_progress" else "🟢"
        )
        lines.append(f"{emoji} *{name}*")

    return "\n".join(lines)


async def send_feedback_to_cto(
    difficulty: int, task_title: str, context: str = ""
) -> bool:
    """Sends feedback data to CTO bot via Council API."""
    if not COUNCIL_API_URL:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{COUNCIL_API_URL}/feedback",
                json={
                    "task": task_title,
                    "difficulty": difficulty,
                    "context": context,
                    "source": "lora",
                },
            )
            return response.status_code == 200
    except Exception as e:
        print(f"Failed to send feedback to CTO: {e}")
        return False
