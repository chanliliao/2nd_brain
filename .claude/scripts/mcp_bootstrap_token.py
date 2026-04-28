import os
import sys
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("project_secrets", Path(__file__).parent / "secrets.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
secure_write_token = _mod.secure_write_token
secure_read_token = _mod.secure_read_token

existing = secure_read_token("mcp_bearer")
if isinstance(existing, dict) and "token" in existing:
    print("WARNING: A bearer token for 'mcp_bearer' already exists.")
    answer = input("Type 'yes' to overwrite: ")
    if answer != "yes":
        print("Aborted.")
        sys.exit(0)

token = os.urandom(32).hex()
secure_write_token("mcp_bearer", {"token": token})

print("Bearer token generated and stored in .claude/data/secrets/mcp_bearer_token.json")
print("Token (copy now — will not be shown again):")
print()
print(token)
print()
print("Add to each client's ~/.claude/mcp.json:")
print(f'  "headers": {{"Authorization": "Bearer {token}"}}')
