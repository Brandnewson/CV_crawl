# Automation Lessons

This file captures recurring pipeline failures and deterministic fix patterns.

## L001 - Bash EOF From Inline Python

- Symptom:
  - `/usr/bin/bash: -c: line N: unexpected EOF while looking for matching '"'`
- Root cause:
  - Multiline Python passed via `python -c "..."` or heredoc snippets with nested quotes.
- Rule:
  - Do not run multiline orchestration logic inline.
  - Use dedicated script files under `tools/` and pass arguments only.

### Safe command pattern

```bash
uv run --project "C:/Code/CV_crawl" python "C:/Code/CV_crawl/tools/<script>.py" --arg value
```

## L002 - JSON Decode Failure After Subprocess

- Symptom:
  - `json.loads(...)` fails on subprocess stdout.
- Root cause:
  - Non-zero exit code, empty stdout, or mixed logs + JSON.
- Rule:
  - Validate `returncode == 0` before parsing stdout.
  - Use scripts that print a single JSON object on success.

## L003 - Ambiguous CLI Flags

- Symptom:
  - `--template` matches multiple flags.
- Root cause:
  - Argparse abbreviation matching enabled.
- Rule:
  - Use full flag names in docs and commands.
  - Set `ArgumentParser(..., allow_abbrev=False)` on high-traffic scripts.

## L004 - Keyword Target Drift After Manual Bullet Edits

- Symptom:
  - Validator fails `keyword_target_verbatim_missing` after user swaps a bullet topic.
- Root cause:
  - Stale `keyword_target` in slot plan no longer matches edited bullet text.
- Rule:
  - Reconcile slot-plan targets against selections before deterministic validation.
  - If no clean target remains, clear it; if a clear JD phrase exists, replace it.

## L005 - 1-Page Wrap Despite Passing Length Gate

- Symptom:
  - Validator passes but rendered CV spills to page 2 in 1-page mode.
- Root cause:
  - Visual wrap threshold is tighter than generic text-length ceiling.
- Rule:
  - Apply profile-specific bullet length limits.
  - On layout overflow, run one deterministic compact pass and re-render before asking user.

## L006 - Discovery LLM 401 / Non-Fatal Fallback Confusion

- Symptom:
  - Discovery completes but user cannot tell whether LLM enrichment/scoring was used.
- Root cause:
  - Fallback path was implicit in logs.
- Rule:
  - Emit explicit fallback summary with `llm_used`, `fallback_used`, and `error_types`.
  - Keep deterministic fallback behavior unchanged.

## L00X - Wrap Gate Must Run Before User Approval Loop

- Symptom:
  - User approves CV in Step 7 but the rendered DOCX/PDF overflows to 2 pages due to bullet wrapping.
- Root cause:
  - Step 6.5 (wrap_optimizer.py) was skipped and run post-approval instead of pre-approval.
- Rule:
  - Always run `tools/wrap_optimizer.py` after Step 6 (render_cv.py) and BEFORE showing the preview in Step 7.
  - Only present the approval loop once the wrap gate confirms 0 wrapped bullets.
  - If the slot plan is regenerated mid-run (e.g. after user feedback), re-run coverage_plan.py and re-apply any keyword_target patches before re-validating.
