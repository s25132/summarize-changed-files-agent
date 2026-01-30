import sys
import os
import subprocess


name = sys.argv[1] if len(sys.argv) > 1 else "World"
print(f"Hello, {name}! 👋 From Docker Action")


WORKSPACE = "/github/workspace"

# 🔑 IMPORTANT: allow git to work inside Docker-mounted workspace
subprocess.run(
    ["git", "config", "--global", "--add", "safe.directory", WORKSPACE],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

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

# fetch refs from origin so commits are resolvable
fetch = subprocess.run(
    ["git", "fetch", "--no-tags", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*"],
    cwd=WORKSPACE,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

if fetch.returncode != 0:
    print("❌ git fetch failed")
    print(fetch.stdout)
    sys.exit(fetch.returncode)

# if base_sha still doesn't exist (e.g. force-push), fall back to HEAD~1
check_base = subprocess.run(
    ["git", "cat-file", "-e", f"{base_sha}^{{commit}}"],
    cwd=WORKSPACE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

if check_base.returncode != 0:
    print(f"⚠️ base SHA not found locally ({base_sha}), falling back to HEAD~1")
    base_sha = "HEAD~1"

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
