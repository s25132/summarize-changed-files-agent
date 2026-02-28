# hello-python-docker-action


w .github/workflows/action.yaml

name: Test Docker Action

on:
  push:
    inputs:
      base_sha:
        description: "Base commit SHA (older)"
        required: true
      head_sha:
        description: "Head commit SHA (newer)"
        required: true
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Print changed Python files
        uses: s25132/hello-python-docker-action@v1
        with:
          base_sha: HEAD~1
          head_sha: HEAD


--------------------------------------------------------------------------------------------\
import os
import re
import subprocess
import asyncio
from typing import List

from agent_framework.github import GitHubCopilotAgent

WORKSPACE = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
TESTS_DIR = os.path.join(WORKSPACE, "tests")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


# -----------------------
# Tools
# -----------------------

def ensure_tests_dir() -> str:
    """Ensure tests/ directory exists."""
    os.makedirs(TESTS_DIR, exist_ok=True)
    return "tests/ directory ensured"


def list_changed_files(base_sha: str, head_sha: str) -> List[str]:
    """Return list of changed Python files between two commits."""
    p = _run(["git", "diff", "--name-only", base_sha, head_sha])
    if p.returncode != 0:
        raise RuntimeError(f"git diff --name-only failed:\n{p.stderr}\n{p.stdout}")
    return [f for f in p.stdout.splitlines() if f.endswith(".py")]


def get_diff(base_sha: str, head_sha: str, path: str) -> str:
    """Return git diff for a single file (truncated)."""
    p = _run(["git", "diff", "--unified=0", base_sha, head_sha, "--", path])
    if p.returncode != 0:
        raise RuntimeError(f"git diff failed for {path}:\n{p.stderr}\n{p.stdout}")
    out = p.stdout.strip()
    if not out:
        return "(no diff)"
    return (out[:12000] + "\n\n...[TRUNCATED]...") if len(out) > 12000 else out


def read_file(path: str, max_chars: int = 12000) -> str:
    """Read file content from repo (truncated)."""
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return "(file does not exist)"
    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()
    return data[:max_chars] + ("\n\n...[TRUNCATED]..." if len(data) > max_chars else "")


def map_source_to_test(path: str) -> str:
    """
    Deterministic mapping from source file path -> test filename under tests/.
    Examples:
      src/foo.py   -> test_src_foo.py
      foo.py       -> test_foo.py
      a/b/c.py     -> test_a_b_c.py
    """
    clean = path.replace("\\", "/")
    if clean.endswith(".py"):
        clean = clean[:-3]
    clean = clean.replace("/", "_")
    return f"test_{clean}.py"


def plan_tests(source_file: str, diff: str) -> str:
    """
    Create a concise, deterministic test plan template based on a code diff.
    The LLM must fill this template in its response text.
    """
    return (
        f"TEST PLAN FOR {source_file}\n"
        f"- Behaviors changed/added:\n"
        f"  - \n"
        f"- Test cases (happy path + edge cases):\n"
        f"  - \n"
        f"- Mocks/fakes needed:\n"
        f"  - \n"
        f"- What should NOT be tested (out of scope):\n"
        f"  - \n"
        f"- Explicit exclusions (MUST): snapshots, randomness, time, sleep, network\n"
    )


def replan_tests(source_file: str, previous_plan: str, test_output: str) -> str:
    """
    Create a deterministic REPLAN template after failed tests or guard rejection.
    The LLM must fill this template (update the plan) BEFORE writing updated tests.
    """
    # We intentionally don't embed full previous_plan/test_output to avoid huge payloads.
    # The LLM already has them in the conversation context / observations.
    return (
        f"REPLAN FOR {source_file}\n"
        f"- Why the previous plan/tests failed (based on pytest output / guard error):\n"
        f"  - \n"
        f"- What assumption was wrong:\n"
        f"  - \n"
        f"- Updated behaviors to validate:\n"
        f"  - \n"
        f"- Updated test cases to implement:\n"
        f"  - \n"
        f"- Updated mocks/fakes:\n"
        f"  - \n"
        f"- Keep exclusions (MUST): no snapshots, no randomness, no time, no sleep, no network\n"
        f"- Note: previous_plan_length={len(previous_plan)}, test_output_length={len(test_output)}\n"
    )


FORBIDDEN_TEST_PATTERNS = [
    # snapshoty / snapshot libs
    r"\bsnapshot\b",
    r"inline snapshot",
    r"snapshottest",
    r"approvaltests",
    r"\bto_match_snapshot\b",
    r"\bassert_match_snapshot\b",

    # flakiness: czas / sleep
    r"\btime\.sleep\s*\(",
    r"\bdatetime\.now\s*\(",
    r"\bdatetime\.utcnow\s*\(",
    r"\btime\.time\s*\(",
    r"\bperf_counter\s*\(",

    # flakiness: random/uuid bez kontroli
    r"\brandom\.",
    r"\buuid\.uuid4\s*\(",

    # flakiness: sieć
    r"\brequests\.",
    r"\bhttpx\.",
    r"\burllib\.",
    r"\bsocket\.",
]


def write_test_file(test_filename: str, content: str) -> str:
    """
    Write a test file ONLY under tests/.
    Blocks snapshot/flaky patterns. Creates tests/ if missing.
    """
    if os.path.isabs(test_filename) or ".." in test_filename:
        raise ValueError("Invalid test filename")

    lowered = content.lower()
    for pat in FORBIDDEN_TEST_PATTERNS:
        if re.search(pat, lowered):
            raise ValueError(
                f"Refusing to write tests/{test_filename}: forbidden pattern matched: {pat}"
            )

    ensure_tests_dir()
    full_path = os.path.join(TESTS_DIR, test_filename)

    with open(full_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(content)

    return f"Wrote tests/{test_filename} ({len(content)} chars)"


def run_tests() -> str:
    """Run pytest on tests/ directory."""
    ensure_tests_dir()
    p = subprocess.run(
        "pytest tests -q",
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
    )
    return f"EXIT={p.returncode}\n{p.stdout}"


# -----------------------
# Agent
# -----------------------

INSTRUCTIONS = """
You are an AI agent that generates deterministic unit tests based on code diffs.

MANDATORY PHASES (DO NOT SKIP):

1. PLANNING
   - Ensure tests/ exists.
   - For each changed source file:
     a) call get_diff to obtain the diff
     b) call plan_tests(source_file, diff) to get the PLAN TEMPLATE
     c) fill in the template with a concrete plan (in your response text),
        based strictly on the diff (behaviors, cases, mocks, exclusions)
   - Do NOT write any test files before all plans are produced.

2. IMPLEMENTATION
   - For each changed source file:
     a) map source -> test using map_source_to_test
     b) read existing mapped test file from tests/ if present (use read_file)
     c) create or update the mapped test file using write_test_file
   - Follow the plan strictly.

3. EXECUTION
   - Run tests using run_tests.

4. REPLAN & FIX LOOP (MAX 3 ITERATIONS TOTAL)
   - Trigger REPLAN when:
     - tests fail (run_tests EXIT != 0), OR
     - write_test_file is rejected by guards (exception)
   - For each affected source file:
     a) call replan_tests(source_file, previous_plan, test_output) to get the REPLAN TEMPLATE
     b) fill in the template with an UPDATED plan in your response text (REPLAN)
     c) implement updated tests according to the UPDATED plan (write_test_file)
     d) run tests again (run_tests)
   - Never patch tests without updating the plan first.

STRICT RULES:
- ALWAYS use tests/
- ALWAYS use map_source_to_test for filenames
- NEVER write tests outside tests/
- Use pytest
- Base tests ONLY on get_diff + read_file
- Do NOT modify production code

ANTI-FLAKY / NO-SNAPSHOT GUARDED BEHAVIOR (MUST FOLLOW):
- DO NOT create snapshot tests (no snapshot files, no snapshot assertions, no inline snapshots).
- DO NOT depend on wall-clock time (no datetime.now(), time.time()).
- DO NOT use random values (no random.*, uuid.uuid4()) unless explicitly seeded and deterministic.
- DO NOT use sleep/retries/timeouts to “make it pass” (no time.sleep()).
- DO NOT call external network services (no requests/httpx/urllib sockets).
- Prefer pure unit tests with mocks/fakes over integration tests.
- Avoid order-dependent tests; tests must be runnable in isolation.

OUTPUT REQUIREMENTS:
- Include a test plan per source file (filled template)
- Include mapping: source file -> tests/<mapped test file>
- List test files created/modified
- Final pytest result (exit code + output)
"""


async def main():
    base_sha = os.environ.get("INPUT_BASE_SHA")
    head_sha = os.environ.get("INPUT_HEAD_SHA")
    if not base_sha or not head_sha:
        raise SystemExit("Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")

    agent = GitHubCopilotAgent(
        default_options={
            "model": os.environ.get("GITHUB_COPILOT_MODEL", "gpt-5"),
            "instructions": INSTRUCTIONS,
        },
        tools=[
            ensure_tests_dir,
            list_changed_files,
            get_diff,
            plan_tests,
            replan_tests,
            read_file,
            map_source_to_test,
            write_test_file,
            run_tests,
        ],
    )

    async with agent:
        result = await agent.run(
            f"""
Compare commits base={base_sha} and head={head_sha} and generate/update unit tests.

Process:
- Ensure tests/ exists
- Identify changed Python files
- PLANNING per file: get_diff → plan_tests(template) → fill template (plan)
- IMPLEMENTATION: write/update mapped test files in tests/
- EXECUTION: run pytest tests
- REPLAN: if tests fail or guard rejects writes: replan_tests(template) → fill template (updated plan) → adjust tests
- FIX LOOP: up to 3 iterations total

Return the required output.
"""
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())


FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (gh)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
 && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# Install Copilot extension for gh
RUN gh extension install github/gh-copilot || gh extension upgrade github/gh-copilot

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt \
 && pip install --no-cache-dir --pre agent-framework agent-framework-github-copilot pytest

# Sanity check during build
RUN which git && git --version \
 && which gh && gh --version \
 && gh copilot --version

COPY app.py /app/app.py

ENTRYPOINT ["python", "/app/app.py"]



# --- Microsoft Agent Framework (CORE) ---
agent-framework==1.0.0b260130
agent-framework-github-copilot==1.0.0b260130

# --- Testing ---
pytest>=7.4,<9.0

# --- Typy / utils (bezpieczne, lekkie) ---
typing-extensions>=4.8
pydantic>=2.6,<3.0

# --- Opcjonalnie (lepsze logi/debug) ---
rich>=13.7


agent-framework --pre
agent-framework-github-copilot --pre
pytest
typing-extensions
pydantic


https://devblogs.microsoft.com/semantic-kernel/build-ai-agents-with-github-copilot-sdk-and-microsoft-agent-framework/?utm_source=chatgpt.com