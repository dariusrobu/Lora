from pathlib import Path

from lora_dev.read_only import collect_context, render_plan_input


def test_collect_context_is_read_only_and_contains_request() -> None:
    root = Path(__file__).resolve().parents[1]
    context = collect_context(root, "verifică formularul Finance")
    assert context.request == "verifică formularul Finance"
    assert "dashboard/src/pages/Finance.tsx" in context.relevant_files
    assert "GIT STATUS:" in render_plan_input(context)


def test_git_command_allowlist_rejects_unknown_command(tmp_path: Path) -> None:
    from lora_dev.read_only import _safe_git

    assert _safe_git(tmp_path, "reset", "--hard") == ""
