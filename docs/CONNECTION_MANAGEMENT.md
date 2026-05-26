# Database Connection Management

## Overview

Lore now supports saving and managing database connection profiles, making it easy to switch between different databases without typing connection strings repeatedly.

## Features

✅ **Save connections** with memorable names  
✅ **Interactive menu** for selecting connections  
✅ **Password masking** in all CLI output  
✅ **CRUD operations** (add, list, edit, remove)  
✅ **Global storage** in `~/.lore/connections.yaml`

## Quick Start

### 1. Add a connection

```bash
# Add with description
lore connections add prod-replica \
  --db "postgresql://user:pass@prod.example.com/mydb" \
  --desc "Production read replica"

# Add without description
lore connections add dev-db \
  --db "mysql://root:pass@localhost:3306/dev"
```

### 2. List saved connections

```bash
lore connections list
```

Output:
```
Saved connections (2):

  • prod-replica
    postgresql://user:***@prod.example.com/mydb - Production read replica

  • dev-db
    mysql://root:***@localhost:3306/dev
```

### 3. Use a saved connection

```bash
# Direct usage by name
lore init --use prod-replica

# Interactive menu
lore init
# > Select a database connection:
# > 
# >   1. prod-replica (postgresql://user:***@prod.example.com/mydb) - Production read replica
# >   2. dev-db (mysql://root:***@localhost:3306/dev)
# > 
# > Enter number: 1
```

### 4. Save connection while running init

```bash
lore init --db "postgresql://user:pass@staging.example.com/db" --save-as staging
```

## Managing Connections

### Edit a connection

```bash
# Update description
lore connections edit prod-replica --desc "Updated description"

# Update URL
lore connections edit prod-replica --db "postgresql://newuser:newpass@host/db"

# Update both
lore connections edit prod-replica \
  --db "postgresql://user:pass@host/db" \
  --desc "New description"
```

### Remove a connection

```bash
# With confirmation prompt
lore connections remove staging

# Skip confirmation
lore connections remove staging --yes
```

## Storage Location

Connections are stored in:
```
~/.lore/connections.yaml
```

Example file structure:
```yaml
connections:
  prod-replica:
    description: Production read replica
    url: postgresql://user:password@prod.example.com/mydb
  dev-db:
    description: Local development database
    url: mysql://root:password@localhost:3306/dev
```

## Security Notes

- **Passwords are masked** in all CLI output (shown as `***`)
- **Passwords are NOT encrypted** in `connections.yaml` (stored in plaintext)
- Consider using environment variables or SSH tunnels for production credentials
- The connections file is readable only by your user account

## Command Reference

### `lore init`

Enhanced with connection management:

```bash
# Use saved connection
lore init --use <name>

# Save new connection
lore init --db <url> --save-as <name>

# Interactive menu (no args)
lore init
```

### `lore connections add`

Add a new connection profile:

```bash
lore connections add <name> --db <url> [--desc <description>]
```

### `lore connections list`

List all saved connections:

```bash
lore connections list
```

### `lore connections edit`

Edit an existing connection:

```bash
lore connections edit <name> [--db <url>] [--desc <description>]
```

### `lore connections remove`

Remove a connection:

```bash
lore connections remove <name> [--yes]
```

## Examples

### Typical Workflow

```bash
# Initial setup: add connections for your databases
lore connections add prod \
  --db "postgresql://readonly:pass@prod.db.company.com/maindb" \
  --desc "Production read-only replica"

lore connections add staging \
  --db "postgresql://admin:pass@staging.db.company.com/maindb" \
  --desc "Staging environment"

lore connections add local \
  --db "postgresql://dev:dev@localhost:5432/dev" \
  --desc "Local development"

# Daily usage: just pick from menu
lore init
# > 1. prod (postgresql://readonly:***@prod.db.company.com/maindb) - Production read-only replica
# > 2. staging (postgresql://admin:***@staging.db.company.com/maindb) - Staging environment
# > 3. local (postgresql://dev:***@localhost:5432/dev) - Local development
# > Enter number: 1

# Or use directly by name
lore init --use prod
```

### Team Setup

Share connection setup commands (without passwords) in your team docs:

```bash
# docs/setup.md
lore connections add prod-replica \
  --db "postgresql://readonly:YOUR_PASSWORD@prod.db.company.com/maindb" \
  --desc "Production read replica"
```

Team members can copy-paste and fill in their own credentials.

## Migration from Direct URLs

If you currently use:
```bash
lore init --db postgresql://user:pass@host/db
```

You can save it for future use:
```bash
lore init --db postgresql://user:pass@host/db --save-as my-db
```

Then use the shortcut going forward:
```bash
lore init --use my-db
```
