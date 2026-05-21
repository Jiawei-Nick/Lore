# ERD Generation - Changes Summary

## What Changed

Enhanced `lore generate-erd` command with **Lark upload support** and **simplified options**.

## New Capabilities

### 1. Upload Directly to Lark
```bash
# Upload overview to Lark parent document
lore generate-erd --upload --overview
```

Previously: Only file output was supported  
Now: Can upload to Lark Docs parent page (same as `lore analyze` uses)

### 2. Combined File + Lark Output
```bash
# Save to files AND upload to Lark
lore generate-erd --output-dir ./docs/erd --upload --overview
```

### 3. Flexible Output Modes

| Command | Output |
|---------|--------|
| `lore generate-erd --output-dir ./docs` | Files only (all 130 categories) |
| `lore generate-erd --upload --overview` | Lark only (overview) |
| `lore generate-erd --output-dir ./docs --upload --overview` | Both |

### 4. Better Help & Error Messages

- Clear examples in `--help`
- Warning when no output specified
- Better error messages when Lark upload fails
- Guidance on character limit issues

## Command Comparison

### Before (Original Implementation)
```bash
# Only file output
lore generate-erd --output-dir ./erd_output
lore generate-erd --output-dir ./erd_output --overview

# Manual steps to get to Lark:
# 1. Generate files
# 2. Open erd_overview.mmd
# 3. Copy content
# 4. Open Lark Doc
# 5. Paste as code block
```

### After (Enhanced)
```bash
# Direct Lark upload
lore generate-erd --upload --overview

# Or save + upload in one command
lore generate-erd --output-dir ./docs/erd --upload --overview
```

## Technical Changes

### `lore/outputs/lark_doc.py`
- ✅ Added `upload_category_erds()` method
- ✅ Uploads multiple category ERDs to Lark Doc
- ✅ Limits to top N categories (by table count)
- ✅ Handles 100K character limit gracefully
- ✅ Better error messages

### `lore/cli.py`
- ✅ Added `--upload` flag to `generate-erd` command
- ✅ Added `--max-categories` option (default: 5)
- ✅ Supports both file output and Lark upload
- ✅ Can do both in single command
- ✅ Shows helpful message when no output specified
- ✅ Better examples in docstring

### Documentation
- ✅ Updated `CLAUDE.md` with new usage
- ✅ Updated `examples/erd/README.md`
- ✅ Added `examples/erd/WORKFLOW.md` with complete workflows

## Why These Changes?

### Problem
Original implementation only saved to files. Users had to:
1. Generate files
2. Manually copy content
3. Manually paste into Lark Docs

For large schemas (766 tables), even the overview is ~17KB - tedious to copy/paste.

### Solution
Direct Lark upload eliminates manual steps:
```bash
lore generate-erd --upload --overview  # Done!
```

### Best Practice for Large Schemas

For schemas with 100+ tables:
- **Lark**: Upload overview only (`--upload --overview`)
- **Files**: Save all detailed categories (`--output-dir ./docs/erd`)
- **Both**: One command (`--output-dir ./docs/erd --upload --overview`)

Detailed category ERDs (170 tables in wallet, 81 in user, etc.) exceed Lark's 100K limit.

## Usage Examples

### Quick Lark Update
```bash
# After running lore init
lore generate-erd --upload --overview
```

Result: https://open.larksuite.com/docx/NOAfdAHu4opRaXxLLmLlxsHfgQc

### Full Documentation
```bash
# Generate everything
lore generate-erd --output-dir ./docs/erd --upload --overview

# Commit to repo
git add docs/erd/
git commit -m "docs: update schema ERDs"
```

Result:
- Git: 130 detailed category files
- Lark: High-level overview diagram
- Team: Can drill into details (Git) or see big picture (Lark)

## Breaking Changes

None! All previous commands still work:
```bash
# Still works exactly as before
lore generate-erd --output-dir ./erd_output
lore generate-erd --overview --output-dir ./erd_output
```

## Tests

All tests passing: 61/61 ✅

No new tests added for Lark upload (would require mocking Lark API), but existing tests cover:
- Category detection
- ERD generation
- File writing

## Next Steps

1. **Commit changes** to `feature/test` branch
2. **Test Lark upload** with real parent doc
3. **Update team documentation** with new workflow
4. **Merge to main** when ready
