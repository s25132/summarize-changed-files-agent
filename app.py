import os
import subprocess
import sys
import asyncio
from typing import List, Optional

from copilot import CopilotClient
from copilot.tools import define_tool
from copilot.generated.session_events import SessionEventType
from pydantic import BaseModel, Field
import traceback

class GetChangedPythonFilesParams(BaseModel):
    base_sha: str = Field(description="The base commit SHA")
    head_sha: str = Field(description="The head commit SHA")

class SummarizeChangedFileParams(BaseModel):
    file: str = Field(description="The file to summarize")
    base_sha: str = Field(description="The base commit SHA")
    head_sha: str = Field(description="The head commit SHA")


WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
if not WORKSPACE:
    print("GITHUB_WORKSPACE not set")
    sys.exit(1)

_SAFE_DIR_CONFIGURED = False

def ensure_safe_directory():
    global _SAFE_DIR_CONFIGURED
    if _SAFE_DIR_CONFIGURED:
        return
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", WORKSPACE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    _SAFE_DIR_CONFIGURED = True


@define_tool(description="Get changed Python files between two git commits.")
def get_changed_python_files(params: GetChangedPythonFilesParams) -> List[str]:
    ensure_safe_directory()

    result = subprocess.run(
        ["git", "diff", "--name-only", params.base_sha, params.head_sha],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.returncode != 0:
        # Nie sys.exit w toolu — lepiej wyjątek (albo zwrotka z błędem)
        raise RuntimeError(f"git diff failed:\n{result.stdout}")

    return [f for f in result.stdout.splitlines() if f.endswith(".py")]


@define_tool(description="Get git diff for a file between two commits.")
def summarize_changed_file(params: SummarizeChangedFileParams) -> str:
    ensure_safe_directory()

    diff_result = subprocess.run(
        ["git", "diff", params.base_sha, params.head_sha, "--", params.file],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if diff_result.returncode != 0:
        # Zawsze zwracaj string
        return f"[WARN] git diff failed for {params.file}:\n{diff_result.stderr}".strip()

    diff = diff_result.stdout.strip()
    if not diff:
        return ""

    return diff[:12000]


def get_token() -> Optional[str]:
    return os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")


async def main():
    base_sha = os.environ.get("INPUT_BASE_SHA")
    head_sha = os.environ.get("INPUT_HEAD_SHA")
    if not base_sha or not head_sha:
        print("Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
        sys.exit(1)

    print(f"Base SHA: {base_sha}, Head SHA: {head_sha}")

    gh_token = get_token()
    if not gh_token:
        print("No token env found (COPILOT_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN).")
        sys.exit(1)

    os.environ["GH_TOKEN"] = gh_token
    os.environ["COPILOT_GITHUB_TOKEN"] = gh_token

    print("\nUruchamianie Copilot SDK...")
    client = CopilotClient()

    try:
        await client.start()

        session = await client.create_session({
            "model": "gpt-4.1",
            "streaming": True,
            "tools": [get_changed_python_files, summarize_changed_file],
        })

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                print(event.data.delta_content, end="", flush=True)
            elif event.type == SessionEventType.SESSION_IDLE:
                print()

        session.on(handle_event)

        prompt = f"""
You are a senior code review agent.

You already have the commit SHAs:
- base_sha: {base_sha}
- head_sha: {head_sha}

STRICT RULES:
- Do NOT ask for parameters.
- You MUST call the tools (first get_changed_python_files, then summarize_changed_file for each file).
- Only after using the tools, output the Markdown report.
- Diffs may be truncated; base your review on what you can see.

TASK:
1) Call get_changed_python_files with base_sha="{base_sha}" and head_sha="{head_sha}".
2) For each returned Python file, call summarize_changed_file with:
   base_sha="{base_sha}", head_sha="{head_sha}", file="<that file>"
3) Output Markdown:
- For each file: 2–4 bullet points.
- Include "Risks" section if applicable.
"""
        await session.send_and_wait({"prompt": prompt})

    except Exception:
        print("\n[ERROR] Unhandled exception:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await client.stop()
        except Exception:
            pass


asyncio.run(main())