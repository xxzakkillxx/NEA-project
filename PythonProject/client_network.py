import socket
import threading
import json

client_socket = None
receive_thread = None
chat_messages = []

def start_client_connection():
    global client_socket, receive_thread
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('127.0.0.1', 50007))

    receive_thread = threading.Thread(target=receive_messages)
    receive_thread.daemon = True
    receive_thread.start()

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
            # Show your own message in chat
            chat_messages.append(f"You: {raw_text}")
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
