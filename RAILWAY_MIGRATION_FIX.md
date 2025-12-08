# Railway Database Migration Fix

## Problem
The Railway PostgreSQL database is missing columns that the application expects, causing errors like:
```
psycopg2.errors.UndefinedColumn: column user.status does not exist
```

## Solution

### Option 1: Run Migration Script (Recommended)

1. **Connect to Railway via CLI:**
   ```bash
   railway login
   railway link
   ```

2. **Run the migration script:**
   ```bash
   railway run python migrate_railway_db.py
   ```

   This will:
   - Check for missing columns in all tables
   - Add missing columns with proper defaults
   - Create any missing tables
   - Update the schema to match your models

### Option 2: Manual SQL Execution

If you prefer to run SQL manually in the Railway database console:

```sql
-- Add missing columns to user table
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'online';
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS status_message VARCHAR(200);
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT NOW();
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS show_last_seen BOOLEAN DEFAULT TRUE;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS show_read_receipts BOOLEAN DEFAULT TRUE;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS allow_messages_from VARCHAR(20) DEFAULT 'everyone';

-- Add missing columns to message table
ALTER TABLE message ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'sent';
ALTER TABLE message ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE;
ALTER TABLE message ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text';
ALTER TABLE message ADD COLUMN IF NOT EXISTS file_url VARCHAR(500);
ALTER TABLE message ADD COLUMN IF NOT EXISTS file_name VARCHAR(255);
ALTER TABLE message ADD COLUMN IF NOT EXISTS reply_to_id INTEGER REFERENCES message(id);
ALTER TABLE message ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE message ADD COLUMN IF NOT EXISTS starred BOOLEAN DEFAULT FALSE;
ALTER TABLE message ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE message ADD COLUMN IF NOT EXISTS deleted_for VARCHAR(500);

-- Create message_reaction table if not exists
CREATE TABLE IF NOT EXISTS message_reaction (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES message(id) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL,
    reaction VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Create group_admin table with permissions
CREATE TABLE IF NOT EXISTS group_admin (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL,
    role VARCHAR(50) DEFAULT 'member',
    can_add_members BOOLEAN DEFAULT FALSE,
    can_remove_members BOOLEAN DEFAULT FALSE,
    can_edit_info BOOLEAN DEFAULT FALSE,
    can_send_messages BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(group_name, username)
);

-- Create device_session table for multi-device sync
CREATE TABLE IF NOT EXISTS device_session (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    device_token VARCHAR(200) UNIQUE NOT NULL,
    paired_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

-- Create group_invitation table
CREATE TABLE IF NOT EXISTS group_invitation (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    token VARCHAR(200) UNIQUE NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    max_uses INTEGER DEFAULT 1,
    current_uses INTEGER DEFAULT 0
);

-- Create call table
CREATE TABLE IF NOT EXISTS call (
    id SERIAL PRIMARY KEY,
    caller VARCHAR(100) NOT NULL,
    callee VARCHAR(100) NOT NULL,
    call_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'initiated',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration INTEGER DEFAULT 0
);
```

### Option 3: Reset and Recreate (Nuclear Option)

⚠️ **WARNING: This will delete all existing data!**

1. In Railway dashboard, go to your PostgreSQL database
2. Delete the database
3. Create a new PostgreSQL database
4. Redeploy your application - tables will be created automatically

### Option 4: Add Migration to Deployment

Add this to your Railway deployment configuration:

1. **Add to `railway.json` (create if doesn't exist):**
   ```json
   {
     "build": {
       "builder": "NIXPACKS"
     },
     "deploy": {
       "startCommand": "python migrate_railway_db.py && python app.py"
     }
   }
   ```

2. **Or add to `Procfile`:**
   ```
   release: python migrate_railway_db.py
   web: python app.py
   ```

## Verify Migration

After running the migration, check the logs:

```bash
railway logs
```

You should see:
```
[migrate] Connected successfully
[migrate] Checking 'user' table...
  [+] Adding column: status
  [+] Adding column: status_message
  ...
[migrate] ✅ Migration completed successfully!
```

## Common Issues

### Issue: "relation 'user' does not exist"
**Solution:** No tables exist yet. Deploy the app first, then run migration.

### Issue: "permission denied"
**Solution:** Make sure your database user has ALTER TABLE permissions.

### Issue: Migration script not found
**Solution:** Make sure `migrate_railway_db.py` is committed to your repo:
```bash
git add migrate_railway_db.py
git commit -m "Add database migration script"
git push
```

## Rollback (If Needed)

If something goes wrong, you can remove added columns:

```sql
-- Remove columns from user table
ALTER TABLE "user" DROP COLUMN IF EXISTS status;
ALTER TABLE "user" DROP COLUMN IF EXISTS status_message;
-- ... etc
```

## Future Migrations

For future schema changes:
1. Update models in `app.py`
2. Update `migrate_railway_db.py` with new columns
3. Run migration on Railway
4. Deploy new code

## Support

If you encounter issues:
1. Check Railway logs: `railway logs`
2. Check database connection: `railway run python test_db_connection.py`
3. Verify environment variables are set correctly in Railway dashboard
