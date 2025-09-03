import socket
import threading
import json

client_socket = None
receive_thread = None
chat_messages = []
client_connected = False

def start_client_connection():
    global client_socket, receive_thread, client_connected
    if client_connected:
        print("[DEBUG] Client is already connected to server.")
        return

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('tramway.proxy.rlwy.net', 23620))
        print("[DEBUG] Connected to server at 'tramway.proxy.rlwy.net':23620")

        receive_thread = threading.Thread(target=receive_messages, daemon=True)
        receive_thread.start()

        client_connected = True
    except Exception as e:
        print(f"[ERROR] Failed to connect to server: {e}")
        client_connected = False

def send_chat_message(raw_text, username):
    if client_socket:
        message = json.dumps({
            "action": "chat",
            "username": username,
            "content": raw_text
        })
        print(f"Sending to server: {message}")  # Debug print
        try:
            client_socket.sendall(message.encode())
        except Exception as e:
            print(f"Failed to send message: {e}")

def receive_messages():
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if message:
                print(f"Received from server: {message}")  # Debug print
                try:
                    data = json.loads(message)
                    chat_text = data.get("content", "")
                    chat_messages.append(chat_text)
                except json.JSONDecodeError:
                    chat_messages.append(message)
            else:
                print("Server closed the connection.")
                break
        except Exception as e:
            print(f"Error receiving message: {e}")
            break
