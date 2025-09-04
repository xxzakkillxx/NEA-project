import socket
import threading
import json
import sqlite3
import hashlib
import os
import datetime

HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', 50007))  # <-- dynamical port
DB_PATH = 'game_data.db'

clients = []

def log_action_to_database(username, message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO admin_logs (username, message, timestamp) VALUES (?, ?, ?)", (username, message, timestamp))
    conn.commit()
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, salt FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if result:
        stored_password, stored_salt = result
        salted_input = password + stored_salt
        hashed_input = hashlib.sha256(salted_input.encode()).hexdigest()
        return hashed_input == stored_password
    return False

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
        if verify_user(username, password):
            print(f"[LOGIN_SUCCESS] {username}")
            return {"status": "success", "message": "Login successful"}
        else:
            print(f"[LOGIN_FAILED] {username}")
            return {"status": "error", "message": "Invalid credentials"}
    elif action == "fetch_admin_logs":
        logs = fetch_logs_from_database()
        return {"status": "success", "logs": logs}

    elif action == "signup":
        username = message.get("username", "")
        password = message.get("password", "")
        print(f"[SIGNUP_ATTEMPT] {username}")
        if check_user_exists(username):
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

    elif action == "get_user_role":
        username = message.get("username")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        return {"role": result[0] if result else "user"}

    elif action == "log_action":
        username = message.get("username")
        msg = message.get("message", "")
        log_action_to_database(username, msg)
        return {"status": "success"}


    # ------------------------------------------------------

    else:
        print(f"[WARN] Unknown action: {action}")
        return {"status": "error", "message": "Unknown action"}

def handle_client_request(client_socket):
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                break
            request = json.loads(data.decode())

            response = process_request(request, client_socket)
            client_socket.sendall((json.dumps(response) + "\n").encode())

        except Exception as e:
            print(f"[ERROR] Failed to handle request: {e}")
            break
def fetch_logs_from_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC")
    logs = cursor.fetchall()
    conn.close()
    return logs

def check_user_exists(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_user_role(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return row[0]

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[STARTED] Server listening on {HOST}:{PORT}")

    while True:
        client_socket, addr = server.accept()
        print(f"[CONNECTED] Client connected from {addr}")
        clients.append(client_socket)

        thread = threading.Thread(target=handle_client_request, args=(client_socket,))
        thread.start()


if __name__ == "__main__":
    main()