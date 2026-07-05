"""Quick verification of webhook implementation."""
import ast
import sys

files_to_check = [
    "app/api/v1/webhooks.py",
    "backend/scripts/imap_idle_listener.py",
]

print("Checking Python syntax...")
for file in files_to_check:
    try:
        with open(file) as f:
            ast.parse(f.read())
        print(f"OK: {file}")
    except SyntaxError as e:
        print(f"ERROR in {file}: {e}")
        sys.exit(1)

print("\nAll files have valid syntax!")
