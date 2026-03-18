# Automation Lessons

This file captures recurring automation failures and the exact fix patterns the
orchestrator should apply.

## L001 - Bash EOF From Multiline `python -c`

- Symptom:
  - `/usr/bin/bash: -c: line N: unexpected EOF while looking for matching '"'`
- Root cause:
  - Multiline code passed via `python -c "..."` with unescaped quotes/newlines.
- Rule:
  - Do not use multiline `python -c` in bash.
  - Use heredoc form for multiline Python.

### Safe patterns

#### Bash

```bash
uv run --project "C:/Code/CV_crawl" python - <<'PY'
import json
print(json.dumps({"ok": True}))
PY
```

#### PowerShell

```powershell
@'
import json
print(json.dumps({"ok": True}))
'@ | uv run --project "C:/Code/CV_crawl" python -
```

## L002 - JSON Decode Failures After Subprocess

- Symptom:
  - `json.loads(...)` fails after command execution.
- Root causes:
  - Command returned non-zero, empty stdout, or encoding mismatch.
- Rule:
  - Always check `returncode` first.
  - Parse JSON only when stdout is non-empty and returncode is 0.
  - Prefer ASCII-safe JSON for CLI output where possible.
