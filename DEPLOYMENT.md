# BB84 Quantum Chat - Deployment Guide

## 🚀 Free Deployment on Render

### Prerequisites
- GitHub account with this repository pushed
- Render account (free tier): https://render.com

---

## Step 1: Prepare Your Repository

Ensure these files exist in your repository:
- ✅ `app.py` - Main Flask application
- ✅ `requirements.txt` - Python dependencies
- ✅ `Procfile` - Render process configuration
- ✅ `static/` folder - Frontend files

---

## Step 2: Set Up PostgreSQL Database on Render

### 2.1 Create Database (Already Done ✅)
You've already created: `bb84-chat-db`

**Your Database Details:**
```
Internal Database URL: postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db
```

### 2.2 Get Connection String
1. Go to Render Dashboard → Your database (`bb84-chat-db`)
2. Copy the **Internal Database URL** (you already have it)
3. Keep this URL safe - you'll need it in Step 3

---

## Step 3: Deploy Web Service on Render

### 3.1 Create New Web Service
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `school11220/bb8_messenger_app`
4. Click **"Connect"**

### 3.2 Configure Web Service

Fill in the settings:

| Setting | Value |
|---------|-------|
| **Name** | `bb84-quantum-chat` (or any name you like) |
| **Region** | Choose closest to you |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn --worker-class eventlet -w 1 app:app` |
| **Instance Type** | `Free` |

### 3.3 Add Environment Variables

Click **"Advanced"** → **"Add Environment Variable"**

Add this variable:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db` |

**Important:** Make sure to use the **Internal Database URL**, not the External one!

### 3.4 Deploy
1. Click **"Create Web Service"**
2. Wait 5-10 minutes for the initial deploy
3. Watch the logs for any errors

---

## Step 4: Verify Deployment

### 4.1 Check Database Connection
Once deployed, check the logs for:
```
✓ Database tables created successfully
✓ SocketIO server started
```

### 4.2 Test Your App
1. Open your Render URL (e.g., `https://bb84-quantum-chat.onrender.com`)
2. Create a new account
3. Try logging in
4. Open another browser/incognito window
5. Create another account and test real-time chat

---

## 🔧 Troubleshooting

### Database Connection Issues

**Problem:** `FATAL: no pg_hba.conf entry for host`
**Solution:** Make sure you're using the **Internal Database URL**, not External

**Problem:** `relation "message" does not exist`
**Solution:** Tables are created automatically on first run. Restart the service if needed.

### WebSocket Issues

**Problem:** "Unable to reach the server"
**Solution:** 
- Check if the service is running in Render dashboard
- Verify no errors in the logs
- Make sure you're using `eventlet` worker in start command

### Free Tier Limitations

- Service sleeps after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- Database limited to 1GB storage (plenty for chat app)

---

## 📝 Environment Variables Reference

Set these in Render Dashboard → Your Service → Environment:

```bash
DATABASE_URL=postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db
```

The `PORT` variable is automatically set by Render.

---

## 🎯 Quick Commands for Local Testing

### Install dependencies:
```bash
pip install -r requirements.txt
```

### Run locally with SQLite (no database setup needed):
```bash
python app.py
```

### Run locally with your Render PostgreSQL:
```bash
export DATABASE_URL="postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db"
python app.py
```

---

## ✨ Features Included

- ✅ User registration with password hashing
- ✅ Secure login system
- ✅ Real-time messaging with WebSockets
- ✅ BB84-inspired encryption
- ✅ Message history persistence
- ✅ Online user tracking
- ✅ Dark mode UI
- ✅ Connection status indicator
- ✅ Clear chat history feature

---

## 🔒 Security Notes

1. **Passwords are hashed** using `pbkdf2:sha256`
2. **Messages are encrypted** before storage
3. **Database credentials** are environment variables (never committed to git)
4. For production use, consider:
   - Adding rate limiting
   - Implementing session management
   - Using HTTPS (Render provides this automatically)
   - Adding CSRF protection

---

## 🚀 Future Improvements

1. **Add user avatars** - Profile pictures
2. **File sharing** - Send images/documents
3. **Group chats** - Multiple users in one conversation
4. **Message reactions** - Emoji reactions to messages
5. **Typing indicators** - Show when someone is typing
6. **Read receipts** - Message read status
7. **Push notifications** - Desktop/mobile notifications
8. **Message search** - Search chat history
9. **Export chats** - Download conversation history
10. **Admin panel** - Manage users and content

---

## 📞 Support

If you encounter issues:
1. Check Render logs for error messages
2. Verify all environment variables are set correctly
3. Ensure database is running and accessible
4. Check that your start command matches: `gunicorn --worker-class eventlet -w 1 app:app`

---

## 🎉 Your App is Live!

Your BB84 Quantum Chat is now deployed and accessible worldwide! Share your Render URL with friends to start chatting securely.

**Example URL:** `https://bb84-quantum-chat.onrender.com`

Remember: Free tier apps sleep after inactivity, so the first request may take 30 seconds to wake up.
