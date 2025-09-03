import socket
import threading
import json
import sqlite3
import hashlib
import os

HOST = '0.0.0.0'
PORT = 50007
DB_PATH = 'game_data.db'

clients = []

def user_exists(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

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
        username = message.get("username", "Unknown")  # Get the username from the message
        print(f"[CHAT] {username}: {content}")
        broadcast_msg = json.dumps({
            "action": "chat",
            "username": username,
            "content": content
        })
        for client in clients:
            if client != sender_conn:
                try:
                    client.sendall(broadcast_msg.encode())
                except Exception as e:
                    print(f"[ERROR] Failed to send to client: {e}")
        # ✅ Also send it back to the sender so they see their own message
        try:
            sender_conn.sendall(broadcast_msg.encode())
        except Exception as e:
            print(f"[ERROR] Failed to send to sender: {e}")
        return {"status": "success", "message": "Message sent"}
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
            conn.sendall(json.dumps(response).encode())

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