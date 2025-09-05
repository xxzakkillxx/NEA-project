import socket
import threading
import json
import sqlite3
import hashlib
import os

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 50007))  # <-- dynamical port
DB_PATH = 'game_data.db'

clients = []

def authenticate_user(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get stored hash and salt for this user
    cursor.execute("SELECT password, salt FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        # User not found
        return False

    stored_hash, salt = row

    # Recreate the salted hash from the password provided and stored salt
    salted_password = password + salt
    hashed_password = hashlib.sha256(salted_password.encode()).hexdigest()

    # Compare hashes
    return hashed_password == stored_hash

def user_exists(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

#def verify_user(username, password):
#    conn = sqlite3.connect(DB_PATH)
#    cursor = conn.cursor()
#    cursor.execute("SELECT password, salt FROM users WHERE username = ?", (username,))
#    result = cursor.fetchone()
#    conn.close()
#
#    if result:
#        stored_password, stored_salt = result
#        salted_input = password + stored_salt
#        hashed_input = hashlib.sha256(salted_input.encode()).hexdigest()
#        return hashed_input == stored_password
#    return False

def create_user(username, password, role="user"):
    salt = os.urandom(16).hex()  # Generate a 16-byte random salt
    salted_password = password + salt
    hashed_password = hashlib.sha256(salted_password.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, salt TEXT, role TEXT)")
    cursor.execute("INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)", (username, hashed_password, salt, role))

    conn.commit()
    conn.close()

# ----------- New helper functions for admin user management -----------

def check_is_admin(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    print(f"[DEBUG] check_is_admin: user={username}, role={result}")
    return result is not None and result[0] == "admin"

def fetch_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    conn.close()
    # Return list of dicts without sensitive info
    return [{"username": u[0], "role": u[1]} for u in users]

def update_user(target_username, new_password=None, new_role=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if new_password:
        salt = os.urandom(16).hex()
        hashed_password = hashlib.sha256((new_password + salt).encode()).hexdigest()
        cursor.execute("UPDATE users SET password = ?, salt = ? WHERE username = ?", (hashed_password, salt, target_username))
    if new_role:
        cursor.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, target_username))
    conn.commit()
    conn.close()

def delete_user(target_username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (target_username,))
    conn.commit()
    conn.close()

# -----------------------------------------------------------------------

def process_request(message, sender_conn=None):
    action = message.get("action")

    if action == "login":
        username = message.get("username", "")
        password = message.get("password", "")
        print(f"[LOGIN ATTEMPT] {username}")
        if authenticate_user(username, password):
            print(f"[LOGIN_SUCCESS] {username}")
            return {"status": "success", "message": "Login successful"}
        else:
            print(f"[LOGIN_FAILED] {username}")
            return {"status": "error", "message": "Invalid credentials"}

    elif action == "signup":
        username = message.get("username", "")
        password = message.get("password", "")
        print(f"[SIGNUP_ATTEMPT] {username}")
        if user_exists(username):
            return {"status": "error", "message": "Username already exists"}
        else:
            create_user(username, password)
            print(f"[SIGNUP_SUCCESS] {username}")
            return {"status": "success", "message": "Signup successful"}

    elif action == "chat":
        content = message.get("content", "")
        username = message.get("username", "Unknown")
        print(f"[CHAT] {username}: {content}")
        broadcast_msg = json.dumps({
            "action": "chat",
            "username": username,
            "content": content
        })
        for client in clients:
            if client != sender_conn:
                try:
                    client.sendall((broadcast_msg + "\n").encode())
                except Exception as e:
                    print(f"[ERROR] Failed to send to client: {e}")
        try:
            sender_conn.sendall((broadcast_msg + "\n").encode())
        except Exception as e:
            print(f"[ERROR] Failed to send to sender: {e}")
        return {"status": "success", "message": "Message sent"}

    # --------- New admin management actions ---------

    elif action == "fetch_users":
        requesting_user = message.get("username", "")
        if not check_is_admin(requesting_user):
            return {"status": "error", "message": "Admin privileges required"}
        users = fetch_all_users()
        return {"status": "success", "users": users}

    elif action == "get_logs":
        requesting_user = message.get("username", "")
        if not check_is_admin(requesting_user):
            return {"status": "error", "message": "Admin privileges required"}
        # Fetch logs from the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 50")
        logs = cursor.fetchall()
        conn.close()
        log_entries = [
            {"username": row[0], "action": row[1], "timestamp": row[2]} for row in logs
        ]
        return {
            "action": "admin_logs",
            "status": "success",
            "logs": log_entries
        }

    elif action == "update_user":
        requesting_user = message.get("username", "")
        if not check_is_admin(requesting_user):
            return {"status": "error", "message": "Admin privileges required"}

        target_user = message.get("target_username")
        new_password = message.get("new_password", None)
        new_role = message.get("new_role", None)

        if not target_user:
            return {"status": "error", "message": "Target username required"}

        if not (new_password or new_role):
            return {"status": "error", "message": "Nothing to update"}

        update_user(target_user, new_password, new_role)
        return {"status": "success", "message": f"User {target_user} updated"}

    elif action == "delete_user":
        requesting_user = message.get("username", "")
        if not check_is_admin(requesting_user):
            return {"status": "error", "message": "Admin privileges required"}

        target_user = message.get("target_username")
        if not target_user:
            return {"status": "error", "message": "Target username required"}

        delete_user(target_user)
        return {"status": "success", "message": f"User {target_user} deleted"}

    # ------------------------------------------------------

    else:
        print(f"[WARN] Unknown action: {action}")
        return {"status": "error", "message": "Unknown action"}

def handle_client(conn, addr):
    print(f"New connection from {addr}")
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            try:
                message = json.loads(data.decode())
            except json.JSONDecodeError:
                print(f"[WARN] Invalid JSON from {addr}: {data!r}")
                continue

            response = process_request(message, sender_conn=conn)
            print(f"[DEBUG SEND]: {json.dumps(response)[:50]}... (truncated)")
            conn.sendall((json.dumps(response) + "\n").encode())

        except Exception as e:
            print(f"[ERROR] with {addr}: {e}")
            break

    print(f"Connection closed from {addr}")
    conn.close()
    if conn in clients:
        clients.remove(conn)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        conn, addr = s.accept()
        clients.append(conn)
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()