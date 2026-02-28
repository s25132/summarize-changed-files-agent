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
            "streaming": True,
            "tools": [
                get_changed_python_files_tool,
                get_file_diff_tool
            ],
        })

        prompt = f"""
You are a senior code review agent.

1. Call get_changed_python_files_tool with:
   base_sha="{base_sha}"
   head_sha="{head_sha}"

2. For each returned Python file, call get_file_diff_tool.

3. Summarize each file in 2–4 bullet points.

4. If you detect risks (breaking changes, security, missing tests),
   add a short "Risks" section.

Return the final report in Markdown.
"""

        async for event in session.send_stream({"prompt": prompt}):

            # Model writes text
            if getattr(event, "type", None) == "content":
                print(event.data.content, end="", flush=True)

            # Model calls tool
            elif getattr(event, "type", None) == "tool_call":
                tool_name = event.data.name
                tool_args = event.data.arguments
                tool_call_id = event.data.id

                if tool_name == "get_changed_python_files_tool":
                    result = await get_changed_python_files_tool(tool_args)

                elif tool_name == "get_file_diff_tool":
                    result = await get_file_diff_tool(tool_args)

                else:
                    result = {"ok": False, "error": f"Unknown tool {tool_name}"}

                await session.send_tool_result({
                    "tool_call_id": tool_call_id,
                    "result": result,
                })

            elif getattr(event, "type", None) == "done":
                break

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