



#def receive_messages():
#    while True:
#        try:
#            message = client_socket.recv(1024).decode('utf-8')
#            if message:
#                print(f"Received from server: {message}")  # Debug print
#                try:
#                    data = json.loads(message)
#                    chat_text = data.get("content", "")
#                    chat_messages.append(chat_text)
#                except json.JSONDecodeError:
#                    chat_messages.append(message)
#            else:
#                print("Server closed the connection.")
#                break
#        except Exception as e:
#            print(f"Error receiving message: {e}")
#            break
