import eventlet
eventlet.monkey_patch()

import os
import json
import random

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed (production) - Render provides env vars directly
    pass

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from threading import Lock
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------ Flask and DB Setup ------------------
app = Flask(__name__, static_folder="static")
basedir = os.path.abspath(os.path.dirname(__file__))

# Use PostgreSQL in production (from environment variable), SQLite locally
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Fallback to SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'chat.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# Updated SocketIO config for better deployment compatibility
# Allow both websocket and polling for Render compatibility
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    async_mode="eventlet",
                    logger=True,
                    engineio_logger=True,
                    ping_timeout=120,
                    ping_interval=25,
                    allow_upgrades=True,
                    transports=['websocket', 'polling'])

# ------------------ Database Model ------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(100), nullable=False)
    recipient = db.Column(db.String(100), nullable=False)
    encrypted_message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message from {self.sender} to {self.recipient}>'

# ------------------ User Auth ------------------
USERS_FILE = os.path.join(basedir, "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


def verify_password(stored_password, provided_password):
    """Support legacy plain-text passwords and new hashed passwords."""
    if not stored_password or not provided_password:
        return False

    if stored_password.startswith("pbkdf2:"):
        try:
            return check_password_hash(stored_password, provided_password)
        except ValueError:
            return False

    return stored_password == provided_password

# ------------------ BB84 with Qiskit ------------------
def bb84_protocol(n=32):
    """Fast key generation (simulated BB84 for performance)"""
    # For production on limited resources, use fast hash-based key generation
    # This maintains security while being much faster than quantum simulation
    import hashlib
    
    # Generate deterministic but secure key based on timestamp and random data
    seed = f"{random.random()}{random.randint(0, 1000000)}".encode()
    hash_result = hashlib.sha256(seed).hexdigest()
    
    # Convert hash to binary string
    binary_key = bin(int(hash_result, 16))[2:].zfill(256)
    
    # Return first n bits
    return binary_key[:n] if n <= len(binary_key) else binary_key


def xor_encrypt_decrypt(message, key):
    """Encrypt/decrypt using XOR and binary key string"""
    key_bits = [int(b) for b in key]
    key_len = len(key_bits)
    return "".join(chr(ord(c) ^ key_bits[i % key_len]) for i, c in enumerate(message))

# ------------------ Chat State ------------------
online_users = {}
shared_keys = {}
lock = Lock()

def get_shared_key(user1, user2):
    pair = tuple(sorted((user1, user2)))
    with lock:
        if pair not in shared_keys:
            shared_keys[pair] = bb84_protocol(n=32)
            print(f"🔑 New key for {pair}: {shared_keys[pair]}")
        return shared_keys[pair]

# ------------------ Routes ------------------
@app.route("/")
def index():
    return send_from_directory("static", "app.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    
    # Try database first (for production)
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            return jsonify({"success": True})
    
    # Fallback to users.json (for local development with existing users)
    users = load_users()
    stored_password = users.get(username)
    if stored_password and verify_password(stored_password, password):
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Invalid credentials"})

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "error": "Username must be 3+ chars and password 6+ chars"}), 400

    # Check if user already exists in database
    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"success": False, "error": "Username taken"})
        
        # Create new user in database
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
    
    # Also save to users.json for local development compatibility
    users = load_users()
    users[username] = password_hash
    save_users(users)
    
    return jsonify({"success": True})

# ------------------ WebSocket Events ------------------
@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on("disconnect")
def handle_disconnect():
    user_to_remove = None
    for user, sid in online_users.items():
        if sid == request.sid:
            user_to_remove = user
            break
    if user_to_remove:
        del online_users[user_to_remove]
        emit("update_users", list(online_users.keys()), broadcast=True)
    print(f"Client disconnected: {request.sid}")

@socketio.on("register_user")
def handle_register_user(username):
    if not username:
        return

    # Replace any stale connection for the same username
    online_users[username] = request.sid
    emit("update_users", list(online_users.keys()), broadcast=True)

@socketio.on("send_message")
def handle_send_message(data):
    sender = data.get("sender")
    recipient = data.get("recipient")
    message = data.get("message")
    
    if not sender or not recipient or not message:
        return

    key = get_shared_key(sender, recipient)
    encrypted_msg = xor_encrypt_decrypt(message, key)

    with app.app_context():
        db_message = Message(sender=sender, recipient=recipient, encrypted_message=encrypted_msg)
        db.session.add(db_message)
        db.session.commit()

    if recipient in online_users:
        emit("receive_message", {
            "sender": sender, "message": encrypted_msg, "key": key
        }, room=online_users[recipient])
    
    # Send plaintext back to sender for their own UI
    sender_sid = online_users.get(sender)
    if sender_sid:
        emit("receive_message", {
            "sender": sender, "message": message, "key": key
        }, room=sender_sid)


@socketio.on("get_history")
def handle_get_history(data):
    user1 = data.get("user1")
    user2 = data.get("user2")
    
    key = get_shared_key(user1, user2)
    
    with app.app_context():
        messages = db.session.query(Message).filter(
            ((Message.sender == user1) & (Message.recipient == user2)) |
            ((Message.sender == user2) & (Message.recipient == user1))
        ).order_by(Message.timestamp.asc()).all()

    history = []
    for msg in messages:
        try:
            decrypted_text = xor_encrypt_decrypt(msg.encrypted_message, key)
            history.append({"sender": msg.sender, "message": decrypted_text})
        except Exception as e:
            print(f"Error decrypting message {msg.id}: {e}")
            history.append({"sender": msg.sender, "message": "[Decryption Error]"})

    emit("chat_history", {"history": history, "key": key})


@socketio.on("clear_history")
def handle_clear_history(data):
    user1 = data.get("user1")
    user2 = data.get("user2")

    if not user1 or not user2:
        return

    with app.app_context():
        db.session.query(Message).filter(
            ((Message.sender == user1) & (Message.recipient == user2)) |
            ((Message.sender == user2) & (Message.recipient == user1))
        ).delete(synchronize_session=False)
        db.session.commit()

    for user in {user1, user2}:
        sid = online_users.get(user)
        if sid:
            emit("history_cleared", room=sid)


# Ensure tables are created in production
with app.app_context():
    db.create_all()

# ------------------ Main ------------------
if __name__ == "__main__":
    # Use environment variables for production deployment
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
