import os
import sys
import subprocess
import asyncio
import traceback
from typing import Optional

from copilot import CopilotClient
from copilot.tools import define_tool


# ==========================================
# ENV
# ==========================================

WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
if not WORKSPACE:
    print("GITHUB_WORKSPACE not set")
    sys.exit(1)


def get_token() -> Optional[str]:
    return (
        os.getenv("COPILOT_GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_TOKEN")
    )


def ensure_safe_directory():
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", WORKSPACE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


# ==========================================
# TOOL 1: Get changed Python files
# ==========================================

@define_tool(description="Get changed Python files between two git commits.")
async def get_changed_python_files_tool(params: dict) -> dict:
    base_sha = params.get("base_sha")
    head_sha = params.get("head_sha")

    if not base_sha or not head_sha:
        return {"ok": False, "error": "Missing base_sha or head_sha"}

    ensure_safe_directory()

    result = subprocess.run(
        ["git", "diff", "--name-only", base_sha, head_sha],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.returncode != 0:
        return {"ok": False, "error": result.stdout}

    files = [f for f in result.stdout.splitlines() if f.endswith(".py")]

    return {"ok": True, "files": files}


# ==========================================
# TOOL 2: Get file diff
# ==========================================

@define_tool(description="Get git diff for a file between two commits.")
async def get_file_diff_tool(params: dict) -> dict:
    base_sha = params.get("base_sha")
    head_sha = params.get("head_sha")
    file_path = params.get("file_path")
    max_chars = params.get("max_chars", 12000)

    if not base_sha or not head_sha or not file_path:
        return {"ok": False, "error": "Missing required parameters"}

    ensure_safe_directory()

    diff_result = subprocess.run(
        ["git", "diff", base_sha, head_sha, "--", file_path],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if diff_result.returncode != 0:
        return {"ok": False, "error": diff_result.stderr}

    diff = diff_result.stdout.strip()

    if not diff:
        return {"ok": True, "file_path": file_path, "diff": "", "note": "No changes"}

    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n... [truncated]"

    return {"ok": True, "file_path": file_path, "diff": diff}


# ==========================================
# AGENT RUNNER
# ==========================================

async def run_agent(base_sha: str, head_sha: str):

    token = get_token()
    if not token:
        print("No GitHub token found.")
        return

    os.environ["GH_TOKEN"] = token
    os.environ["COPILOT_GITHUB_TOKEN"] = token

    client = CopilotClient()

    try:
        await client.start()

        session = await client.create_session({
            "model": "gpt-4.1",
            "streaming": True,  # ✅ zostaje
            "tools": [
                get_changed_python_files_tool,
                get_file_diff_tool
            ],
        })

        prompt = f"""
You are a senior code review agent.

You have the commit SHAs already:
- base_sha: {base_sha}
- head_sha: {head_sha}

STRICT RULES:
- Do NOT ask for parameters.
- Do NOT request SHAs.
- Do NOT answer until you have called the tools.
- You MUST call get_changed_python_files_tool first, then get_file_diff_tool for each returned file.

TASK:
1) Call get_changed_python_files_tool with:
   base_sha="{base_sha}"
   head_sha="{head_sha}"

2) For each returned Python file, call get_file_diff_tool with:
   base_sha="{base_sha}"
   head_sha="{head_sha}"
   file_path="<that file>"
   max_chars=12000

3) Then output a Markdown report:
- For each file: 2–4 bullet points summarizing the changes.
- Add a "Risks" section if applicable.
"""
        def handle_event(event):
            # event.type może być enumem albo stringiem – zrobimy odporne porównanie
            et = getattr(event, "type", None)
            data = getattr(event, "data", None)

            # Najczęściej: delta content odpowiedzi
            if data is not None:
                chunk = (
                    getattr(data, "delta_content", None)
                    or getattr(data, "deltaContent", None)
                    or getattr(data, "delta_content", None)
                    or ""
                )
                if chunk:
                    print(chunk, end="", flush=True)

            # (opcjonalnie) wykryj koniec – nie zawsze potrzebne
            # Jeśli masz enum SessionEventType, możesz tu dodać warunek na idle.
            # Na razie nie robimy nic, bo po send_and_wait i tak wyjdziesz.

        session.on(handle_event)

        # ==========================================
        # WYWOŁANIE AGENTA
        # ==========================================

        await session.send_and_wait({"prompt": prompt})

        # Dla pewności nowa linia po streamingu
        print("\n", flush=True)

    except Exception as e:
        print("\nERROR:", repr(e))
        traceback.print_exc()

    finally:
        try:
            await client.stop()
        except Exception:
            pass


# ==========================================
# MAIN
# ==========================================

def main():
    base_sha = os.environ.get("INPUT_BASE_SHA")
    head_sha = os.environ.get("INPUT_HEAD_SHA")

    if not base_sha or not head_sha:
        print("Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
        sys.exit(1)

    print(f"Comparing commits:\n  base: {base_sha}\n  head: {head_sha}\n")

    asyncio.run(run_agent(base_sha, head_sha))


if __name__ == "__main__":
    main()