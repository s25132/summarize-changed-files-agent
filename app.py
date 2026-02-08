import os
import subprocess
import sys
import asyncio
from typing import List
from copilot import CopilotClient
import logging
logging.basicConfig(level=logging.DEBUG)

os.environ["COPILOT_LOG_LEVEL"] = "debug"
os.environ["COPILOT_SDK_LOG_LEVEL"] = "debug"
os.environ["GH_LOG_LEVEL"] = "debug"
os.environ["DEBUG"] = "*copilot*"

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

    # Podsumowanie zmian przez Copilot SDK
    summarize_changes_with_copilot(changed_py, base_sha, head_sha)


async def summarize_changes_with_copilot_async(changed_files, base_sha, head_sha):
    if not changed_files:
        return
    if CopilotClient is None:
        print("\nCopilot SDK nie jest zainstalowany. Pomijam podsumowania zmian.")
        return
    
    gh_token = os.environ.get("COPILOT_GITHUB_TOKEN")
    if not gh_token:
        print("\nBrak COPILOT_GITHUB_TOKEN. Pomijam podsumowania zmian przez Copilot.")
        return
    
    
    print("GH_TOKEN set:", bool(os.getenv("GH_TOKEN")))
    print("COPILOT_GITHUB_TOKEN set:", bool(os.getenv("COPILOT_GITHUB_TOKEN")))
    
    print("\nUruchamianie Copilot SDK...")
    client = CopilotClient()
    
    try:
        print("Startowanie klienta Copilot...")
        await asyncio.wait_for(client.start(), timeout=30)
        print("Klient uruchomiony.")
        
        print("Tworzenie sesji...")
        session = await asyncio.wait_for(
            client.create_session({
                "model": "gpt-4.1",
                "github_token": gh_token
            }),
            timeout=30
        )
        print("Sesja utworzona.")
        
        for f in changed_files:
            diff_result = subprocess.run(
                ["git", "diff", base_sha, head_sha, "--", f],
                cwd=WORKSPACE,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            diff = diff_result.stdout
            if diff:
                # Limit diff size to prevent timeouts
                max_diff_length = 500
                if len(diff) > max_diff_length:
                    diff = diff[:max_diff_length] + "\n... (diff truncated)"
                
                prompt = f"Briefly summarize changes in {f} (max 2 sentences):\n{diff}"
                try:
                    print(f"\nWysyłam zapytanie dla {f} (diff length: {len(diff)})...")
                    response = await asyncio.wait_for(
                        session.send_and_wait({"prompt": prompt}),
                        timeout=90
                    )
                    summary = response.data.content
                    print(f"\nPodsumowanie zmian w {f}:\n{summary}")
                except asyncio.TimeoutError:
                    print(f"\nTimeout (90s) - pomijam podsumowanie dla {f}.")
                except Exception as e:
                    print(f"\nBłąd dla {f}: {e}")
            else:
                print(f"\nBrak zmian do podsumowania w {f}.")
    except asyncio.TimeoutError as e:
        print(f"\nTimeout podczas inicjalizacji Copilot SDK: {e}")
    except Exception as e:
        print(f"\nBłąd podczas wywoływania Copilot SDK: {e}")
    finally:
        try:
            await client.stop()
        except:
            pass

def summarize_changes_with_copilot(changed_files, base_sha, head_sha):
    asyncio.run(summarize_changes_with_copilot_async(changed_files, base_sha, head_sha))

if __name__ == "__main__":
    main()
