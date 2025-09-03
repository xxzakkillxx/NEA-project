import json
import socket
import threading

chat_messages = []

def receive_messages(sock, username):
    buffer = ""
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                break

            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue

                print(f"[DEBUG] Raw received: {line}")
                try:
                    message = json.loads(line)
                    if message.get("action") == "chat":
                        sender = message.get("username", "Unknown")
                        content = message.get("content", "")
                        sender_display = "You" if sender == username else sender
                        display_message = f"{sender_display}: {content}"
                        print(display_message)
                        chat_messages.append(display_message)
                    else:
                        continue
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Invalid JSON: {e} -> {line}")

        except Exception as e:
            print(f"[ERROR receiving message]: {e}")
            break


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