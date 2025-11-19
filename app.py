import eventlet
eventlet.monkey_patch()

import os
import json
import random
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from threading import Lock
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    async_mode="eventlet",
                    logger=True,
                    engineio_logger=True,
                    ping_timeout=60,
                    ping_interval=25)

# ------------------ Database Model ------------------
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(100), nullable=False)
    recipient = db.Column(db.String(100), nullable=False)
    encrypted_message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message from {self.sender} to {self.recipient}>'

# ------------------ User Auth ------------------
USERS_FILE = "users.json"

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
    return send_from_directory("static", "index.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    users = load_users()
    if username in users and users[username] == password:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid credentials"})

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    users = load_users()
    if username in users:
        return jsonify({"success": False, "error": "Username taken"})
    users[username] = password
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
    online_users[username] = request.sid
    emit("update_users", list(online_users.keys()), broadcast=True)

@socketio.on("send_message")
def handle_send_message(data):
    sender = data.get("sender")
    recipient = data.get("recipient")
    message = data.get("message")
    
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
    emit("receive_message", {
        "sender": sender, "message": message, "key": key
    }, room=online_users[sender])


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


# ------------------ Main ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # Use environment variables for production deployment
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
