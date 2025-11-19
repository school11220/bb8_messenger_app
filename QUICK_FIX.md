# Quick Fix: "Unable to reach the server" on Render

## 🔍 Diagnose the Problem

### Step 1: Check Render Logs (DO THIS FIRST!)

1. Go to: https://dashboard.render.com
2. Click on your service: **bb84-chat** (or whatever you named it)
3. Click **"Logs"** tab
4. Scroll to the bottom to see recent errors

**Look for these error patterns:**

❌ **Connection Error:**
```
could not connect to server
timeout
Connection refused
```
**Fix:** Update DATABASE_URL to use Internal URL (see Step 2)

❌ **Module Not Found:**
```
ModuleNotFoundError: No module named 'X'
```
**Fix:** Missing dependency - check requirements.txt

❌ **Port Binding Error:**
```
Address already in use
Failed to bind
```
**Fix:** Check Start Command uses gunicorn

❌ **Database Error:**
```
relation "message" does not exist
psycopg2.OperationalError
```
**Fix:** Database tables not created - this should auto-fix on first run

---

## ✅ Step 2: Fix Environment Variables

### In Render Dashboard:

1. Go to your web service
2. Click **"Environment"** in left sidebar
3. Find **DATABASE_URL**

**Change it to use INTERNAL URL:**

❌ **Wrong (External URL):**
```
postgresql://bb84_chat_db_user:...@dpg-d4erovuuk2gs739nq80g-a.singapore-postgres.render.com/bb84_chat_db
```

✅ **Correct (Internal URL):**
```
postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db
```

**Key difference:** No `.singapore-postgres.render.com` in the internal URL!

4. Click **"Save Changes"**
5. Click **"Manual Deploy"** → **"Deploy latest commit"**

---

## ✅ Step 3: Verify Start Command

In Render Dashboard → Your Service → Settings:

**Start Command should be:**
```bash
gunicorn --worker-class eventlet -w 1 app:app
```

If it's different, change it and save.

---

## ✅ Step 4: Force Redeploy

1. Click **"Manual Deploy"** button (top right)
2. Select **"Clear build cache & deploy"**
3. Wait 2-3 minutes
4. Watch the logs for any errors

---

## ✅ Step 5: Test Your App

Once you see: **"Deploy live ✓"**

1. Click on your service URL at the top
2. You should see the login page with dark purple UI
3. Try to login or create an account

---

## 🚨 Still Not Working?

### Share these with me:

1. **Screenshot of the Render Logs** (last 20-30 lines)
2. **Your DATABASE_URL value** (just tell me if it has `.singapore-postgres.render.com` or not)
3. **Service Status** (Is it "Live" or "Deploy failed"?)

### Quick Checks:

✓ Database status is "Available"  
✓ Web service and database are in **same region** (both Singapore)  
✓ Using **Internal** database URL (no .render.com suffix)  
✓ All files committed to GitHub  
✓ Procfile exists in repository root  

---

## Common Render Issues:

### Issue: Build succeeds but site shows error

**Solution:** This usually means:
- Database connection is wrong → Fix DATABASE_URL
- App crashes on startup → Check logs for Python errors

### Issue: Build fails

**Solution:** 
- Missing dependency in requirements.txt
- Python version incompatibility
- Check build logs for specific error

### Issue: Site loads but can't login

**Solution:**
- Socket.IO connection issue
- CORS configuration
- This is easier to fix once site loads!

---

## Test Locally First (Optional)

Before deploying, test locally:

```bash
cd "/home/shivam/Downloads/BB84 messenger"
./start_server.sh
```

Open: http://localhost:5000

If it works locally but not on Render:
- It's likely a DATABASE_URL issue
- Or missing environment variables on Render
