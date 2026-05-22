---
name: add-output
description: Scaffold a new output plugin in lore/outputs/ following the OutputPlugin pattern. Use when adding a new documentation target (e.g. Confluence, Notion, GitHub Wiki, Slack).
---

When the user asks to add a new output destination, follow these steps exactly.

## Steps

1. **Create `lore/outputs/<name>.py`**
   - Subclass `OutputPlugin` from `lore/outputs/base.py`
   - Implement `run(context: PipelineContext) -> PipelineContext`
   - Set `context.output_url` to the URL of the created/updated page before returning

2. **Handle HTTP errors correctly**
   - **CRITICAL**: Many documentation APIs (including Lark) return HTTP 200 even on errors
   - Always check the response body, not just `raise_for_status()`
   - Safe pattern:
     ```python
     resp.raise_for_status()
     data = resp.json()
     if data.get("code", 0) != 0:
         raise RuntimeError(f"API error {data['code']}: {data.get('msg')}")
     ```
   - If the target API uses standard HTTP status codes, `raise_for_status()` alone is fine

3. **Add config fields** (if new credentials are needed)
   - Add fields to the config dataclass in `lore/config.py`
   - Add `${ENV_VAR}` references to `lore.yaml` and `.env.example`
   - `load_config()` raises on unresolved `${...}` vars — document required env vars clearly

4. **Wire into `cli.py`**
   - Instantiate the output conditionally (typically gated on config presence)
   - Follow the pattern of existing outputs in `analyze` or add a dedicated subcommand

5. **Create `tests/outputs/test_<name>.py`**
   - Mock HTTP clients with `unittest.mock` or `respx` (httpx)
   - Test: successful publish, API error in body (HTTP 200 with non-zero code), network error
   - Follow the pattern in `tests/outputs/` for existing output tests

6. **Run tests**
   ```bash
   python -m pytest tests/outputs/test_<name>.py -v
   ```

## Checklist before finishing
- [ ] `context.output_url` set before returning from `run()`
- [ ] Response body checked for API-level errors (not just `raise_for_status()`)
- [ ] New env vars documented in `.env.example`
- [ ] Config fields added to `lore/config.py` and `lore.yaml`
- [ ] `python -m pytest tests/outputs/test_<name>.py -v` passes
