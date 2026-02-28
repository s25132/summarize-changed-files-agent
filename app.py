import os
import sys
import subprocess
import asyncio
import traceback
from typing import Optional
from dataclasses import dataclass

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
# TOOL PARAM SCHEMAS (IMPORTANT)
# ==========================================

@dataclass
class ChangedFilesParams:
    base_sha: str
    head_sha: str


@dataclass
class FileDiffParams:
    base_sha: str
    head_sha: str
    file_path: str
    max_chars: int = 12000


# ==========================================
# TOOL 1
# ==========================================

@define_tool(description="Get changed Python files between two git commits.")
async def get_changed_python_files_tool(
    params: ChangedFilesParams,
    context=None
) -> dict:
    print(f"[TOOL] get_changed_python_files_tool params={params}", flush=True)

    base_sha = params.base_sha
    head_sha = params.head_sha

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
# TOOL 2
# ==========================================

@define_tool(description="Get git diff for a file between two commits.")
async def get_file_diff_tool(
    params: FileDiffParams,
    context=None
) -> dict:
    print(f"[TOOL] get_file_diff_tool params={params}", flush=True)

    ensure_safe_directory()

    diff_result = subprocess.run(
        ["git", "diff", params.base_sha, params.head_sha, "--", params.file_path],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if diff_result.returncode != 0:
        return {"ok": False, "error": diff_result.stderr}

    diff = (diff_result.stdout or "").strip()

    if not diff:
        return {"ok": True, "file_path": params.file_path, "diff": "", "note": "No changes"}

    if len(diff) > params.max_chars:
        diff = diff[: params.max_chars] + "\n... [truncated]"

    return {"ok": True, "file_path": params.file_path, "diff": diff}


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
            "streaming": True,
            "tools": [
                get_changed_python_files_tool,
                get_file_diff_tool
            ],
        })

        prompt = f"""
You are a senior code review agent.

You already have the commit SHAs:
- base_sha: {base_sha}
- head_sha: {head_sha}

STRICT RULES:
- Do NOT ask for parameters.
- You MUST call the tools with proper parameters.
- First call get_changed_python_files_tool.
- Then call get_file_diff_tool for each returned file.
- Only after using the tools, output the Markdown report.

TASK:
1) Call get_changed_python_files_tool with parameters: {{"base_sha": "{base_sha}", "head_sha": "{head_sha}"}}
2) For each returned Python file, call get_file_diff_tool with parameters: {{"base_sha": "{base_sha}", "head_sha": "{head_sha}", "file_path": "<filename>"}}
3) Output Markdown:
   - For each file: 2–4 bullet points summarizing the changes.
   - Include a "Risks" section if applicable.

EXAMPLE TOOL CALL:
get_changed_python_files_tool({{"base_sha": "{base_sha}", "head_sha": "{head_sha}"}})
"""

        # ==========================================
        # STREAMING HANDLER
        # ==========================================

        def handle_event(event):
            data = getattr(event, "data", None)
            if not data:
                return

            chunk = (
                getattr(data, "delta_content", None)
                or getattr(data, "deltaContent", None)
                or getattr(data, "content", None)
                or getattr(data, "text", None)
                or ""
            )

            if chunk:
                print(chunk, end="", flush=True)

        session.on(handle_event)

        await session.send_and_wait({"prompt": prompt})
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

    print(f"Comparing commits:\n  base: {base_sha}\n  head: {head_sha}\n", flush=True)

    asyncio.run(run_agent(base_sha, head_sha))


if __name__ == "__main__":
    main()