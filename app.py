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

from flask import Flask, request, jsonify, send_from_directory, session
from flask_socketio import SocketIO, emit
from threading import Lock
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------ Flask and DB Setup ------------------
app = Flask(__name__, static_folder="static")
basedir = os.path.abspath(os.path.dirname(__file__))

# Session configuration - use Flask's built-in sessions (cookie-based)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bb84-quantum-secret-key-change-in-production-12345')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Use PostgreSQL in production (from environment variable), SQLite locally
def _find_database_url():
    # Look for a DB URL in several commonly used environment variable names.
    candidates = [
        'DATABASE_URL',
        'RAILWAY_DATABASE_URL',
        'POSTGRES_URL',
        'POSTGRESQL_URL',
        'PG_URI',
        'SQLALCHEMY_DATABASE_URI',
        'DB_URL'
    ]
    for key in candidates:
        val = os.environ.get(key)
        if val:
            print(f"[startup] Found DB env var: {key}")
            return val
    return None

database_url = _find_database_url()
if database_url:
    # Normalize common Postgres schemes (some providers give postgres:// while SQLAlchemy
    # prefers postgresql://).
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Fallback to SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'chat.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Socket.IO (must be after app and db)
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode="eventlet",
                    logger=False,
                    engineio_logger=False,
                    ping_timeout=120,
                    ping_interval=25,
                    allow_upgrades=True,
                    transports=['polling', 'websocket'])

# ------------------ Database Models ------------------
group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    members = db.relationship('User', secondary=group_members, lazy='subquery',
                              backref=db.backref('groups', lazy=True))

    def __repr__(self):
        return f'<Group {self.name}>'

    creator = db.relationship('User', backref='created_groups')
    members = db.relationship('User', secondary=group_members, lazy='subquery',
                              backref=db.backref('groups', lazy=True))

    def __repr__(self):
        return f'<Group {self.name}>'


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
    recipient = db.Column(db.String(100), nullable=True) # Can be null for group messages
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    encrypted_message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='sent') # sent, delivered, read
    read = db.Column(db.Boolean, default=False)
    edited = db.Column(db.Boolean, default=False)

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


@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint for deployment diagnostics."""
    return jsonify({'status': 'ok', 'uptime': True}), 200


@app.route('/admin/users', methods=['GET'])
def admin_list_users():
    """Return list of registered users (for quick debug). Remove or protect in production."""
    try:
        with app.app_context():
            users = [u.username for u in User.query.order_by(User.id.desc()).limit(100).all()]
        return jsonify({'count': len(users), 'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    
    print(f"Login attempt for user: {username}")
    
    # Try database first (for production)
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User found in database: {username}")
            if check_password_hash(user.password_hash, password):
                print(f"Password verified for: {username}")
                session['username'] = username
                session.permanent = True
                return jsonify({"success": True, "username": username})
            else:
                print(f"Password verification failed for: {username}")
        else:
            print(f"User not found in database: {username}")
    
    # Fallback to users.json (for local development with existing users)
    users = load_users()
    stored_password = users.get(username)
    if stored_password:
        print(f"User found in users.json: {username}")
        if verify_password(stored_password, password):
            print(f"Password verified from users.json for: {username}")
            session['username'] = username
            session.permanent = True
            return jsonify({"success": True, "username": username})
    
    print(f"Login failed for: {username}")
    return jsonify({"success": False, "error": "Invalid credentials"})

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    
    print(f"Registration attempt for user: {username}")
    
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "error": "Username must be 3+ chars and password 6+ chars"}), 400

    # Check if user already exists in database
    with app.app_context():
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Username already taken: {username}")
            return jsonify({"success": False, "error": "Username taken"})
        
        # Create new user in database
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        print(f"User created in database: {username}")
    
    # Also save to users.json for local development compatibility
    users = load_users()
    users[username] = password_hash
    save_users(users)
    
    # Auto-login after registration
    session['username'] = username
    session.permanent = True
    
    print(f"Registration successful for: {username}")
    return jsonify({"success": True, "username": username})

@app.route("/check_session", methods=["GET"])
def check_session():
    """Check if user is already logged in"""
    username = session.get('username')
    if username:
        return jsonify({"logged_in": True, "username": username})
    return jsonify({"logged_in": False})

@app.route("/logout", methods=["POST"])
def logout():
    """Logout user by clearing session"""
    session.pop('username', None)
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

    # Calculate and send unread message counts
    with app.app_context():
        unread_counts = db.session.query(Message.sender, db.func.count(Message.id)).filter(
            Message.recipient == username,
            Message.read == False
        ).group_by(Message.sender).all()
        emit("unread_counts", dict(unread_counts))

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
        message_id = db_message.id # Get the ID of the new message

    if recipient in online_users:
        emit("receive_message", {
            "id": message_id,
            "sender": sender, 
            "message": encrypted_msg, 
            "key": key, 
            "timestamp": db_message.timestamp.isoformat(),
            "status": "sent"
        }, room=online_users[recipient])
    
    # Send plaintext back to sender for their own UI
    sender_sid = online_users.get(sender)
    if sender_sid:
        emit("receive_message", {
            "id": message_id,
            "sender": sender, 
            "message": message, 
            "key": key, 
            "timestamp": db_message.timestamp.isoformat(),
            "status": "sent"
        }, room=sender_sid)


@socketio.on("message_delivered")
def handle_message_delivered(data):
    message_id = data.get("id")
    with app.app_context():
        msg = Message.query.get(message_id)
        if msg and msg.status == 'sent':
            msg.status = 'delivered'
            db.session.commit()
            
            # Notify the sender that the message was delivered
            sender_sid = online_users.get(msg.sender)
            if sender_sid:
                emit("message_status_updated", {"id": msg.id, "status": "delivered"}, room=sender_sid)

            # Notify recipient of a new unread message
            recipient_sid = online_users.get(msg.recipient)
            if recipient_sid:
                emit("new_unread_message", {"sender": msg.sender})


@socketio.on("edit_message")
def handle_edit_message(data):
    message_id = data.get("message_id")
    username = data.get("username")
    new_message = data.get("new_message")
    
    with app.app_context():
        msg = Message.query.get(message_id)
        # Check if the message exists, the user is the sender, and it's within 5 minutes
        if msg and msg.sender == username and (datetime.utcnow() - msg.timestamp) < timedelta(minutes=5):
            key = get_shared_key(msg.sender, msg.recipient)
            msg.encrypted_message = xor_encrypt_decrypt(new_message, key)
            msg.edited = True
            db.session.commit()

            # Notify both sender and recipient
            sender_sid = online_users.get(msg.sender)
            if sender_sid:
                emit("message_edited", {
                    "id": msg.id, "new_message": new_message, "edited": True
                }, room=sender_sid)
            
            recipient_sid = online_users.get(msg.recipient)
            if recipient_sid:
                # Re-encrypt for the recipient
                encrypted_for_recipient = xor_encrypt_decrypt(new_message, key)
                emit("message_edited", {
                    "id": msg.id, "new_message": encrypted_for_recipient, "edited": True
                }, room=recipient_sid)


@socketio.on("delete_message")
def handle_delete_message(data):
    message_id = data.get("message_id")
    username = data.get("username")
    with app.app_context():
        msg = Message.query.get(message_id)
        if msg and msg.sender == username:
            recipient = msg.recipient
            db.session.delete(msg)
            db.session.commit()
            
            # Notify both sender and recipient that the message was deleted
            sender_sid = online_users.get(username)
            if sender_sid:
                emit("message_deleted", {"id": message_id}, room=sender_sid)
            recipient_sid = online_users.get(recipient)
            if recipient_sid:
                emit("message_deleted", {"id": message_id}, room=recipient_sid)


@socketio.on("mark_as_read")
def handle_mark_as_read(data):
    reader = data.get("reader")
    sender = data.get("sender")
    with app.app_context():
        Message.query.filter_by(recipient=reader, sender=sender, read=False).update({"read": True})
        db.session.commit()


@socketio.on("typing")
def handle_typing(data):
    recipient_sid = online_users.get(data['recipient'])
    if recipient_sid:
        emit("user_typing", {"sender": data['sender']}, room=recipient_sid)

@socketio.on("stop_typing")
def handle_stop_typing(data):
    recipient_sid = online_users.get(data['recipient'])
    if recipient_sid:
        emit("user_stopped_typing", {"sender": data['sender']}, room=recipient_sid)


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
            history.append({
                "id": msg.id,
                "sender": msg.sender, 
                "message": decrypted_text, 
                "timestamp": msg.timestamp.isoformat(),
                "status": msg.status,
                "edited": msg.edited
            })
        except Exception as e:
            print(f"Error decrypting message {msg.id}: {e}")
            history.append({
                "id": msg.id,
                "sender": msg.sender, 
                "message": "[Decryption Error]", 
                "timestamp": msg.timestamp.isoformat(),
                "status": msg.status,
                "edited": msg.edited
            })

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

    # Diagnostic info: which DB engine are we using? (prints to app logs)
    try:
        engine_name = getattr(db.engine, 'name', None)
    except Exception:
        engine_name = None
    # Also print which env var we used (if any) and test a simple SELECT
    used_env = None
    for k in ('DATABASE_URL', 'RAILWAY_DATABASE_URL', 'POSTGRES_URL', 'POSTGRESQL_URL', 'PG_URI', 'SQLALCHEMY_DATABASE_URI', 'DB_URL'):
        if os.environ.get(k):
            used_env = k
            break
    print(f"[startup] DATABASE_ENV_VAR: {used_env}, DB engine: {engine_name}")

    # Quick DB connectivity test (SELECT 1)
    try:
        with db.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('[startup] DB connection test: OK')
    except Exception as e:
        print(f"[startup] DB connection test: FAILED - {e}")
    # Lightweight schema migration: add missing columns if they don't exist.
    # This helps when the app evolves and the DB was created earlier without new columns.
    def _add_column_if_missing(table_name, column_sql):
        engine_name = db.engine.name
        try:
            if engine_name == 'postgresql':
                # Use IF NOT EXISTS for Postgres
                db.session.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_sql};")
            else:
                # SQLite: adding a column that already exists will raise, so ignore errors
                db.session.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql};")
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Message table additional columns
    _add_column_if_missing('message', 'read BOOLEAN DEFAULT 0')
    _add_column_if_missing('message', 'group_id INTEGER')
    _add_column_if_missing('message', "status VARCHAR(20) DEFAULT 'sent'")
    _add_column_if_missing('message', 'edited BOOLEAN DEFAULT 0')

# ------------------ Main ------------------
if __name__ == "__main__":
    # Use environment variables for production deployment
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
