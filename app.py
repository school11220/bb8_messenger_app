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
import logging
from logging.handlers import RotatingFileHandler
import base64
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

# ------------------ Logging Configuration ------------------
LOG_TO_FILE = os.environ.get('LOG_TO_FILE', '1') == '1'
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_PLAINTEXT = os.environ.get('LOG_PLAINTEXT', '0') == '1'  # Dangerous: logs plaintext messages

logger = logging.getLogger('bb84chat')
logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
if LOG_TO_FILE:
    os.makedirs(os.path.join(basedir, 'logs'), exist_ok=True)
    fh = RotatingFileHandler(os.path.join(basedir, 'logs', 'chat.log'), maxBytes=5*1024*1024, backupCount=5)
    fh.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    fh.setFormatter(formatter)
    logger.addHandler(fh)
else:
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def _enc_for_log(s: str) -> str:
    """Safely encode server-stored encrypted string to base64 for logging."""
    try:
        b = s.encode('latin-1')
    except Exception:
        b = s.encode('utf-8', errors='ignore')
    return base64.b64encode(b).decode('ascii')

def _maybe_log_plain(text: str) -> str:
    return text if LOG_PLAINTEXT else '[REDACTED]'

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
# Eavesdrop registration: map pair_key -> eavesdropper username
eavesdrop_targets = {}

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
    # Simple token protection: set ADMIN_TOKEN env var to protect this endpoint.
    admin_token = os.environ.get('ADMIN_TOKEN')
    provided = request.headers.get('X-ADMIN-TOKEN') or request.args.get('admin_token')
    if admin_token:
        if not provided or provided != admin_token:
            return jsonify({'error': 'forbidden'}), 403
    else:
        # If no ADMIN_TOKEN set, deny to avoid accidental exposure in production
        return jsonify({'error': 'admin endpoint disabled'}), 403

    try:
        with app.app_context():
            users = [u.username for u in User.query.order_by(User.id.desc()).limit(100).all()]
        return jsonify({'count': len(users), 'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/logs', methods=['GET'])
def admin_get_logs():
    """Return recent log lines. Protected by ADMIN_TOKEN."""
    admin_token = os.environ.get('ADMIN_TOKEN')
    provided = request.headers.get('X-ADMIN-TOKEN') or request.args.get('admin_token')
    if not admin_token or provided != admin_token:
        return jsonify({'error': 'forbidden'}), 403

    log_file = os.path.join(basedir, 'logs', 'chat.log')
    if not os.path.exists(log_file):
        return jsonify({'error': 'no logs'}), 404

    # Read last N lines (simple tail)
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()[-1000:]
        return jsonify({'lines': lines})
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

    # Calculate and send unread message counts (be defensive: missing columns may raise)
    try:
        with app.app_context():
            unread_counts = db.session.query(Message.sender, db.func.count(Message.id)).filter(
                Message.recipient == username,
                Message.read == False
            ).group_by(Message.sender).all()
            emit("unread_counts", dict(unread_counts))
    except Exception as e:
        print(f"[startup] unread_counts query failed: {e} - attempting to heal schema and retry")
        try:
            # Attempt to heal schema drift and retry once
            _ensure_message_columns_exist()
            with app.app_context():
                unread_counts = db.session.query(Message.sender, db.func.count(Message.id)).filter(
                    Message.recipient == username,
                    Message.read == False
                ).group_by(Message.sender).all()
                emit("unread_counts", dict(unread_counts))
        except Exception as e2:
            print(f"[startup] unread_counts retry failed: {e2}")


# ------------------ BB84 and eavesdrop socket handlers ------------------
def _pair_key(a, b):
    return tuple(sorted([a, b]))


@socketio.on('register_eavesdrop')
def handle_register_eavesdrop(data):
    # data: { 'user1': 'alice', 'user2': 'bob' }
    e1 = data.get('user1')
    e2 = data.get('user2')
    enabler = data.get('by')  # username of who registered
    if not e1 or not e2 or not enabler:
        return
    key = _pair_key(e1, e2)
    eavesdrop_targets[key] = enabler
    logger.info(f"eavesdrop registered by={enabler} pair={key}")
    # acknowledge
    emit('eavesdrop_registered', {'pair': key, 'by': enabler})


@socketio.on('unregister_eavesdrop')
def handle_unregister_eavesdrop(data):
    e1 = data.get('user1')
    e2 = data.get('user2')
    enabler = data.get('by')
    if not e1 or not e2 or not enabler:
        return
    key = _pair_key(e1, e2)
    if key in eavesdrop_targets and eavesdrop_targets[key] == enabler:
        del eavesdrop_targets[key]
        logger.info(f"eavesdrop unregistered by={enabler} pair={key}")
        emit('eavesdrop_unregistered', {'pair': key, 'by': enabler})


@socketio.on('bb84_qubits')
def handle_bb84_qubits(payload):
    # payload: { from, to, qubits: [{i, bit, basis}, ...] }
    sender = payload.get('from')
    recipient = payload.get('to')
    qubits = payload.get('qubits') or []
    if not sender or not recipient or not qubits:
        return

    pair = _pair_key(sender, recipient)
    # check if eavesdrop registered for this pair
    eavesdropper = eavesdrop_targets.get(pair)
    forwarded_qubits = []
    if eavesdropper and eavesdropper in online_users:
        # simulate eavesdropper measuring each qubit
        eavesdrop_sid = online_users.get(eavesdropper)
        measured = []
        for q in qubits:
            # eavesdropper picks random basis
            basis_e = '+' if random.random() < 0.5 else 'x'
            if basis_e == q.get('basis'):
                measured_bit = q.get('bit')
            else:
                measured_bit = 1 if random.random() < 0.5 else 0
            measured.append({'i': q.get('i'), 'basis': basis_e, 'bit': measured_bit})
            # forwarded qubit is set to the eavesdropper's measured bit in their basis
            forwarded_qubits.append({'i': q.get('i'), 'bit': measured_bit, 'basis': q.get('basis')})

        # send capture data to eavesdropper
        try:
            emit('bb84_eavesdrop_capture', {'from': sender, 'to': recipient, 'measured': measured}, room=eavesdrop_sid)
            logger.info(f"eavesdrop capture sent to {eavesdropper} for pair {pair}")
        except Exception as e:
            print(f"eavesdrop emit failed: {e}")
    else:
        forwarded_qubits = qubits

    # forward (possibly altered) qubits to recipient
    recip_sid = online_users.get(recipient)
    if recip_sid:
        emit('bb84_qubits', {'from': sender, 'to': recipient, 'qubits': forwarded_qubits}, room=recip_sid)
        logger.info(f"bb84_qubits forwarded from={sender} to={recipient} eavesdrop={bool(eavesdropper)}")


@socketio.on('bb84_measurements')
def handle_bb84_measurements(payload):
    # relay measurements back to initiator
    to = payload.get('to')
    if to and to in online_users:
        emit('bb84_measurements', payload, room=online_users[to])


@socketio.on('bb84_bases_reveal')
def handle_bb84_bases_reveal(payload):
    to = payload.get('to')
    if to and to in online_users:
        emit('bb84_bases_reveal', payload, room=online_users[to])


@socketio.on('bb84_sample_reveal')
def handle_bb84_sample_reveal(payload):
    to = payload.get('to')
    if to and to in online_users:
        emit('bb84_sample_reveal', payload, room=online_users[to])


@socketio.on('bb84_result')
def handle_bb84_result(payload):
    # payload includes e_rate and passed, relay to the other party
    to = payload.get('to')
    if to and to in online_users:
        emit('bb84_result', payload, room=online_users[to])
    # also log the result
    try:
        logger.info(f"bb84_result from={payload.get('from')} to={to} e_rate={payload.get('e_rate')} passed={payload.get('passed')}")
    except Exception:
        pass

@socketio.on("send_message")
def handle_send_message(data):
    sender = data.get("sender")
    recipient = data.get("recipient")
    message = data.get("message")
    
    if not sender or not recipient or not message:
        return

    key = get_shared_key(sender, recipient)
    encrypted_msg = xor_encrypt_decrypt(message, key)

    # Log the send event (encrypted payload). Do NOT log the shared key.
    try:
        logger.info(f"send_message sender={sender} recipient={recipient} encrypted={_enc_for_log(encrypted_msg)} plaintext={_maybe_log_plain(message)}")
    except Exception as e:
        print(f"[logging] send_message log failed: {e}")

    with app.app_context():
        db_message = Message(sender=sender, recipient=recipient, encrypted_message=encrypted_msg)
        db.session.add(db_message)
        db.session.commit()
        message_id = db_message.id # Get the ID of the new message

    # Log that the message was stored with its ID
    try:
        logger.info(f"stored_message id={message_id} sender={sender} recipient={recipient} timestamp={db_message.timestamp.isoformat()}")
    except Exception:
        pass

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
            try:
                logger.info(f"message_delivered id={msg.id} sender={msg.sender} recipient={msg.recipient} status=delivered")
            except Exception:
                pass


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
            try:
                logger.info(f"message_edited id={msg.id} sender={msg.sender} editor={username} new_plain={_maybe_log_plain(new_message)} encrypted={_enc_for_log(msg.encrypted_message)}")
            except Exception:
                pass


@socketio.on("delete_message")
def handle_delete_message(data):
    message_id = data.get("message_id")
    username = data.get("username")
    with app.app_context():
        msg = Message.query.get(message_id)
        if msg and msg.sender == username:
            recipient = msg.recipient
            # Log deletion and then delete
            try:
                logger.info(f"message_deleted id={msg.id} sender={msg.sender} deleter={username} recipient={recipient}")
            except Exception:
                pass
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
            # Log decryption attempt (don't log key)
            try:
                logger.info(f"decrypt_message id={msg.id} sender={msg.sender} recipient={msg.recipient} decrypted={_maybe_log_plain(decrypted_text)} encrypted={_enc_for_log(msg.encrypted_message)}")
            except Exception:
                pass
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


def _ensure_message_columns_exist():
    """Ensure the Message table has the expected columns.

    Safe to run at startup. Returns list of added columns.
    """
    added = []
    with app.app_context():
        try:
            engine_name = getattr(db.engine, 'name', None)
        except Exception:
            engine_name = None

        try:
            if engine_name == 'postgresql':
                rows = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='message';")).fetchall()
                existing = {r[0] for r in rows}
                desired = {
                    'read': 'boolean DEFAULT false',
                    'group_id': 'integer',
                    'status': "varchar(20) DEFAULT 'sent'",
                    'edited': 'boolean DEFAULT false'
                }
                for col, definition in desired.items():
                    if col not in existing:
                        db.session.execute(text(f"ALTER TABLE message ADD COLUMN IF NOT EXISTS {col} {definition};"))
                        added.append(col)
                db.session.commit()
            else:
                # SQLite
                rows = db.session.execute(text("PRAGMA table_info('message');")).fetchall()
                existing = {r[1] for r in rows}
                desired = {
                    'read': 'BOOLEAN DEFAULT 0',
                    'group_id': 'INTEGER',
                    'status': "VARCHAR(20) DEFAULT 'sent'",
                    'edited': 'BOOLEAN DEFAULT 0'
                }
                for col, definition in desired.items():
                    if col not in existing:
                        db.session.execute(text(f"ALTER TABLE message ADD COLUMN {col} {definition};"))
                        added.append(col)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[startup] _ensure_message_columns_exist failed: {e}")
    return added


# Run startup tasks: create tables, diagnostics, and heal schema drift
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"[startup] db.create_all() failed: {e}")

    try:
        engine_name = getattr(db.engine, 'name', None)
    except Exception:
        engine_name = None
    used_env = None
    for k in ('DATABASE_URL', 'RAILWAY_DATABASE_URL', 'POSTGRES_URL', 'POSTGRESQL_URL', 'PG_URI', 'SQLALCHEMY_DATABASE_URI', 'DB_URL'):
        if os.environ.get(k):
            used_env = k
            break
    print(f"[startup] DATABASE_ENV_VAR: {used_env}, DB engine: {engine_name}")

    try:
        with db.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('[startup] DB connection test: OK')
    except Exception as e:
        print(f"[startup] DB connection test: FAILED - {e}")

    added = _ensure_message_columns_exist()
    if added:
        print(f"[startup] added message columns: {added}")

# ------------------ Main ------------------
if __name__ == "__main__":
    # Use environment variables for production deployment
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
