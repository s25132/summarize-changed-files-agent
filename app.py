import os
import subprocess
import sys

WORKSPACE = "/github/workspace"

base_sha = os.environ.get("INPUT_BASE_SHA")  # e.g. HEAD~1
head_sha = os.environ.get("INPUT_HEAD_SHA")  # e.g. HEAD

if not base_sha or not head_sha:
    print("❌ Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
    sys.exit(1)

# allow git to work on mounted repo in Docker
subprocess.run(
    ["git", "config", "--global", "--add", "safe.directory", WORKSPACE],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

result = subprocess.run(
    ["git", "diff", "--name-only", base_sha, head_sha],
    cwd=WORKSPACE,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

if result.returncode != 0:
    print("❌ git diff failed")
    print(result.stdout)
    sys.exit(result.returncode)

changed_py = [f for f in result.stdout.splitlines() if f.endswith(".py")]

print(f"🔎 Comparing commits:\n  base: {base_sha}\n  head: {head_sha}\n")

if changed_py:
    print("✅ Changed Python files:")
    for f in changed_py:
        print(f" - {f}")
else:
    print("ℹ️ No Python files changed.")
