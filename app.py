import sys
import os
import subprocess


name = sys.argv[1] if len(sys.argv) > 1 else "World"
print(f"Hello, {name}! 👋 From Docker Action")


WORKSPACE = "/github/workspace"

print("📂 Files in repository:\n")

for root, dirs, files in os.walk(WORKSPACE):
    for name in files:
        path = os.path.join(root, name)
        print(path.replace(WORKSPACE + "/", ""))


base_sha = os.environ.get("INPUT_BASE_SHA")
head_sha = os.environ.get("INPUT_HEAD_SHA")

if not base_sha or not head_sha:
    print("❌ Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
    sys.exit(1)

print(f"🔎 Comparing commits:")
print(f"  base: {base_sha}")
print(f"  head: {head_sha}\n")

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

changed_files = [
    f for f in result.stdout.splitlines()
    if f.endswith(".py")
]

if not changed_files:
    print("ℹ️ No Python files changed.")
else:
    print("✅ Changed Python files:")
    for f in changed_files:
        print(f" - {f}")