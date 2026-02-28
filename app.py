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


def summarize_changed_file(file, base_sha, head_sha) -> str:
            diff_result = subprocess.run(
                ["git", "diff", base_sha, head_sha, "--", file],
                cwd=WORKSPACE,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if diff_result.returncode != 0:
                print(f"[WARN] git diff failed for {file}:\n{diff_result.stderr}")
                return

            diff = diff_result.stdout.strip()
            if not diff:
                return

            return diff[:12000]


def summarize_changed_files(changed_files: List[str], base_sha: str, head_sha: str) -> dict:
        changed_files_summaries = {}
        for f in changed_files:
            diff = summarize_changed_file(f, base_sha, head_sha)
            if not diff:
                print(f"Brak zmian do podsumowania w {f}.")
                continue
            changed_files_summaries[f] = diff

        return changed_files_summaries



async def summarize_changes_with_copilot_async(changed_files_summaries: dict) -> None:
    if not changed_files_summaries:
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
        for f, diff in changed_files_summaries.items():
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

    changed_files_summaries = summarize_changed_files(changed_py, base_sha, head_sha)

    if not changed_files_summaries:
        print("\nNo changes to summarize with Copilot.")
        return

    asyncio.run(summarize_changes_with_copilot_async(changed_files_summaries))


if __name__ == "__main__":
    main()
