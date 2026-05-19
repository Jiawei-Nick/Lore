# Migration: Lark Wiki → Lark Doc

## What Changed

The project has been updated to use **Lark Docs** instead of **Lark Wiki** because Wiki requires special space creation permissions.

## Breaking Changes

### Configuration Files

**Old (`lore.yaml`):**
```yaml
lark:
  wiki_space_id: ${LARK_WIKI_SPACE_ID}
  parent_node_token: ${LARK_PARENT_NODE_TOKEN}
```

**New (`lore.yaml`):**
```yaml
lark:
  folder_token: ${LARK_FOLDER_TOKEN}
  parent_doc_id: ${LARK_PARENT_DOC_ID}
```

### Environment Variables

| Old Variable | New Variable | How to Get |
|-------------|--------------|------------|
| `LARK_WIKI_SPACE_ID` | `LARK_FOLDER_TOKEN` | From folder URL: `https://xxx.feishu.cn/drive/folder/[TOKEN]` |
| `LARK_PARENT_NODE_TOKEN` | `LARK_PARENT_DOC_ID` | From doc URL: `https://xxx.feishu.cn/docx/[DOC_ID]` |

### Code Changes

- **Module**: `lore.outputs.lark.LarkWikiOutput` → `lore.outputs.lark_doc.LarkDocOutput`
- **API Endpoints**: Changed from Wiki API to Docx API
- **Content Format**: Changed from markdown to Lark Doc block structure

## Migration Steps

### For Existing Users

1. **Update your `.env` file**:
   ```bash
   # Remove old variables
   # LARK_WIKI_SPACE_ID=...
   # LARK_PARENT_NODE_TOKEN=...
   
   # Add new variables
   LARK_FOLDER_TOKEN=your-folder-token
   LARK_PARENT_DOC_ID=your-parent-doc-id
   ```

2. **Get the new tokens**:
   - Create a folder in Lark Drive
   - Get `LARK_FOLDER_TOKEN` from folder URL
   - Create a doc for ERD in that folder
   - Get `LARK_PARENT_DOC_ID` from doc URL

3. **Update app permissions**:
   - Go to your Lark app settings
   - Remove Wiki permissions (optional)
   - Add Doc permissions: `docx:document`, `drive:drive`
   - Republish your app version

4. **Test the migration**:
   ```bash
   lore analyze --branch your-test-branch
   ```

### For New Users

Just follow the setup guide in `docs/LARK_SETUP.md` - no migration needed!

## Benefits of Lark Docs

✅ **No special permissions required** - Any user can create folders and docs
✅ **Better organization** - Docs appear in your normal Drive folder structure
✅ **Easier sharing** - Standard Lark Drive sharing model
✅ **Rich formatting** - Better support for tables and structured content

## Rollback (if needed)

If you need to rollback to Wiki mode:

```bash
git revert HEAD
pip install -e .
# Restore old .env variables
```

Then contact your admin to create a Wiki space.
