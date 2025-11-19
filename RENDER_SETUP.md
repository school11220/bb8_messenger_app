# Render.com Configuration Guide

## 🗄️ Your Database (Already Created ✅)

**Database Name:** bb84-chat-db  
**Internal URL:** `postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db`

---

## 🚀 Deploy Your Web Service

### Step 1: Go to Render Dashboard
Visit: https://dashboard.render.com/

### Step 2: Create New Web Service
1. Click **"New +"** button (top right)
2. Select **"Web Service"**
3. Click **"Connect account"** if not connected to GitHub
4. Select repository: **school11220/bb8_messenger_app**
5. Click **"Connect"**

### Step 3: Configure Service

Copy these exact settings:

```
Name: bb84-quantum-chat
Region: (Choose closest to you - Singapore/Oregon/Frankfurt)
Branch: main
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn --worker-class eventlet -w 1 app:app
Instance Type: Free
```

### Step 4: Environment Variables

Click **"Advanced"** button, then **"Add Environment Variable"**

Add this ONE variable:

```
Key: DATABASE_URL
Value: postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db
```

**IMPORTANT:** 
- Use the **Internal Database URL** (starts with `postgresql://`)
- Do NOT use External URL
- Copy exactly as shown above

### Step 5: Deploy

1. Click **"Create Web Service"** button at bottom
2. Wait 5-10 minutes for initial deployment
3. Watch the logs for:
   ```
   ✓ Installing dependencies...
   ✓ Build successful
   ✓ Server initialized for eventlet
   ✓ Service started
   ```

### Step 6: Access Your App

Once deployed, your app will be available at:
```
https://bb84-quantum-chat.onrender.com
```
(Replace with your chosen service name)

---

## 🧪 Test Your Deployment

1. **Open the URL** in your browser
2. **Create an account:**
   - Username: testuser1
   - Password: test1234
   - Click "Sign Up"

3. **Open incognito/private window**
4. **Create second account:**
   - Username: testuser2
   - Password: test1234
   - Click "Sign Up"

5. **Test chat:**
   - Click on the other user in the sidebar
   - Type a message
   - See it appear in real-time!

---

## 📊 Monitor Your App

### View Logs:
1. Go to Render Dashboard
2. Click your service name
3. Click "Logs" tab
4. See real-time application logs

### Check Database:
1. Click on "bb84-chat-db" in dashboard
2. View connection info
3. Monitor storage usage (1GB free)

---

## 🔧 Common Issues & Solutions

### Issue: "Service Unavailable"
**Solution:** 
- Check if service is "Live" in dashboard
- Free tier apps sleep after 15 min - first request takes 30 sec

### Issue: "Database connection failed"
**Solution:**
- Verify DATABASE_URL in Environment Variables
- Check database is running (green dot in dashboard)
- Make sure you used INTERNAL URL, not external

### Issue: "Build failed"
**Solution:**
- Check Build Logs for specific error
- Verify requirements.txt has all dependencies
- Ensure Python 3 is selected as runtime

### Issue: WebSocket not connecting
**Solution:**
- Verify start command: `gunicorn --worker-class eventlet -w 1 app:app`
- Check that eventlet is in requirements.txt
- Look for errors in Logs tab

---

## 🔄 Update Your App

After making changes locally:

```bash
git add .
git commit -m "Your update message"
git push origin main
```

Render will automatically:
1. Detect the push
2. Rebuild your app
3. Deploy the new version
4. Takes 3-5 minutes

---

## 💰 Free Tier Limits

| Resource | Limit |
|----------|-------|
| Web Service | 750 hours/month (enough for 1 app 24/7) |
| Database | 1 GB storage |
| Bandwidth | Free tier included |
| Auto-sleep | After 15 min inactivity |
| Wake time | ~30 seconds on first request |

---

## 📱 Your App Features

Once deployed, users can:
- ✅ Create accounts (encrypted passwords)
- ✅ Login securely
- ✅ See online users in real-time
- ✅ Send encrypted messages instantly
- ✅ View message history
- ✅ Clear chat history
- ✅ See connection status
- ✅ Use from any device with internet

---

## 🎨 Dark Mode UI

Your app now features:
- Professional dark theme
- Purple gradient accents
- Glassmorphism effects
- Smooth animations
- High contrast for readability
- Mobile responsive design

---

## 🔒 Security Features

- ✅ Password hashing (pbkdf2:sha256)
- ✅ Message encryption (BB84-inspired XOR)
- ✅ HTTPS by default (Render provides)
- ✅ Environment variables (secure credentials)
- ✅ SQL injection protection (SQLAlchemy)
- ✅ Input validation

---

## 🎯 Final Checklist

Before deploying, ensure:
- [x] Code pushed to GitHub
- [x] Database created on Render
- [x] requirements.txt has all dependencies
- [x] Procfile configured correctly
- [x] Dark mode CSS applied
- [x] app.py has correct database handling

---

## 🌐 Share Your App

Once live, share your URL:
```
https://bb84-quantum-chat.onrender.com
```

Users can:
1. Visit the URL
2. Create account instantly
3. Start chatting with quantum-inspired encryption!

---

## 📞 Need Help?

1. Check Render Logs for errors
2. Review DEPLOYMENT.md for detailed troubleshooting
3. Verify environment variables are set correctly
4. Ensure database is running

---

## 🚀 You're Ready to Deploy!

Follow the steps above and your BB84 Quantum Chat will be live in 10 minutes!

**Database:** ✅ Already created  
**Code:** ✅ Ready to deploy  
**UI:** ✅ Dark mode enabled  
**Docs:** ✅ Complete

Just create the web service and add the DATABASE_URL! 🎉
