# New Features Documentation

## Overview
This document describes the newly implemented features: Enhanced Typing Indicators, Group Management with Admin Controls, and Multi-Device Sync.

---

## 1. Enhanced Typing Indicators

### Features
- **Multi-User Display**: Shows who is typing in real-time with smart formatting
  - 1 user: "Alice is typing"
  - 2 users: "Alice and Bob are typing"
  - 3 users: "Alice, Bob, and Charlie are typing"
  - 4+ users: "Alice, Bob, and 3 others are typing"

- **Group Support**: Works in both direct messages and group chats
- **Conversation Isolation**: Only shows typing for the currently active conversation
- **Auto-Timeout**: Typing indicator disappears after 2 seconds of inactivity

### How It Works
**Frontend (chat.js)**:
- `typingUsers` object tracks typing users per conversation
- `showTypingIndicator()` adds users to the typing set
- `hideTypingIndicator()` removes users from the typing set
- `updateTypingIndicatorDisplay()` renders the indicator with smart text formatting

**Backend (app.py)**:
- `handle_typing()`: Broadcasts typing event to all group members or direct recipient
- `handle_stop_typing()`: Broadcasts stop typing event
- Includes `group_id` or `recipient` for proper routing

### Usage
```javascript
// Send typing notification
socket.emit("typing", { 
    sender: username, 
    group_id: 123  // or recipient: "username" for DMs
});

// Stop typing
socket.emit("stop_typing", { 
    sender: username, 
    group_id: 123 
});
```

---

## 2. Group Management with Admin Controls

### Database Models

#### GroupAdmin
```python
- id: Primary key
- group_id: Foreign key to group
- user_id: Foreign key to user
- role: 'admin' or 'super_admin'
- can_add_members: Boolean permission
- can_remove_members: Boolean permission
- can_edit_group: Boolean permission
- can_send_messages: Boolean permission
- appointed_at: Timestamp
```

#### GroupInvitation
```python
- id: Primary key
- group_id: Foreign key to group
- invited_by: Foreign key to user
- invited_user: Username string
- invite_token: Unique token
- status: 'pending', 'accepted', 'rejected', 'expired'
- created_at: Timestamp
- expires_at: Expiration timestamp (7 days)
```

### Features

#### Admin Promotion/Demotion
- **Promote to Admin**: Only creator or super admins can promote members
- **Demote Admin**: Only creator or super admins can demote admins
- **Creator Protection**: Group creator cannot be demoted or removed

#### Member Management
- **Add Members**: Admins with `can_add_members` permission can add users
- **Remove Members**: Admins with `can_remove_members` permission can remove users
- **Real-time Notifications**: All group members notified of changes

#### Group Settings
- **Edit Group Name**: Admins with `can_edit_group` permission can rename group
- **View Admins**: List all admins with their roles and permissions
- **Member List**: View all group members with admin badges

#### Invitation System
- **Create Invitations**: Any group member can create invitation links
- **Token-Based**: Secure token with 7-day expiration
- **Accept/Reject**: Invited users can accept via token
- **Real-time Delivery**: Invitations sent via WebSocket if user is online

### Socket Events

#### Group Management
```javascript
// Promote user to admin
socket.emit("promote_to_admin", {
    group_id: 123,
    username: "user",
    promoter: "admin_user"
});

// Demote admin
socket.emit("demote_admin", {
    group_id: 123,
    username: "admin_user",
    demoter: "creator"
});

// Add member
socket.emit("add_group_member", {
    group_id: 123,
    username: "new_user",
    adder: "admin_user"
});

// Remove member
socket.emit("remove_group_member", {
    group_id: 123,
    username: "user",
    remover: "admin_user"
});

// Edit group name
socket.emit("edit_group", {
    group_id: 123,
    new_name: "New Group Name",
    editor: "admin_user"
});

// Get admins list
socket.emit("get_group_admins", {
    group_id: 123
});
```

#### Invitations
```javascript
// Create invitation
socket.emit("create_group_invitation", {
    group_id: 123,
    inviter: "username",
    invited_user: "invitee"
});

// Accept invitation
socket.emit("accept_group_invitation", {
    invite_token: "abc123...",
    username: "invitee"
});
```

### UI Components
- **Group Settings Modal**: Accessible via gear icon in group chat header
  - Group name editor
  - Member list with remove buttons
  - Add member dropdown
  - Admin list with promote/demote controls
  - Invitation creator

---

## 3. Multi-Device Sync

### Database Models

#### DeviceSession
```python
- id: Primary key
- user_id: Foreign key to user
- device_token: Unique token (255 chars)
- device_name: Display name (e.g., "iPhone", "Desktop")
- device_type: 'web', 'mobile', 'desktop'
- ip_address: Last known IP
- last_active: Last activity timestamp
- is_active: Boolean flag
- created_at: Creation timestamp
```

### Features

#### QR Code Pairing
- **Generate QR**: Primary device generates time-limited QR code (5 min expiry)
- **Scan QR**: Secondary device scans and verifies token
- **Automatic Linking**: Devices linked upon successful verification
- **Real-time Notification**: Both devices notified of successful pairing

#### Device Management
- **List Devices**: View all linked devices with last active time
- **Remove Device**: Deactivate specific devices
- **Device Info**: Shows device name, type, and activity status

#### Message Synchronization
- **Cross-Device Messaging**: Messages broadcasted to all user's active devices
- **History Sync**: New devices can sync message history
- **Timestamp-Based**: Sync messages since last sync timestamp

### Security
- **Token Expiration**: Pairing tokens expire after 5 minutes
- **Unique Tokens**: Each device gets unique 32-byte token
- **Session Tracking**: Track device activity and IP addresses
- **Manual Removal**: Users can remove suspicious devices

### Socket Events

#### Device Management
```javascript
// Generate QR code for pairing
socket.emit("generate_qr_code", {
    username: "username"
});

// Verify QR code from secondary device
socket.emit("verify_qr_code", {
    token: "pairing_token",
    device_name: "My Phone",
    device_type: "mobile"
});

// Get list of devices
socket.emit("get_devices", {
    username: "username"
});

// Remove device
socket.emit("remove_device", {
    device_id: 123,
    username: "username"
});

// Sync messages
socket.emit("sync_messages", {
    username: "username",
    last_sync: "2024-01-01T00:00:00Z"  // ISO timestamp
});
```

#### Received Events
```javascript
// QR code generated
socket.on("qr_code_generated", data => {
    // data.token: Pairing token
    // data.expires_in: Seconds until expiration
});

// Device successfully paired
socket.on("device_paired", data => {
    // data.device_name, data.device_type, data.paired_at
});

// New device paired (notification to primary)
socket.on("new_device_paired", data => {
    // data.device_name, data.device_type
});

// Devices list
socket.on("devices_list", data => {
    // data.devices: Array of device objects
});

// Messages synced
socket.on("messages_synced", data => {
    // data.messages: Array of message objects
    // data.sync_timestamp: Latest sync time
});
```

### UI Components
- **Multi-Device Modal**: Accessible from Settings → "Manage Devices"
  - Linked devices list with last active time
  - QR code generator with countdown timer
  - Manual token input field
  - Remove device buttons

---

## Integration Guide

### Frontend Setup
1. The new features are automatically loaded when `chat.js` loads
2. Group settings button appears automatically when viewing group chats
3. Multi-device option added to settings modal automatically

### Backend Setup
1. Run migration: `python migrate_new_features.py`
2. New tables created: `group_admin`, `device_session`, `group_invitation`
3. Socket handlers registered automatically on server start

### Testing

#### Enhanced Typing
1. Open two browser windows with different users
2. Start typing in one window
3. Verify typing indicator appears in other window
4. Test in both DMs and group chats

#### Group Management
1. Create a group
2. Click gear icon in group chat header
3. Test promoting/demoting admins
4. Test adding/removing members
5. Test creating invitations

#### Multi-Device Sync
1. Open Settings → Manage Devices
2. Click "Generate QR Code"
3. Open new incognito window
4. Login and click "Scan QR Code"
5. Enter token manually or use QR scanner
6. Verify both devices show pairing success

---

## API Endpoints

### File Uploads (Existing)
- `POST /upload` - Upload files/media
- `POST /upload_voice` - Upload voice messages
- `POST /upload_avatar` - Upload profile pictures

### Health Check
- `GET /health` - Server health status

---

## Configuration

### Timeouts
- Typing indicator timeout: 2000ms (2 seconds)
- QR code expiration: 300s (5 minutes)
- Invitation expiration: 7 days

### Limits
- Max typing users displayed: 4 (rest shown as "X others")
- Device sessions: Unlimited per user
- Group admins: Unlimited per group

---

## Error Handling

### Common Errors
```javascript
socket.on("error", data => {
    // data.message contains error description
});
```

### Error Messages
- "Group not found"
- "No permission to [action]"
- "User not in group"
- "Invalid invitation"
- "Invitation expired"
- "Device not found"
- "Token expired"

---

## Production Considerations

### Database
- Add indexes on `group_id`, `user_id` in `group_admin`
- Add index on `device_token` in `device_session`
- Add index on `invite_token` in `group_invitation`

### Scaling
- Consider Redis for pairing token storage (currently in-memory)
- Implement cleanup job for expired invitations
- Add rate limiting for invitation creation

### Security
- Validate admin permissions on all group operations
- Sanitize group names and device names
- Implement CSRF protection for device pairing
- Add 2FA option for device pairing

---

## Future Enhancements

### Group Management
- Role templates (moderator, member, viewer)
- Permission granularity (pin messages, delete messages)
- Group icons/avatars
- Member join requests
- Invite link sharing (public links)

### Multi-Device
- QR code image generation (currently shows token)
- Push notification sync
- End-to-end encrypted device pairing
- Device trust levels
- Biometric authentication

### Typing Indicators
- Show typing location (in group X)
- Typing speed analytics
- Smart notification timing

---

## Troubleshooting

### Typing indicators not showing
- Check browser console for WebSocket errors
- Verify `typingUsers` object in console
- Ensure users are in same conversation

### Group settings not accessible
- Verify user is group member
- Check if gear icon appears in header
- Open browser console for errors

### Device pairing fails
- Check token hasn't expired (5 min limit)
- Verify both devices connected to server
- Check server logs for errors
- Ensure database migration ran successfully

### Messages not syncing
- Verify device session is active (`is_active = true`)
- Check `last_sync` timestamp is correct
- Ensure WebSocket connection established

---

## Code Reference

### Key Files
- `app.py`: Backend socket handlers (lines 1780-2425)
- `static/chat.js`: Frontend logic (lines 1-2000)
- `static/chat.html`: UI modals (lines 1202-1370)
- `migrate_new_features.py`: Database migration

### Database Schema
```sql
-- Group Admin
CREATE TABLE group_admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(20) DEFAULT 'admin',
    can_add_members BOOLEAN DEFAULT 1,
    can_remove_members BOOLEAN DEFAULT 1,
    can_edit_group BOOLEAN DEFAULT 1,
    can_send_messages BOOLEAN DEFAULT 1,
    appointed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Device Session
CREATE TABLE device_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_token VARCHAR(255) UNIQUE NOT NULL,
    device_name VARCHAR(100),
    device_type VARCHAR(50),
    ip_address VARCHAR(50),
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Group Invitation
CREATE TABLE group_invitation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    invited_by INTEGER NOT NULL,
    invited_user VARCHAR(100) NOT NULL,
    invite_token VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

---

## License & Credits
BB84 Messenger Application - Quantum-Inspired Secure Messaging
Enhanced with group management and multi-device capabilities.
