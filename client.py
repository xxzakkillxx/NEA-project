import json
import socket
import threading

chat_messages = []

def receive_messages(sock, username):
    while True:
        try:
            message = sock.recv(1024).decode('utf-8')
            if message:
                data = json.loads(message)
                if data.get("action") == "chat":
                    sender = data.get("username", "Unknown")
                    content = data.get("content", "")

                    if sender == username:
                        display_message = f"You: {content}"
                    else:
                        display_message = f"{sender}: {content}"

                    print(display_message)
                    chat_messages.append(display_message)
                else:
                    # Handle other message types if needed
                    pass
            else:
                break
        except Exception as e:
            print(f"[ERROR receiving message]: {e}")
            break

def main():
    HOST = 'nea-project-production.up.railway.app'
    PORT = 50007

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