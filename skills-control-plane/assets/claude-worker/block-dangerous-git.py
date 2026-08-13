#!/usr/bin/env python3
import json
import re
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    print("BLOCKED: malformed hook input", file=sys.stderr)
    raise SystemExit(2)

command = str(data.get("tool_input", {}).get("command", ""))
patterns = [
    r"(^|[;&|\n]\s*)git\s+push(?:\s|$)",
    r"(^|[;&|\n]\s*)git\s+reset\s+--hard(?:\s|$)",
    r"(^|[;&|\n]\s*)git\s+clean\s+[^;&|\n]*-[^;&|\n]*f",
    r"(^|[;&|\n]\s*)git\s+branch\s+-D(?:\s|$)",
    r"(^|[;&|\n]\s*)git\s+(?:checkout|restore)\s+(?:--\s+)?\.(?:\s|$)",
    r"(^|[;&|\n]\s*)(?:rm|sudo\s+rm)\s+[^;&|\n]*-[^;&|\n]*r[^;&|\n]*f",
]
for pattern in patterns:
    if re.search(pattern, command):
        print(
            f"BLOCKED: command matches governed destructive/push policy: {command}",
            file=sys.stderr,
        )
        raise SystemExit(2)
raise SystemExit(0)
