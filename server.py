import socket
import threading
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import bcrypt
import logging
import os
import time
import pytz

TIME_OFFSET_HOURS = 1

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_id = os.environ.get('RAILWAY_APP_ID')

if not app_id:
    raise ValueError("RAILWAY_APP_ID environment variable is not set. This is required for correct database pathing.")

try:
    key_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')

    if not key_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable is not set.")

    cred = credentials.Certificate(json.loads(key_json))
    firebase_admin.initialize_app(cred)
    logging.info("Firebase app initialized successfully from environment variable.")
    db = firestore.client()
except Exception as e:
    logging.error(f"Failed to initialize Firebase app: {e}")
    db = None

clients = []
clients_lock = threading.Lock()

players_in_game = {}
players_in_game_lock = threading.Lock()

user_timezones = {}
user_timezones_lock = threading.Lock()


def broadcast_message(message):
    encoded_message = (json.dumps(message) + '\n').encode('utf-8')
    with clients_lock:
        disconnected_clients = []
        for client_socket in clients:
            try:
                client_socket.sendall(encoded_message)
            except Exception as e:
                logging.error(f"Error broadcasting message to client: {e}")
                disconnected_clients.append(client_socket)
        for client in disconnected_clients:
            clients.remove(client)


def broadcast_updated_user_list():
    try:
        users = get_all_users_from_db(app_id)
        response = {"action": "all_users", "users": users}
        broadcast_message(response)
    except Exception as e:
        logging.error(f"Error broadcasting user list: {e}")


def add_user_to_db(username, password, role="user"):
    if not db:
        return False, "Database not connected."
    path = f"artifacts/{app_id}/public/data/users"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        user_ref = db.collection(path).document(username)
        user_ref.set({
            'username': username,
            'password': hashed_password,
            'role': role
        })
        log_action(app_id, username, "signup", f"User '{username}' created.")
        return True, "User created successfully."
    except Exception as e:
        logging.error(f"Error adding user to database: {e}")
        return False, "Failed to create user."


def get_user_from_db(app_id, username):
    if not db:
        return None
    try:
        path = f"artifacts/{app_id}/public/data/users"
        user_ref = db.collection(path).document(username)
        user_doc = user_ref.get()
        if user_doc.exists:
            return user_doc.to_dict()
        else:
            return None
    except Exception as e:
        logging.error(f"Error getting user from database: {e}")
        return None


def get_all_users_from_db(app_id):
    if not db:
        return []
    try:
        users_ref = db.collection(f"artifacts/{app_id}/public/data/users")
        users = users_ref.stream()
        return [(user.get('username'), user.get('role')) for user in users]
    except Exception as e:
        logging.error(f"Error getting all users from database: {e}")
        return []


def update_user_in_db(app_id, target_username, new_password=None, new_role=None):
    if not db:
        return False, "Database not connected."
    path = f"artifacts/{app_id}/public/data/users"
    try:
        user_ref = db.collection(path).document(target_username)
        update_data = {}
        if new_password:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_data['password'] = hashed_password
        if new_role:
            update_data['role'] = new_role

        user_ref.set(update_data, merge=True)
        log_action(app_id, "server", "update_user", f"Admin updated user '{target_username}'.")
        return True, "User updated successfully."
    except Exception as e:
        logging.error(f"Error updating user: {e}")
        return False, "Failed to update user."


def delete_user_from_db(app_id, target_username):
    if not db:
        return False, "Database not connected."
    path = f"artifacts/{app_id}/public/data/users"
    try:
        db.collection(path).document(target_username).delete()
        log_action(app_id, "server", "delete_user", f"Admin deleted user '{target_username}'.")
        return True, "User deleted successfully."
    except Exception as e:
        logging.error(f"Error deleting user: {e}")
        return False, "Failed to delete user."


def log_action(app_id, username, action, message):
    if not db:
        return
    path = f"artifacts/{app_id}/public/data/logs"
    try:
        log_ref = db.collection(path).document()
        log_ref.set({
            'username': username,
            'action': action,
            'message': message,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        logging.error(f"Error writing log to database: {e}")


def get_admin_logs(app_id, user_tz_name):
    if not db:
        return []
    path = f"artifacts/{app_id}/public/data/logs"
    try:
        logs_ref = db.collection(path).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100)
        logs = logs_ref.stream()
        log_list = []
        user_timezone = pytz.timezone(user_tz_name)

        offset_timedelta = timedelta(hours=TIME_OFFSET_HOURS)

        for log in logs:
            log_data = log.to_dict()
            if isinstance(log_data.get('timestamp'), datetime):
                utc_dt = log_data['timestamp'].replace(tzinfo=pytz.utc) + offset_timedelta
                local_dt = utc_dt.astimezone(user_timezone)
                log_data['timestamp'] = local_dt.strftime("%Y-%m-%d %H:%M:%S")
            log_list.append(log_data)
        return log_list
    except Exception as e:
        logging.error(f"Error getting admin logs: {e}")
        return []


def handle_client(conn, addr):
    logging.info(f"Connected by {addr}")
    with clients_lock:
        clients.append(conn)

    current_username = None

    try:
        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data:
                break
            requests = data.split('\n')
            for req in requests:
                if not req:
                    continue
                try:
                    message = json.loads(req)
                    action = message.get("action")
                    username = message.get("username")

                    if username:
                        current_username = username

                    if action == "signup":
                        password = message.get("password")
                        success, msg = add_user_to_db(username, password)
                        response = {"action": "signup_result", "status": "success" if success else "error",
                                    "message": msg}
                        conn.sendall(json.dumps(response).encode() + b'\n')
                        if success:
                            time.sleep(0.5)
                            broadcast_updated_user_list()
                    elif action == "login":
                        password = message.get("password")
                        user_data = get_user_from_db(app_id, username)
                        if user_data and bcrypt.checkpw(password.encode('utf-8'),
                                                        user_data['password'].encode('utf-8')):
                            log_action(app_id, username, "login", "User logged in.")
                            response = {"action": "login_result", "status": "success", "username": username,
                                        "role": user_data['role']}
                        else:
                            log_action(app_id, username, "failed_login", "Failed login attempt.")
                            response = {"action": "login_result", "status": "error",
                                        "message": "Invalid username or password."}
                        conn.sendall(json.dumps(response).encode() + b'\n')
                    elif action == "update_timezone":
                        user_tz = message.get("timezone")
                        if current_username and user_tz:
                            with user_timezones_lock:
                                user_timezones[current_username] = user_tz
                            logging.info(f"Stored timezone for {current_username}: {user_tz}")
                            response = {"action": "timezone_updated", "status": "success"}
                            conn.sendall(json.dumps(response).encode() + b'\n')

                    elif action == "get_all_users":
                        request_username = message.get("username")
                        user_data = get_user_from_db(app_id, request_username)
                        if user_data and user_data.get('role') == 'admin':
                            users = get_all_users_from_db(app_id)
                            response = {"action": "all_users", "users": users}
                        else:
                            response = {"action": "all_users", "users": [], "message": "Access denied."}
                        conn.sendall(json.dumps(response).encode() + b'\n')
                    elif action == "update_user":
                        target_username = message.get('target_username')
                        new_password = message.get('new_password')
                        new_role = message.get('new_role')
                        user_data = get_user_from_db(app_id, username)
                        if user_data and user_data.get('role') == 'admin':
                            success, msg = update_user_in_db(app_id, target_username, new_password, new_role)
                            response = {"action": "update_user_result", "status": "success" if success else "error",
                                        "message": msg}
                            conn.sendall(json.dumps(response).encode() + b'\n')
                            if success:
                                time.sleep(0.5)
                                broadcast_updated_user_list()
                        else:
                            response = {"action": "update_user_result", "status": "error", "message": "Access denied."}
                            conn.sendall(json.dumps(response).encode() + b'\n')
                    elif action == "delete_user":
                        target_username = message.get('target_username')
                        user_data = get_user_from_db(app_id, username)
                        if user_data and user_data.get('role') == 'admin':
                            success, msg = delete_user_from_db(app_id, target_username)
                            response = {"action": "delete_user_result", "status": "success" if success else "error",
                                        "message": msg}
                            conn.sendall(json.dumps(response).encode() + b'\n')
                            if success:
                                time.sleep(0.5)
                                broadcast_updated_user_list()
                        else:
                            response = {"action": "delete_user_result", "status": "error", "message": "Access denied."}
                            conn.sendall(json.dumps(response).encode() + b'\n')
                    elif action == "get_logs":
                        user_data = get_user_from_db(app_id, username)
                        if user_data and user_data.get('role') == 'admin':
                            with user_timezones_lock:
                                user_tz_name = user_timezones.get(username, 'UTC')
                            logs = get_admin_logs(app_id, user_tz_name)
                            response = {"action": "admin_logs", "logs": logs}
                        else:
                            response = {"action": "admin_logs", "logs": [], "message": "Access denied."}
                        conn.sendall(json.dumps(response).encode() + b'\n')
                    elif action == "chat":
                        content = message.get("content")
                        if content:
                            log_action(app_id, username, "chat", content)
                            broadcast_message({"action": "chat", "username": username, "content": content})
                    elif action == "join_game":
                        player_id = message.get("player_id")  # Use player ID for game state management
                        if current_username:
                            with players_in_game_lock:
                                players_in_game[current_username] = {
                                    "position": [375, 550],  # Default start position
                                    "character_class": message.get("character_class"),
                                    "character_skill": message.get("character_skill")
                                }
                                # Notify all clients of the new player
                                broadcast_message({
                                    "action": "player_joined",
                                    "username": current_username,
                                    "players": players_in_game
                                })
                                logging.info(
                                    f"User {current_username} joined the game. Total players: {len(players_in_game)}")

                    elif action == "move_player":
                        position = message.get("position")
                        if current_username and position:
                            with players_in_game_lock:
                                if current_username in players_in_game:
                                    players_in_game[current_username]["position"] = position
                                    # Broadcast the updated position to all other clients
                                    broadcast_message({
                                        "action": "player_moved",
                                        "username": current_username,
                                        "position": position
                                    })

                    elif action == "player_leave":
                        if current_username:
                            with players_in_game_lock:
                                if current_username in players_in_game:
                                    del players_in_game[current_username]
                                    broadcast_message({
                                        "action": "player_left",
                                        "username": current_username
                                    })
                                    logging.info(
                                        f"User {current_username} left the game. Total players: {len(players_in_game)}")

                    elif action == "move_player":
                        position = message.get("position")
                        if current_username and position:
                            with players_in_game_lock:
                                if current_username in players_in_game:
                                    players_in_game[current_username]["position"] = position
                                    # Correct way to broadcast the update
                                    broadcast_message({
                                        "action": "player_moved",
                                        "username": current_username,
                                        "position": position
                                    })
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode JSON from client: {e}")
    except Exception as e:
        logging.error(f"Error in client handler for {addr}: {e}")
    finally:
        logging.info(f"Client {addr} disconnected.")
        if current_username:
            with players_in_game_lock:
                if current_username in players_in_game:
                    del players_in_game[current_username]
                    broadcast_message({
                        "action": "player_left",
                        "username": current_username
                    })
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()


def main():
    global clients

    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 50007))
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    logging.info(f"Server listening on {HOST}:{PORT}")
    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()