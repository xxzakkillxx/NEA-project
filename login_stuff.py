import pygame
import re
import socket
import queue
import json
import threading

screen_change_queue = queue.Queue()

pygame.init()
WIDTH, HEIGHT = 800, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Login & Signup System")
FONT = pygame.font.SysFont("arial", 24)
current_screen = "login"

client_socket = None
receive_thread = None
chat_messages = []
client_connected = False
RECONNECT_DELAY = 3  # Initial delay (in seconds)
MAX_RECONNECT_DELAY = 30
running = True
_message_handler = None

def start_client_connection():
    import time
    global client_socket, receive_thread, client_connected, running, chat_messages

    SERVER_HOST = 'tramway.proxy.rlwy.net'
    SERVER_PORT = 23620
    RECONNECT_DELAY = 3
    MAX_RECONNECT_DELAY = 30

    reconnect_delay = RECONNECT_DELAY
    client_connected = False
    running = True

    while running:
        try:
            print("[INFO] Connecting to server...")
            chat_messages.append("🔌 Connecting to server...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((SERVER_HOST, SERVER_PORT))
            print(f"[DEBUG] Connected to server at '{SERVER_HOST}':{SERVER_PORT}")

            client_connected = True
            reconnect_delay = RECONNECT_DELAY  # Reset delay after success

            chat_messages.append("✅ Connected to server.")

            receive_thread = threading.Thread(
                target=receive_messages,
                args=(client_socket,), # Removed username and logs_handler
                daemon=True
            )
            receive_thread.start()

            break  # Leave the loop after a successful connection

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


def receive_messages(client_socket):
    buffer = ""

    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break
            buffer += data
            lines = buffer.split('\n')
            buffer = lines.pop()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    message = json.loads(line)
                    print(f"[DECODED MESSAGE]: {message}")
                    if isinstance(message, dict):
                        # The single point of handling all messages is handle_server_response
                        handle_server_response(message)
                except json.JSONDecodeError as e:
                    print(f"[JSON ERROR]: {e}")
                    print(f"[LINE CAUSING ERROR]: {line}")
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

logs_cache = []

def request_admin_logs():
    if client_connected and client_socket:
        send_message({"action": "get_logs", "username": current_user})
    else:
        print("[ERROR] Cannot request logs — disconnected.")

def handle_server_response(response):
    global logs_cache, current_user, chat_messages, user_role, user_list_cache

    action = response.get("action")
    status = response.get("status")

    if action == "admin_logs":
        logs_cache = response.get("logs", [])
        print(f"[GUI] Logs cache updated with {len(logs_cache)} entries.")

    elif action == "login_result":
        if status == "success":
            current_user = response.get("username")
            user_role = response.get("role")
            if user_role == "admin":
                print(f"[SUCCESS] Login successful for admin: {current_user}")
                switch_screen("admin_panel")
            else:
                print(f"[SUCCESS] Login successful for user: {current_user}")
                switch_screen("welcome_screen")
        else:
            error_msg = response.get("message", "An unknown error occurred.")
            login_username.error = True
            login_username.error_msg = error_msg
            login_password.error = True
            login_password.error_msg = ""
            print(f"[ERROR] Login failed: {error_msg}")

    elif action == "signup_result":
        if status == "success":
            print("[CLIENT] Signup successful!")
            switch_screen("login")
        else:
            error_msg = response.get("message", "An unknown error occurred.")
            signup_username.error = True
            signup_username.error_msg = error_msg
            print(f"[ERROR] Signup failed: {error_msg}")

    elif action == "all_users":
        user_list_cache = response.get("users", [])
        print(f"[GUI] User list cache updated with {len(user_list_cache)} users.")

    elif action == "update_user_result":
        if status == "success":
            print("[CLIENT] User updated successfully. Requesting updated user list.")
            send_message({"action": "get_all_users", "username": current_user})
        else:
            error_msg = response.get("message", "An unknown error occurred.")
            print(f"[ERROR] User update failed: {error_msg}")

    elif action == "delete_user_result":
        if status == "success":
            print("[CLIENT] User deleted successfully. Requesting updated user list.")
            send_message({"action": "get_all_users", "username": current_user})
        else:
            error_msg = response.get("message", "An unknown error occurred.")
            print(f"[ERROR] User deletion failed: {error_msg}")

    # Handle chat messages here
    elif action == "chat":
        sender = response.get("username", "Unknown")
        content = response.get("content", "")
        if sender == current_user:
            display_message = f"You: {content}"
        else:
            display_message = f"{sender}: {content}"
        print(display_message)
        chat_messages.append(display_message)

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number."
    if not re.search(r'[._@]', password):
        return False, "Password must contain at least one special character (., _, @)."
    return True, ""

def select_user(username):
    global selected_user, current_screen
    selected_user = username
    current_screen = "user_details"


class Button:
    def __init__(self, x, y, width, height, text, color, hover_color, text_color, hover_text_color, action=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.hover_color = hover_color
        self.text = text
        self.text_color = text_color
        self.hover_text_color = hover_text_color
        self.action = action

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, self.hover_color if is_hovered else self.color, self.rect, border_radius=8)

        text_surf = FONT.render(self.text, True, self.hover_text_color if is_hovered else self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.action()

class InputBox:
    def __init__(self, x, y, w, h, is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = pygame.Color('gray')
        self.text = ''
        self.active = False
        self.error = False
        self.error_msg = ''
        self.is_password = is_password  # <-- NEW

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key != pygame.K_RETURN:
                self.text += event.unicode

    def draw(self, screen):
        outline = pygame.Color('red') if self.error else pygame.Color('blue') if self.active else pygame.Color('gray')
        pygame.draw.rect(screen, outline, self.rect, 2)
        display_text = '*' * len(self.text) if self.is_password else self.text
        txt_surface = FONT.render(display_text, True, pygame.Color('black'))
        screen.blit(txt_surface, (self.rect.x + 5, self.rect.y + 5))
        if self.error_msg:
            error_surf = FONT.render(self.error_msg, True, pygame.Color('red'))
            screen.blit(error_surf, (self.rect.x, self.rect.y + self.rect.height + 5))

    def clear_error(self):
        self.error = False
        self.error_msg = ''

user_buttons = []
selected_user = None
new_password_input = InputBox(300, 100, 200, 40, is_password=True)
confirm_password_input = InputBox(300, 160, 200, 40, is_password=True)
password_reset_message = ""
current_user = None  # Tracks who is currently logged in
scroll_offset = 0  # How many logs to skip at the top
max_visible_logs = 20
max_scroll_offset = 0
log_scroll_offset = 0
client_socket = None
receive_thread = None
client_connected = False
chat_input_active = False
logs_requested = False
user_list_cache = []

chat_scroll_offset = 0
max_visible_chat_messages = 10  # or whatever fits your current chat box
max_chat_scroll_offset = 0

chat_box_width = 300
chat_box_height = 280
resizing_chat = False
resize_start_mouse_pos = None
resize_start_box_size = None
auto_scroll = True

chat_visible = False  # Start hidden
chat_input_text = ""

login_username = InputBox(300, 190, 200, 40)
login_password = InputBox(300, 260, 200, 40, is_password=True)
signup_username = InputBox(300, 150, 200, 40)
signup_password = InputBox(300, 230, 200, 40, is_password=True)
signup_confirm = InputBox(300, 310, 200, 40, is_password=True)

def toggle_chat():
    global chat_visible
    chat_visible = not chat_visible
    print(f"[DEBUG] Chat visibility toggled: {chat_visible}")

def clear_signup_errors():
    signup_username.clear_error()
    signup_password.clear_error()
    signup_confirm.clear_error()

def request_all_users():
    if client_connected:
        send_message({"action": "get_all_users"})
    else:
        print("[ERROR] Not connected to server. Cannot request users.")

# New version
def reset_user_password(username):
    new_pw = new_password_input.text.strip()
    confirm_pw = confirm_password_input.text.strip()
    if new_pw == "" or confirm_pw == "":
        password_reset_message = "Password fields cannot be empty."
        return
    if new_pw != confirm_pw:
        password_reset_message = "Passwords do not match."
        return
    # Send a request to the server instead of touching the DB
    send_message({
        "action": "update_user",
        "target_username": username,
        "new_password": new_pw,
        "username": current_user
    })
    # The response will update the UI
    password_reset_message = "Request sent to server..."

def wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ''

    for word in words:
        test_line = current_line + word + ' '
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + ' '
    lines.append(current_line)
    return lines

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)

    # This is the most important part: triple-check the tuple ordering
    cursor.execute(
        "INSERT INTO logs (username, message, timestamp) VALUES (?, ?, ?)",
        (username, message, timestamp)
    )

    conn.commit()
    conn.close()

def update_logs_cache(logs):
    global logs_cache
    logs_cache = logs
    print(f"[GUI] logs_cache updated with {len(logs)} entries")

# New version
def delete_user(username):
    send_message({
        "action": "delete_user",
        "target_username": username,
        "username": current_user
    })
    selected_user = None
    # The response from the server will trigger the screen switch

# New version
def toggle_user_role(username):
    # Fetch the current role from your local cache (user_list_cache)
    current_role = "user" # Default
    for u in user_list_cache:
        if u[0] == username:
            current_role = u[1]
            break
    new_role = "admin" if current_role == "user" else "user"
    send_message({
        "action": "update_user",
        "target_username": username,
        "new_role": new_role,
        "username": current_user
    })

def show_manage_users():
    global current_screen
    current_screen = "manage_users"
    if client_connected and current_user:
        send_message({"action": "get_all_users", "username": current_user})

def draw_chat():
    global chat_box_width, chat_box_height, max_chat_scroll_offset

    chat_rect = pygame.Rect(WIDTH - chat_box_width - 10, HEIGHT - chat_box_height - 30, chat_box_width, chat_box_height)
    pygame.draw.rect(SCREEN, (230, 230, 250), chat_rect)
    pygame.draw.rect(SCREEN, (100, 100, 150), chat_rect, 2)

    # Draw resize handle (top-left corner)
    handle_rect = pygame.Rect(chat_rect.left, chat_rect.top, 10, 10)
    pygame.draw.rect(SCREEN, (150, 150, 200), handle_rect)

    # Draw messages with wrapping
    font = FONT
    line_height = 20
    max_width = chat_box_width - 20
    start_y = chat_rect.top + 10

    wrapped_lines = []
    for msg in chat_messages:
        wrapped_lines.extend(wrap_text(msg, font, max_width))

    max_visible_lines = chat_box_height // line_height - 1
    visible_lines = wrapped_lines[chat_scroll_offset:chat_scroll_offset + max_visible_lines]
    max_chat_scroll_offset = max(0, len(wrapped_lines) - max_visible_lines)
    for i, line in enumerate(visible_lines):
        msg_surf = font.render(line, True, (0, 0, 0))
        SCREEN.blit(msg_surf, (chat_rect.left + 10, start_y + i * line_height))

    # Draw input box
    input_rect = pygame.Rect(chat_rect.left, HEIGHT - 20, chat_box_width, 20)
    pygame.draw.rect(SCREEN, (255, 255, 255), input_rect)
    pygame.draw.rect(SCREEN, (100, 100, 150), input_rect, 2)

    input_surf = font.render(chat_input_text, True, (0, 0, 0))
    SCREEN.blit(input_surf, (input_rect.left + 5, input_rect.top))

def draw_user_details():
    SCREEN.fill((255, 255, 240))

    if not selected_user:
        return

    title = FONT.render(f"User: {selected_user}", True, (0, 0, 0))
    title_x = WIDTH // 2 - title.get_width() // 2
    SCREEN.blit(title, (title_x, 30))  # 30 px from the top

    label1 = FONT.render("New Password:", True, (0, 0, 0))
    SCREEN.blit(label1, (new_password_input.rect.x, new_password_input.rect.y - 25))
    new_password_input.draw(SCREEN)

    label2 = FONT.render("Confirm Password:", True, (0, 0, 0))
    SCREEN.blit(label2, (confirm_password_input.rect.x, confirm_password_input.rect.y - 25))
    confirm_password_input.draw(SCREEN)

    reset_password_button.draw(SCREEN)
    delete_user_button.draw(SCREEN)
    toggle_role_button.draw(SCREEN)
    back_to_manage_users_button.draw(SCREEN)

    # Show result message
    if password_reset_message:
        result_label = FONT.render(password_reset_message, True, (0, 128, 0))
        SCREEN.blit(result_label, (300, 220))
    draw_logged_in_user()
    chat_toggle_button.draw(SCREEN)

def draw_manage_users():
    global user_buttons
    SCREEN.fill((245, 245, 255))  # Light blue
    title = FONT.render("Manage Users", True, (0, 0, 0))
    SCREEN.blit(title, (300, 30))

    users = user_list_cache
    user_buttons = []
    y_offset = 100

    for user in users:
        username, role = user
        btn = Button( x=50, y=y_offset, width=300, height=35, text=f"{username} ({role})", color=(200, 200, 255), hover_color=(180, 180, 255), text_color=(0, 0, 0), hover_text_color=(0, 0, 100), action=lambda u=username: select_user(u))
        user_buttons.append(btn)
        btn.draw(SCREEN)
        y_offset += 50
    manage_users_back_button.draw(SCREEN)
    draw_logged_in_user()
    chat_toggle_button.draw(SCREEN)

def scroll_up():
    global scroll_offset
    if scroll_offset > 0:
        scroll_offset -= 1

def scroll_down():
    global scroll_offset
    if scroll_offset < max(0, len(logs) - max_visible_logs):
        scroll_offset += 1

def clear_all_inputs_and_messages():
    # Login screen inputs
    login_username.text = ""
    login_password.text = ""
    login_username.clear_error()
    login_password.clear_error()

    # Signup screen inputs
    signup_username.text = ""
    signup_password.text = ""
    signup_confirm.text = ""
    signup_username.clear_error()
    signup_password.clear_error()
    signup_confirm.clear_error()

    # Password reset fields
    new_password_input.text = ""
    confirm_password_input.text = ""

    # Clear messages
    global password_reset_message
    password_reset_message = ""


def draw_logs_viewer():
    SCREEN.fill((240, 240, 255))  # Light background

    # Draw Title
    title = FONT.render("Admin Logs", True, (0, 0, 0))
    SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, 20))

    headers = ["Date", "Time", "Username", "Action"]
    col_widths = [100, 80, 150, 350]

    # Fixed x_positions for table data (keep this unchanged)
    data_x_positions = [50]
    for w in col_widths[:-1]:
        data_x_positions.append(data_x_positions[-1] + w)

    # Separate x_positions for headers so you can tweak individually
    header_x_positions = [data_x_positions[0] + 5,  # Date header slightly right
                          data_x_positions[1] + 35,  # Time header shifted right
                          data_x_positions[2] + 60,  # Username header shifted right
                          data_x_positions[3] + 30]   # Action header slightly right

    # Draw header background
    header_bg_rect = pygame.Rect(45, 60, sum(col_widths) + 10, 30)
    pygame.draw.rect(SCREEN, (200, 200, 220), header_bg_rect)

    # Draw headers
    for i, header in enumerate(headers):
        header_text = FONT.render(header, True, (0, 0, 0))
        SCREEN.blit(header_text, (header_x_positions[i], 65))

    # Fetch logs
    try:
        logs = logs_cache
    except Exception as e:
        error_text = FONT.render(f"Error fetching logs: {e}", True, (255, 0, 0))
        SCREEN.blit(error_text, (50, 100))
        return

    # Starting position for rows
    y = 95
    row_height = 25
    text_vertical_offset = -3

    max_visible_logs = 20
    total_logs = len(logs)  # total number of logs you fetched

    max_scroll_offset = max(0, total_logs - max_visible_logs)

    start_index = log_scroll_offset
    end_index = start_index + max_visible_logs
    visible_logs = logs[start_index:end_index]

    # Draw logs rows with alternating colors
    for idx, log in enumerate(visible_logs):
        row_bg_color = (230, 230, 250) if idx % 2 == 0 else (245, 245, 255)
        row_rect = pygame.Rect(45, y, sum(col_widths) + 10, row_height)
        pygame.draw.rect(SCREEN, row_bg_color, row_rect)

        username = log.get("username", "Unknown")
        message = log.get("action", "No action")
        timestamp = log.get("timestamp", "N/A")
        if ' ' in timestamp:
            date_part, time_part = timestamp.split(' ')
        else:
            date_part = timestamp
            time_part = "N/A"

        # Render texts
        date_text = FONT.render(date_part, True, (0, 0, 0))
        time_text = FONT.render(time_part, True, (0, 0, 0))
        username_text = FONT.render(username, True, (0, 0, 0))
        action_text = FONT.render(message, True, (0, 0, 0))

        # Use fixed data positions here (no tweaking)
        SCREEN.blit(date_text, (data_x_positions[0] + 5, y + text_vertical_offset))
        SCREEN.blit(time_text, (data_x_positions[1] + 35, y + text_vertical_offset))
        SCREEN.blit(username_text, (data_x_positions[2] + 62, y + text_vertical_offset))
        SCREEN.blit(action_text, (data_x_positions[3] + 30, y + text_vertical_offset))

        y += row_height

        # Separate x_positions for vertical lines (can tweak individually)
        line_x_positions = [
            data_x_positions[1] + 30,
            data_x_positions[2] + 54,
            data_x_positions[3] + 25,
            data_x_positions[3] + col_widths[3] + 5  # End line (optional)
        ]
        # Draw vertical lines between columns
        line_color = (150, 150, 150)
        for x in line_x_positions:
            pygame.draw.line(SCREEN, line_color, (x, 60), (x, 60 + 30 + 25 * 20), 1)

    back_button_logs.draw(SCREEN)
    scroll_up_button.draw(SCREEN)
    scroll_down_button.draw(SCREEN)

def request_signup():
    username = signup_username.text.strip()
    password = signup_password.text.strip()
    confirm = signup_confirm.text.strip()
    clear_signup_errors()
    error_found = False

    if signup_username.text.strip() == '':
        signup_username.error = True
        signup_username.error_msg = "Username cannot be empty"
        error_found = True
    if signup_password.text.strip() == '':
        signup_password.error = True
        signup_password.error_msg = "Password cannot be empty"
        error_found = True
    if signup_confirm.text.strip() == '':
        signup_confirm.error = True
        signup_confirm.error_msg = "Confirm password cannot be empty"
        error_found = True

    if not signup_password.error and not signup_confirm.error:
        if signup_password.text != signup_confirm.text:
            signup_password.error = True
            signup_confirm.error = True
            signup_confirm.error_msg = "Passwords do not match"
            error_found = True

    valid, message = is_strong_password(password)
    if not valid:
        signup_password.error = True
        signup_password.error_msg = message
        error_found = True

    if not error_found:
        # Send signup request to the server
        if client_connected and client_socket:
            send_message({"action": "signup", "username": username, "password": password})
        else:
            print("[ERROR] Cannot send signup request - not connected to server.")
            signup_username.error = True
            signup_username.error_msg = "Server not connected. Please try again later."

def draw_logged_in_user():
    global user_role # Make sure this is accessible

    if current_user:
        # Use the global user_role variable directly
        user_text = FONT.render(f"Logged in as: {current_user} ({user_role})", True, (0, 0, 0))
        SCREEN.blit(user_text, (10, HEIGHT - 30))  # Bottom-left corner
        chat_toggle_button.draw(SCREEN)

def draw_admin_panel():
    SCREEN.fill((255, 230, 230))  # light red background
    title = FONT.render("Admin Panel", True, (0, 0, 0))
    SCREEN.blit(title, (300, 50))

    logout_button.draw(SCREEN)
    manage_users_button.draw(SCREEN)
    view_logs_button.draw(SCREEN)
    draw_logged_in_user()
    chat_toggle_button.draw(SCREEN)

def draw_login_screen():
    SCREEN.fill((255, 255, 255))

    label_user = FONT.render("Username:", True, (0, 0, 0))
    SCREEN.blit(label_user, (login_username.rect.x, login_username.rect.y - 30))

    label_pass = FONT.render("Password:", True, (0, 0, 0))
    SCREEN.blit(label_pass, (login_password.rect.x, login_password.rect.y - 30))

    login_username.draw(SCREEN)
    login_password.draw(SCREEN)
    login_button.draw(SCREEN)
    signup_button.draw(SCREEN)


def draw_welcome_screen():
    SCREEN.fill((230, 255, 230))  # light green for user
    title = FONT.render("Welcome to the Game!", True, (0, 0, 0))
    SCREEN.blit(title, (250, 50))
    draw_logged_in_user()
    chat_toggle_button.draw(SCREEN)

def draw_signup_screen():
    SCREEN.fill((240, 240, 255))

    label_signup_user = FONT.render("Username:", True, (0, 0, 0))
    SCREEN.blit(label_signup_user, (signup_username.rect.x, signup_username.rect.y - 30))

    label_signup_pass = FONT.render("Password:", True, (0, 0, 0))
    SCREEN.blit(label_signup_pass, (signup_password.rect.x, signup_password.rect.y - 30))

    label_confirm_pass = FONT.render("Confirm Password:", True, (0, 0, 0))
    SCREEN.blit(label_confirm_pass, (signup_confirm.rect.x, signup_confirm.rect.y - 30))

    signup_username.draw(SCREEN)
    signup_password.draw(SCREEN)
    signup_confirm.draw(SCREEN)
    signup_submit.draw(SCREEN)

    signup_submit.draw(SCREEN)
    back_button.draw(SCREEN)
logs = logs_cache

def switch_screen(name):
    global current_screen
    current_screen = name
    clear_all_inputs_and_messages()

    if name == "logs_viewer":
        try:
            if client_connected:
                request_admin_logs()
            else:
                print("[INFO] Delaying log request until client connects...")
        except Exception as e:
            print(f"[ERROR] Failed to request logs: {e}")

    if name == "manage_users":
        if client_connected:
            send_message({"action": "get_all_users"})
        else:
            print("[ERROR] Cannot request users - not connected.")

def request_login():
    # 1. Clear any previous error messages
    login_username.clear_error()
    login_password.clear_error()

    # 2. Get and strip the username and password
    username = login_username.text.strip()
    password = login_password.text.strip()

    # 3. Perform basic client-side validation
    if not username:
        login_username.error = True
        login_username.error_msg = "Username cannot be empty"
        return
    if not password:
        login_password.error = True
        login_password.error_msg = "Password cannot be empty"
        return

    # 4. Send the request to the server
    if client_connected and client_socket:
        print("[CLIENT] Sending login request to server...")
        send_message({"action": "login", "username": username, "password": password})
    else:
        # 5. Handle the disconnected state gracefully
        print("[ERROR] Cannot send login request - not connected to server.")
        login_password.error = True
        login_password.error_msg = "Server not connected. Please try again later."

login_button = Button(300, 320, 90, 40, "Login", (0, 200, 0), (0, 255, 0), (255, 255, 255), (0, 0, 0), request_login)
signup_button = Button(410, 320, 90, 40, "Sign Up", (0, 0, 200), (0, 0, 255), (255, 255, 255), (0, 0, 0), action=lambda: switch_screen("signup"))
signup_submit = Button(300, 380, 200, 40, "Create Account", (100, 0, 200), (150, 0, 255), (255, 255, 255), (0, 0, 0), request_signup)
back_button = Button(10,10,100,40,"Back",(150,0,0),(200,0,0),(255,255,255),(255,255,0),action=lambda: switch_screen("login"))
logout_button = Button(x=10, y=10, width=100, height=40, text="Log Out", color=(150, 0, 0), hover_color=(200, 0, 0), text_color=(255, 255, 255), hover_text_color=(255, 255, 0), action=lambda: switch_screen("login"))
manage_users_button = Button(x=10, y=60, width=180, height=40,text="Manage Users",color=(0, 100, 200),hover_color=(0, 150, 255),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=show_manage_users)
manage_users_back_button = Button(x=10, y=10, width=100, height=40,text="Back",color=(150, 0, 0),hover_color=(200, 0, 0),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=lambda: switch_screen("admin_panel"))
reset_password_button = Button( x=50, y=100, width=200, height=40, text="Reset Password", color=(100, 150, 100), hover_color=(120, 180, 120), text_color=(255, 255, 255), hover_text_color=(0, 0, 0), action=lambda: reset_user_password(selected_user))
delete_user_button = Button( x=50, y=160, width=200, height=40, text="Delete User", color=(150, 0, 0), hover_color=(200, 0, 0), text_color=(255, 255, 255), hover_text_color=(255, 255, 0), action=lambda: delete_user(selected_user))
toggle_role_button = Button( x=50, y=220, width=200, height=40, text="Toggle Admin/User", color=(0, 100, 200), hover_color=(0, 150, 255), text_color=(255, 255, 255), hover_text_color=(0, 0, 0), action=lambda: toggle_user_role(selected_user))
back_to_manage_users_button = Button(x=10, y=10, width=100, height=40,text="Back",color=(150, 0, 0),hover_color=(200, 0, 0),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=show_manage_users)
view_logs_button = Button(10, 120, 200, 40, "View Logs", (60, 60, 180), (100, 100, 220), (255, 255, 255), (255, 255, 0), action=lambda: switch_screen("logs_viewer"))
back_button_logs = Button(10, 10, 100, 40, "Back", (150, 0, 0), (200, 0, 0), (255, 255, 255), (255, 255, 0), action=lambda: switch_screen("admin_panel"))
scroll_up_button = Button(5, 500, 40, 40, "▲", (180, 180, 180), (150, 150, 150), (0, 0, 0), (0, 0, 0), scroll_up)
scroll_down_button = Button(750, 500, 40, 40, "▼", (180, 180, 180), (150, 150, 150), (0, 0, 0), (0, 0, 0), scroll_down)
chat_toggle_button = Button(
    x=WIDTH - 110, y=10, width=100, height=40,
    text="Chat",
    color=(0, 120, 200), hover_color=(0, 150, 255),
    text_color=(255, 255, 255), hover_text_color=(255, 255, 0),
    action=lambda: toggle_chat()# <== This line is important
)

try:
    start_client_connection()
except Exception as e:
    print(f"[CRITICAL ERROR] Failed to start client connection: {e}")

running = True
clock = pygame.time.Clock()
while running:
    try:
        # get_nowait() retrieves an item immediately or raises an exception
        new_screen = screen_change_queue.get_nowait()
        switch_screen(new_screen)
    except queue.Empty:
        # Do nothing if the queue is empty
        pass
    pygame.event.set_allowed(None)  # Restrict event types
    pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT])
    pygame.key.start_text_input()
    SCREEN.fill((255, 255, 255))
    current_logs = logs_cache
    logs_viewer_height = 25 * 20
    log_row_height = 25
    max_visible_logs = logs_viewer_height // log_row_height  # Set dynamically if needed
    max_scroll_offset = max(0, len(current_logs) - max_visible_logs)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            if client_socket:
                try:
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
                except Exception:
                    pass
        if event.type == pygame.MOUSEWHEEL:
            if chat_visible:
                chat_scroll_offset -= event.y
                chat_scroll_offset = max(0, min(chat_scroll_offset, max_chat_scroll_offset))
            elif current_screen == "logs_viewer":  # Only scroll logs if chat isn't open
                log_scroll_offset -= event.y
                log_scroll_offset = max(0, min(log_scroll_offset, max_scroll_offset))
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            chat_rect = pygame.Rect(WIDTH - chat_box_width - 10, HEIGHT - chat_box_height - 30, chat_box_width,
                                    chat_box_height)
            input_rect = pygame.Rect(chat_rect.left, HEIGHT - 20, chat_box_width, 20)
            if input_rect.collidepoint(mouse_x, mouse_y):
                chat_input_active = True
            else:
                chat_input_active = False
            handle_rect = pygame.Rect(chat_rect.left, chat_rect.top, 10, 10)

            if handle_rect.collidepoint(mouse_x, mouse_y):
                resizing_chat = True
                resize_start_mouse_pos = (mouse_x, mouse_y)
                resize_start_box_size = (chat_box_width, chat_box_height)
            if scroll_up_button.rect.collidepoint(event.pos):
                log_scroll_offset = max(0, log_scroll_offset - 1)
            elif scroll_down_button.rect.collidepoint(event.pos):
                log_scroll_offset = min(max_scroll_offset, log_scroll_offset + 1)
        elif event.type == pygame.MOUSEBUTTONUP:
            resizing_chat = False
        if chat_input_active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                chat_input_text = chat_input_text[:-1]
            elif event.key == pygame.K_RETURN:
                if chat_input_text.strip() != "":
                    send_chat_message(chat_input_text.strip(), current_user)
                    chat_input_text = ""
            else:
                if len(event.unicode) > 0 and event.unicode.isprintable():
                    chat_input_text += event.unicode
        elif event.type == pygame.MOUSEMOTION and resizing_chat:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            dx = resize_start_mouse_pos[0] - mouse_x
            dy = resize_start_mouse_pos[1] - mouse_y

            chat_box_width = max(200, resize_start_box_size[0] + dx)
            chat_box_height = max(100, resize_start_box_size[1] + dy)
        if current_screen == "login":
            login_username.handle_event(event)
            login_password.handle_event(event)
            login_button.check_click(event)
            signup_button.check_click(event)
        elif current_screen == "signup":
            signup_username.handle_event(event)
            signup_password.handle_event(event)
            signup_confirm.handle_event(event)
            signup_submit.check_click(event)
            back_button.check_click(event)
        elif current_screen == "admin_panel":
            logout_button.check_click(event)
            manage_users_button.check_click(event)
            view_logs_button.check_click(event)
            chat_toggle_button.check_click(event)
        elif current_screen == "manage_users":
            for button in user_buttons:
                button.check_click(event)
            manage_users_back_button.check_click(event)
            chat_toggle_button.check_click(event)
        elif current_screen == "user_details":
            reset_password_button.check_click(event)
            delete_user_button.check_click(event)
            toggle_role_button.check_click(event)
            back_to_manage_users_button.check_click(event)
            new_password_input.handle_event(event)
            confirm_password_input.handle_event(event)
            chat_toggle_button.check_click(event)
        elif current_screen == "logs_viewer":
            back_button_logs.check_click(event)
            scroll_up_button.check_click(event)
            scroll_down_button.check_click(event)
            if chat_visible:
                toggle_chat()
        elif current_screen == "welcome_screen":
            chat_toggle_button.check_click(event)

    if current_screen == "login":
        draw_login_screen()
    elif current_screen == "signup":
        draw_signup_screen()
    elif current_screen == "admin_panel":
        draw_admin_panel()
        if chat_visible:
            draw_chat()
    elif current_screen == "welcome_screen":
        draw_welcome_screen()
        if chat_visible:
            draw_chat()
    elif current_screen == "manage_users":
        draw_manage_users()
        if chat_visible:
            draw_chat()
    elif current_screen == "user_details":
        draw_user_details()
        if chat_visible:
            draw_chat()
    elif current_screen == "logs_viewer" and not logs_requested:
        request_admin_logs()
        logs_requested = True
    elif current_screen == "logs_viewer":
        draw_logs_viewer()
    if current_screen != "logs_viewer":
        logs_requested = False
    pygame.display.flip()
    clock.tick(60)

if client_connected and client_socket:
    try:
        client_socket.close()
        client_connected = False
        print("[DEBUG] Disconnected from server.")
    except Exception as e:
        print(f"[ERROR] Error closing socket: {e}")

pygame.quit()