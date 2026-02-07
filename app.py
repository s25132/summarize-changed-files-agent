import os
import subprocess
import sys
from typing import List

WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
if not WORKSPACE:
    print("GITHUB_WORKSPACE not set")
    sys.exit(1)

def get_changed_python_files(base_sha: str, head_sha: str) -> List[str]:
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
        print("git diff failed")
        print(result.stdout)
        sys.exit(result.returncode)

    return [
        f for f in result.stdout.splitlines()
        if f.endswith(".py")
    ]


def main() -> None:
    base_sha = os.environ.get("INPUT_BASE_SHA")
    head_sha = os.environ.get("INPUT_HEAD_SHA")

    if not base_sha or not head_sha:
        print("Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
        sys.exit(1)
    
    changed_py = get_changed_python_files(base_sha, head_sha)

    print(f"Comparing commits:\n  base: {base_sha}\n  head: {head_sha}\n")

    if changed_py:
        print("Changed Python files:")
        for f in changed_py:
            print(f" - {f}")
    else:
        print("No Python files changed.")


if __name__ == "__main__":
    main()
