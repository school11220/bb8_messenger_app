# How to Connect Your Render Database

## Step 1: Get Your External Database URL

1. Go to your Render dashboard (the screenshot you showed)
2. Click on your database: **bb84-chat-db**
3. Scroll to the **"Connections"** section
4. Look for **"External Database URL"**
5. Click the eye icon or copy button to reveal/copy the full URL

The URL should look like:
```
postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a.oregon-postgres.render.com/bb84_chat_db
```

## Step 2: Update the .env File

1. Open the `.env` file in this project
2. Replace the DATABASE_URL value with your **External Database URL** from Render
3. Save the file

## Step 3: Start the Server

Run the start script:
```bash
./start_server.sh
```

Or manually:
```bash
# Initialize database
.venv/bin/python init_db.py

# Start server
.venv/bin/python app.py
```

## Step 4: Test the Application

1. Open your browser to: http://localhost:5000
2. Try logging in with existing credentials or create a new account
3. The data will now be stored in your Render PostgreSQL database!

## Troubleshooting

### Error: "could not connect to server"
- Check that your External Database URL is correct
- Verify your database is active in Render dashboard
- Make sure you're using the EXTERNAL URL (not internal)

### Error: "relation does not exist"
- Run `init_db.py` to create the tables:
  ```bash
  .venv/bin/python init_db.py
  ```

### Error: "authentication failed"
- Double-check the password in your DATABASE_URL
- Copy the full External Database URL from Render again

## For Render Deployment

When deploying to Render as a web service:
- You DON'T need to manually set DATABASE_URL
- Render automatically uses the environment variable you set
- Just deploy the app and Render will use the Internal Database URL automatically
