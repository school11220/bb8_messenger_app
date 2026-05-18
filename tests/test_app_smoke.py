import os
import tempfile
import uuid

db_file = os.path.join(tempfile.gettempdir(), f"bb8_test_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
os.environ["LOG_TO_FILE"] = "0"
os.environ.setdefault("SECRET_KEY", "test-secret")

import app as app_module  # noqa: E402


app = app_module.app
db = app_module.db
socketio = app_module.socketio


def _register(http_client, username, password="secret123"):
    response = http_client.post("/register", json={"username": username, "password": password})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    return payload


def test_health_and_auth_flow():
    client = app.test_client()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    username = f"user_{uuid.uuid4().hex[:8]}"
    _register(client, username)

    login = client.post("/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200
    assert login.get_json()["success"] is True

    session_check = client.get("/check_session")
    assert session_check.get_json() == {"logged_in": True, "username": username}


def test_direct_message_history_edit_delete_flow():
    client = app.test_client()
    alice = f"alice_{uuid.uuid4().hex[:8]}"
    bob = f"bob_{uuid.uuid4().hex[:8]}"
    _register(client, alice)
    _register(client, bob)

    alice_socket = socketio.test_client(app)
    bob_socket = socketio.test_client(app)
    assert alice_socket.is_connected()
    assert bob_socket.is_connected()

    alice_socket.emit("register_user", alice)
    bob_socket.emit("register_user", bob)
    alice_socket.emit("send_message", {"sender": alice, "recipient": bob, "message": "hello bob"})

    bob_events = bob_socket.get_received()
    received = [event for event in bob_events if event["name"] == "receive_message"]
    assert received
    message = received[-1]["args"][0]
    assert message["sender"] == alice
    assert message["message"] == "hello bob"

    alice_socket.emit("edit_message", {"message_id": message["id"], "editor": alice, "new_text": "hello again"})
    bob_events = bob_socket.get_received()
    edited = [event for event in bob_events if event["name"] == "message_edited"]
    assert edited
    assert edited[-1]["args"][0]["new_text"] == "hello again"

    bob_socket.emit("get_history", {"user1": bob, "user2": alice})
    history_events = [event for event in bob_socket.get_received() if event["name"] == "chat_history"]
    assert history_events
    history = history_events[-1]["args"][0]["history"]
    assert history[-1]["message"] == "hello again"

    alice_socket.emit("delete_message", {"message_id": message["id"], "deleter": alice, "delete_for_everyone": True})
    bob_events = bob_socket.get_received()
    deleted = [event for event in bob_events if event["name"] == "message_deleted"]
    assert deleted
    assert deleted[-1]["args"][0]["delete_for_everyone"] is True

    alice_socket.disconnect()
    bob_socket.disconnect()


def test_group_creation_and_group_message_flow():
    client = app.test_client()
    alice = f"alice_{uuid.uuid4().hex[:8]}"
    bob = f"bob_{uuid.uuid4().hex[:8]}"
    group_name = f"group_{uuid.uuid4().hex[:8]}"
    _register(client, alice)
    _register(client, bob)

    alice_socket = socketio.test_client(app)
    bob_socket = socketio.test_client(app)
    alice_socket.emit("register_user", alice)
    bob_socket.emit("register_user", bob)

    alice_socket.emit("create_group", {"creator": alice, "name": group_name, "members": [bob]})
    created = [event for event in alice_socket.get_received() if event["name"] == "group_created"]
    assert created
    assert created[-1]["args"][0]["name"] == group_name
    assert set(created[-1]["args"][0]["members"]) == {alice, bob}

    alice_socket.emit("get_user_groups", {"username": alice})
    groups_events = [event for event in alice_socket.get_received() if event["name"] == "user_groups"]
    assert groups_events
    groups = groups_events[-1]["args"][0]["groups"]
    group = next(group for group in groups if group["name"] == group_name)
    assert group["id"]
    assert set(group["members"]) == {alice, bob}

    alice_socket.emit(
        "send_group_message",
        {"sender": alice, "group_name": group_name, "message": "hello group", "message_type": "text"},
    )
    bob_events = bob_socket.get_received()
    group_messages = [event for event in bob_events if event["name"] == "group_message"]
    assert group_messages
    assert group_messages[-1]["args"][0]["message"] == "hello group"
    assert group_messages[-1]["args"][0]["group_id"] == group["id"]

    bob_socket.emit("get_group_history", {"group_name": group_name, "username": bob})
    history_events = [event for event in bob_socket.get_received() if event["name"] == "group_history"]
    assert history_events
    assert history_events[-1]["args"][0]["history"][-1]["message"] == "hello group"

    alice_socket.disconnect()
    bob_socket.disconnect()


def teardown_module():
    with app.app_context():
        db.session.remove()
        db.drop_all()
    if os.path.exists(db_file):
        os.remove(db_file)
