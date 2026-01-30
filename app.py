import sys
import os


name = sys.argv[1] if len(sys.argv) > 1 else "World"
print(f"Hello, {name}! 👋 From Docker Action")


WORKSPACE = "/github/workspace"

print("📂 Files in repository:\n")

for root, dirs, files in os.walk(WORKSPACE):
    for name in files:
        path = os.path.join(root, name)
        print(path.replace(WORKSPACE + "/", ""))