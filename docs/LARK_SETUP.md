# Lark Doc Setup Guide

This guide explains how to set up Lark (Feishu) integration for the Lore project using **Lark Docs** instead of Lark Wiki.

## Why Lark Docs?

Lark Docs provides more flexibility and doesn't require special Wiki space permissions. You can create docs in any shared folder in your Lark Drive.

## Step-by-Step Setup

### 1. Create a Lark App

1. Visit:
   - **China**: https://open.feishu.cn/app
   - **International**: https://open.larksuite.com/app

2. Log in with your Lark account

3. Click **"Create App"** (创建应用) → Choose **"Custom App"** (自建应用)

4. Fill in app details:
   - Name: `Lore DB Sync` (or any name you prefer)
   - Description: `Database schema change tracking`

5. After creation, you'll see:
   - **App ID** (`cli_xxxxxxxxxx`) - Save this as `LARK_APP_ID`
   - **App Secret** - Save this as `LARK_APP_SECRET`

### 2. Configure App Permissions

1. In your app settings, go to **"Permissions & Scopes"** (权限管理)

2. Add these permissions:
   - **Docs (文档)**:
     - `docx:document` - Create and edit docs
     - `docx:document:readonly` - Read docs
   - **Drive (云空间)**:
     - `drive:drive` - Access drive folders

3. Click **"Save"** and **"Publish Version"**

4. **Important**: Install the app to your workspace:
   - Go to **"Version Management & Release"** (版本管理与发布)
   - Click **"Create Version"** → **"Apply for Release"**
   - Or use the app in "Development Mode" for testing

### 3. Get Folder Token

1. Open Lark Drive in your browser

2. Create or navigate to a folder where you want reports to be created

3. The URL will look like:
   ```
   https://xxx.feishu.cn/drive/folder/[FOLDER_TOKEN]
   ```

4. Copy the `FOLDER_TOKEN` part → Save as `LARK_FOLDER_TOKEN`

### 4. Get Parent Doc ID

1. Create a new Lark Doc in your folder (this will hold the ERD)

2. Name it something like "DB Schema - ERD"

3. The URL will look like:
   ```
   https://xxx.feishu.cn/docx/[DOC_ID]
   ```

4. Copy the `DOC_ID` part → Save as `LARK_PARENT_DOC_ID`

### 5. Configure Environment Variables

Edit your `.env` file:

```bash
# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

# Lark App Credentials
LARK_APP_ID=cli_xxxxxxxxxx
LARK_APP_SECRET=your-app-secret-here

# Lark Doc Configuration
LARK_FOLDER_TOKEN=your-folder-token-here
LARK_PARENT_DOC_ID=your-parent-doc-id-here
```

### 6. Test Your Setup

```bash
# Test with a PostgreSQL database (optional)
lore init --db postgresql://user:pass@localhost/testdb

# Test analysis on a branch
lore analyze --branch feature/test-branch
```

## Troubleshooting

### Error: "permission denied" or "app not installed"

**Solution**: Make sure your app is installed to the workspace:
- Go to app settings → "Version Management" → Create and release a version
- Or enable "Development Mode" for testing

### Error: "folder not found" or "403 Forbidden"

**Solution**: Share the folder with your app:
1. Right-click the folder in Lark Drive
2. Click "Share" → "Add members"
3. Add your app (search by app name)
4. Give it "Edit" permissions

### Error: "document not found"

**Solution**: Make sure the parent doc exists and is shared with your app:
1. Open the parent doc
2. Click "Share" → Add your app with "Edit" permissions

## Understanding the Output

After running `lore analyze`, the tool will:

1. **Create a new doc** in your specified folder with title format:
   ```
   2026-05-18 | feature/add-phone | MEDIUM
   ```

2. **Update the parent doc** with the latest ERD (Entity Relationship Diagram)

3. Your folder structure will look like:
   ```
   📁 DB Schema Reports/
      📄 ERD (Parent Doc) - Updated each run
      📄 2026-05-18 | feature/add-phone | MEDIUM
      📄 2026-05-17 | feature/user-audit | HIGH
      📄 2026-05-15 | feature/add-index | LOW
   ```

## API Reference

- **Lark Open API Docs**: https://open.larksuite.com/document
- **Lark Docs API**: https://open.larksuite.com/document/server-docs/docs/docs/docx-v1/overview
- **Authentication**: https://open.larksuite.com/document/server-docs/authentication-management/access-token/tenant_access_token_internal
