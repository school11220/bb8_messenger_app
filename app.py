import os
import webbrowser
import json
import random
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from threading import Lock
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# ------------------ Flask and DB Setup ------------------
app = Flask(__name__, static_folder="static")
# Use an absolute path for the database to avoid issues with PyInstaller's temp folder
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

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
    """Simulate BB84 key exchange using Qiskit AerSimulator"""
    alice_bits = [random.randint(0, 1) for _ in range(n)]
    alice_bases = [random.randint(0, 1) for _ in range(n)]
    bob_bases = [random.randint(0, 1) for _ in range(n)]
    bob_results = []

    simulator = AerSimulator()

    for bit, a_basis, b_basis in zip(alice_bits, alice_bases, bob_bases):
        qc = QuantumCircuit(1, 1)
        if bit == 1: qc.x(0)
        if a_basis == 1: qc.h(0)
        if b_basis == 1: qc.h(0)
        qc.measure(0, 0)
        
        result = simulator.run(qc, shots=1).result()
        counts = result.get_counts()
        measured_bit = int(list(counts.keys())[0])
        bob_results.append(measured_bit)

    shared_bits = [a for a, ab, bb in zip(alice_bits, alice_bases, bob_bases) if ab == bb]
    
    # This is a simplified check. A real implementation would compare a subset of bits.
    final_key_bits = [ab for ab, bb, res in zip(alice_bits, alice_bases, bob_results) if ab == bb]

    if not final_key_bits: return "01010101" # Fallback key
    return "".join(map(str, final_key_bits))

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
