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

# --- Configuration ---
# You can set a manual time offset here if the automatic timezone conversion is incorrect.
TIME_OFFSET_HOURS = 1

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_id = os.environ.get('RAILWAY_APP_ID')

if not app_id:
    # This will crash the server immediately if the variable isn't set, which is what we want.
    raise ValueError("RAILWAY_APP_ID environment variable is not set. This is required for correct database pathing.")

# --- Firestore Setup ---
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

# Global list to store connected clients and a lock for thread-safe access
clients = []
clients_lock = threading.Lock()

# A new dictionary to store each user's timezone
user_timezones = {}
user_timezones_lock = threading.Lock()


# --- Broadcasting Functions ---
def broadcast_message(message):
    """Sends a message to all connected clients."""
    encoded_message = (json.dumps(message) + '\n').encode('utf-8')
    with clients_lock:
        disconnected_clients = []
        for client_socket in clients:
            try:
                client_socket.sendall(encoded_message)
            except Exception as e:
                logging.error(f"Error broadcasting message to client: {e}")
                disconnected_clients.append(client_socket)
        # Clean up disconnected clients
        for client in disconnected_clients:
            clients.remove(client)


def broadcast_updated_user_list():
    """Fetches all users and broadcasts the list to all clients."""
    try:
        users = get_all_users_from_db(app_id)
        response = {"action": "all_users", "users": users}
        broadcast_message(response)
    except Exception as e:
        logging.error(f"Error broadcasting user list: {e}")


# --- User and Log Management Functions (Using Firestore) ---
def add_user_to_db(username, password, role="user"):
    """Adds a new user to the Firestore 'users' collection."""
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
    """Retrieves a single user document from Firestore."""
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
    """Retrieves all users from the correct Firestore collection."""
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
    """Updates a user's password or role in Firestore using a merge operation."""
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
    """Deletes a user from the Firestore 'users' collection."""
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
    """Adds a log entry to the Firestore 'logs' collection."""
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
    """
    Retrieves and converts log timestamps to the user's specific timezone, with an optional offset.
    """
    if not db:
        return []
    path = f"artifacts/{app_id}/public/data/logs"
    try:
        logs_ref = db.collection(path).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100)
        logs = logs_ref.stream()
        log_list = []
        user_timezone = pytz.timezone(user_tz_name)

        # Define the offset
        offset_timedelta = timedelta(hours=TIME_OFFSET_HOURS)

        for log in logs:
            log_data = log.to_dict()
            if isinstance(log_data.get('timestamp'), datetime):
                # Apply the offset before conversion
                utc_dt = log_data['timestamp'].replace(tzinfo=pytz.utc) + offset_timedelta
                local_dt = utc_dt.astimezone(user_timezone)
                log_data['timestamp'] = local_dt.strftime("%Y-%m-%d %H:%M:%S")
            log_list.append(log_data)
        return log_list
    except Exception as e:
        logging.error(f"Error getting admin logs: {e}")
        return []


# --- Server Logic ---
def handle_client(conn, addr):
    """Handles a single client connection."""
    logging.info(f"Connected by {addr}")
    # Add client to the global list for broadcasting
    with clients_lock:
        clients.append(conn)

    current_username = None  # Track the current user for this connection

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
                            time.sleep(0.5)  # Allow Firestore to sync
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
                        # NEW ACTION: store the user's timezone on the server
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
                                time.sleep(0.5)  # Allow Firestore to sync
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
                        # MODIFIED: Get the user's timezone from our new dictionary
                        user_data = get_user_from_db(app_id, username)
                        if user_data and user_data.get('role') == 'admin':
                            with user_timezones_lock:
                                user_tz_name = user_timezones.get(username, 'UTC')  # Default to UTC
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
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode JSON from client: {e}")
    except Exception as e:
        logging.error(f"Error in client handler for {addr}: {e}")
    finally:
        logging.info(f"Client {addr} disconnected.")
        # Remove client from the global list
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()


def main():
    """Main function to start the server."""
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