import json
import socket
import threading

client_socket = None
receive_thread = None
chat_messages = []
client_connected = False
RECONNECT_DELAY = 3  # Initial delay (in seconds)
MAX_RECONNECT_DELAY = 30
running = True

def start_client_connection(username, password):
    import time
    global client_socket, receive_thread, client_connected, running, chat_messages

    SERVER_HOST = 'tramway.proxy.rlwy.net'
    SERVER_PORT = 23620
    RECONNECT_DELAY = 3
    MAX_RECONNECT_DELAY = 30

    reconnect_delay = RECONNECT_DELAY
    client_connected = False
    running = True
    first_connection = True  # ✅ Send login payload only once

    while running:
        try:
            if first_connection:
                chat_messages.append("🔌 Connecting to server...")
            else:
                chat_messages.append("🔁 Reconnecting to server...")

            print("[INFO] Connecting to server...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((SERVER_HOST, SERVER_PORT))
            print(f"[DEBUG] Connected to server at '{SERVER_HOST}':{SERVER_PORT}")

            client_connected = True
            reconnect_delay = RECONNECT_DELAY  # Reset delay after success

            chat_messages.append("✅ Connected to server.")

            if first_connection:
                try:
                    login_payload = json.dumps({
                        "action": "login",
                        "username": username,
                        "password": password
                        # Add "password": password if needed
                    })
                    client_socket.sendall(login_payload.encode())
                    first_connection = False  # ✅ Only send login once
                except Exception as login_error:
                    print(f"[ERROR] Failed to send login info: {login_error}")
                    chat_messages.append("❌ Failed to send login info.")

            receive_thread = threading.Thread(
                target=receive_messages,
                args=(client_socket, username),
                daemon=True
            )
            receive_thread.start()

            # ❌ DO NOT block with join() — it freezes UI
            # receive_thread.join()

            break  # ✅ Leave the loop after a successful connection

        except (ConnectionRefusedError, socket.error) as e:
            print(f"[ERROR] Failed to connect or lost connection: {e}")
            client_connected = False
            chat_messages.append("⚠️ Lost connection to server.")

        if not running:
            break

        chat_messages.append(f"🔁 Retrying in {reconnect_delay} seconds...")
        print(f"[INFO] Reconnecting in {reconnect_delay} seconds...")
        time.sleep(reconnect_delay)
        reconnect_delay = min(MAX_RECONNECT_DELAY, reconnect_delay * 2)

#start_client_connection(username)

def send_chat_message(raw_text, username):
    global client_socket
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
    else:
        print("[ERROR] Cannot send message - socket is not connected")


def receive_messages(client_socket, username):
    buffer = ""
    decoder = json.JSONDecoder()

    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break

            buffer += data

            while buffer:
                try:
                    # Try to decode a full JSON message from the buffer
                    message, index = decoder.raw_decode(buffer)
                    buffer = buffer[index:].lstrip()  # Remove parsed part + strip whitespace

                    # Debug print to verify message
                    print(f"[DECODED MESSAGE]: {message}")

                    if isinstance(message, dict) and message.get("action") == "chat":
                        sender = message.get("username", "Unknown")
                        content = message.get("content", "")

                        if sender == username:
                            display_message = f"You: {content}"
                        else:
                            display_message = f"{sender}: {content}"

                        print(display_message)
                        chat_messages.append(display_message)

                    # Ignore status messages silently or print if you want:
                    # else:
                    #     print(f"[OTHER MESSAGE]: {message}")

                except json.JSONDecodeError as e:
                    print(f"[PARTIAL BUFFER]: {buffer[:100]}")  # Show up to 100 chars of the buffer
                    print(f"[JSON ERROR]: {e}")
                    break

        except Exception as e:
            print(f"[ERROR receiving message]: {e}")
            break

def send_message(message: dict):
    """
    Send a dictionary message to the server via the socket connection.

    Args:
        message (dict): The message to send to the server.
    """
    global client_socket
    if client_socket is None:
        print("Error: socket is not connected")
        return

    try:
        serialized = json.dumps(message).encode('utf-8')
        client_socket.sendall(serialized)
        print(f"Sent message to server: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    HOST = 'tramway.proxy.rlwy.net'
    PORT = 23620

    username = input("Enter your username: ")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))

    # Start receiving thread, pass the socket and username
    threading.Thread(target=receive_messages, args=(s, username), daemon=True).start()

    while True:
        msg = input()
        if msg.strip() == "":
            continue
        # Include username in the message sent to server
        message = json.dumps({"action": "chat", "username": username, "content": msg})
        s.sendall(message.encode())

if __name__ == "__main__":
    main()