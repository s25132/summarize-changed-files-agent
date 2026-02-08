import os
import subprocess
import sys
import asyncio
from typing import List, Optional
from copilot import CopilotClient
import traceback



WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
if not WORKSPACE:
    print("GITHUB_WORKSPACE not set")
    sys.exit(1)


def get_changed_python_files(base_sha: str, head_sha: str) -> List[str]:
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", WORKSPACE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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

    return [f for f in result.stdout.splitlines() if f.endswith(".py")]


def get_token() -> Optional[str]:
    return os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")


async def summarize_changes_with_copilot_async(changed_files: List[str], base_sha: str, head_sha: str) -> None:
    if not changed_files:
        print("No Python files changed -> skipping Copilot.")
        return

    gh_token = get_token()
    if not gh_token:
        print("No token env found (COPILOT_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN).")
        return

    # force standard env vars for CLI/SDK
    os.environ["GH_TOKEN"] = gh_token
    os.environ["COPILOT_GITHUB_TOKEN"] = gh_token

    print("\nUruchamianie Copilot SDK...")
    client = CopilotClient()

    try:
        print("Startowanie klienta Copilot...")
        await asyncio.wait_for(client.start(), timeout=30)
        print("Klient uruchomiony.")

        print("Tworzenie sesji z modelem GPT-4.1...")
        session = await asyncio.wait_for(
            client.create_session({"streaming": False, "model": "gpt-4.1"}),
            timeout=30,
        )
        print("Sesja utworzona.")

        async def ask(prompt: str, t: int = 45):
            return await asyncio.wait_for(session.send_and_wait({"prompt": prompt}), timeout=t)

        # 2) Summarize changed files
        for f in changed_files:
            diff_result = subprocess.run(
                ["git", "diff", base_sha, head_sha, "--", f],
                cwd=WORKSPACE,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if diff_result.returncode != 0:
                print(f"[WARN] git diff failed for {f}:\n{diff_result.stderr}")
                continue

            diff = diff_result.stdout.strip()
            if not diff:
                print(f"Brak zmian do podsumowania w {f}.")
                continue

            diff = diff[:12000]
            prompt = f"Summarize the code changes in {f} in 2-4 bullet points:\n{diff}"

            print(f"\nWysyłam zapytanie dla {f} (diff length: {len(diff)})...")
            resp = await ask(prompt, 60)
            print(f"\nPodsumowanie zmian w {f}:\n{resp.data.content}")

    except Exception as e:
        print("\nBłąd podczas wywoływania Copilot SDK (repr):", repr(e))
        traceback.print_exc()
    finally:
        try:
            await client.stop()
        except Exception:
            pass


def main() -> None:

    base_sha = os.environ.get("INPUT_BASE_SHA")
    head_sha = os.environ.get("INPUT_HEAD_SHA")
    if not base_sha or not head_sha:
        print("Missing INPUT_BASE_SHA or INPUT_HEAD_SHA")
        sys.exit(1)

    changed_py = get_changed_python_files(base_sha, head_sha)

    print(f"\nComparing commits:\n  base: {base_sha}\n  head: {head_sha}\n")

    if changed_py:
        print("Changed Python files:")
        for f in changed_py:
            print(f" - {f}")
    else:
        print("No Python files changed.")

    asyncio.run(summarize_changes_with_copilot_async(changed_py, base_sha, head_sha))


if __name__ == "__main__":
    main()
