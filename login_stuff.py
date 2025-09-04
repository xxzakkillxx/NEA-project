import pygame
import sqlite3
import hashlib
import os
import re
from datetime import datetime
import client
import socket

pygame.init()
WIDTH, HEIGHT = 800, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Login & Signup System")
FONT = pygame.font.SysFont("arial", 24)
current_screen = "login"

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            salt TEXT
        )
    """)
    conn.commit()
    conn.close()

DB_PATH = 'game_data.db'
initialize_database()

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

def clear_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    print("All users deleted.")

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

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = cursor.fetchall()
    conn.close()
    return users  # List of (username, role)

def reset_user_password(username):
    global password_reset_message

    new_pw = new_password_input.text.strip()
    confirm_pw = confirm_password_input.text.strip()

    if new_pw == "" or confirm_pw == "":
        password_reset_message = "Password fields cannot be empty."
        return

    if new_pw != confirm_pw:
        password_reset_message = "Passwords do not match."
        return

    salt = os.urandom(16).hex()
    hashed_pw = hashlib.sha256((new_pw + salt).encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ?, salt = ? WHERE username = ?", (hashed_pw, salt, username))
    conn.commit()
    conn.close()

    log_action(current_user, f"Reset password for user '{username}'")
    password_reset_message = f"Password updated for '{username}'"

    # Clear inputs
    new_password_input.text = ""
    confirm_password_input.text = ""

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

def log_action(username, message):
    print(f"LOGGING: {username} - {message}")  # Debug print
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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


def delete_user(username):
    global selected_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    print(f"User {username} deleted.")
    selected_user = None
    switch_screen("manage_users")
    log_action(current_user, f"Deleted user {selected_user}")


def fetch_admin_logs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, message, timestamp FROM logs ORDER BY id DESC")
    logs = cursor.fetchall()
    conn.close()
    return logs

def toggle_user_role(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    if result:
        current_role = result[0]
        new_role = "admin" if current_role == "user" else "user"
        cursor.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
        conn.commit()
        print(f"Changed role of {username} to {new_role}")
        log_action(current_user, f"Toggled role for {selected_user} to {new_role}")
    conn.close()

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
    for msg in client.chat_messages:
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

    users = get_all_users()
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
        logs = fetch_admin_logs()
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

        _, username, message, timestamp = log
        date_part, time_part = timestamp.split(' ')

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

def signup_submit_action():
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

    if not error_found and user_exists(signup_username.text):
        signup_username.error = True
        signup_username.error_msg = "Username already taken"
        error_found = True

    valid, message = is_strong_password(password)
    if not valid:
        signup_password.error = True
        signup_password.error_msg = message
        error_found = True

    if not error_found:
        create_user(username, password)
        print("Sign Up Success! Data:")
        print(f"Username: {signup_username.text}")
        print(f"Password: {signup_password.text}")
        signup_username.text = ''
        signup_password.text = ''
        signup_confirm.text = ''
        clear_signup_errors()
        global current_screen
        current_screen = "login"
        log_action(username, "Signed up")
    else:
        print("Sign Up Failed: Errors found")

def is_admin(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result is not None and result[0] == 'admin'

def draw_logged_in_user():
    if current_user:
        role = get_user_role(current_user)
        user_text = FONT.render(f"Logged in as: {current_user} ({role})", True, (0, 0, 0))
        SCREEN.blit(user_text, (10, HEIGHT - 30))  # Bottom-left corner
        chat_toggle_button.draw(SCREEN)

def get_user_role(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "user"  # default to "user" if not found


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
logs = fetch_admin_logs()

def switch_screen(name):
    global current_screen
    current_screen = name
    clear_all_inputs_and_messages()

def dummy_login():
    login_username.clear_error()
    login_password.clear_error()

    username = login_username.text.strip()
    password = login_password.text.strip()

    if username == '':
        login_username.error = True
        login_username.error_msg = "Username cannot be empty"
        return

    if password == '':
        login_password.error = True
        login_password.error_msg = "Password cannot be empty"
        return

    if not user_exists(username):
        login_username.error = True
        login_username.error_msg = "Username does not exist"
        return

    if not verify_user(username, password):
        login_password.error = True
        login_password.error_msg = "Incorrect password"
        return

    print("Login successful!")
    global current_user, current_screen
    current_user = username
    log_action(current_user, "Logged in successfully")
    if is_admin(username):
        current_screen = "admin_panel"
        import client

        # After setting current_user and switching screen
        client.start_client_connection(current_user)

    else:
        current_screen = "welcome_screen"
        import client

        # After setting current_user and switching screen
        client.start_client_connection(current_user)


login_button = Button(300, 320, 90, 40, "Login", (0, 200, 0), (0, 255, 0), (255, 255, 255), (0, 0, 0), dummy_login)
signup_button = Button(410, 320, 90, 40, "Sign Up", (0, 0, 200), (0, 0, 255), (255, 255, 255), (0, 0, 0), action=lambda: switch_screen("signup"))
signup_submit = Button(300, 380, 200, 40, "Create Account", (100, 0, 200), (150, 0, 255), (255, 255, 255), (0, 0, 0), signup_submit_action)
back_button = Button(10,10,100,40,"Back",(150,0,0),(200,0,0),(255,255,255),(255,255,0),action=lambda: switch_screen("login"))
logout_button = Button(x=10, y=10, width=100, height=40, text="Log Out", color=(150, 0, 0), hover_color=(200, 0, 0), text_color=(255, 255, 255), hover_text_color=(255, 255, 0), action=lambda: switch_screen("login"))
manage_users_button = Button(x=10, y=60, width=180, height=40,text="Manage Users",color=(0, 100, 200),hover_color=(0, 150, 255),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=lambda: switch_screen("manage_users"))
manage_users_back_button = Button(x=10, y=10, width=100, height=40,text="Back",color=(150, 0, 0),hover_color=(200, 0, 0),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=lambda: switch_screen("admin_panel"))
reset_password_button = Button( x=50, y=100, width=200, height=40, text="Reset Password", color=(100, 150, 100), hover_color=(120, 180, 120), text_color=(255, 255, 255), hover_text_color=(0, 0, 0), action=lambda: reset_user_password(selected_user))
delete_user_button = Button( x=50, y=160, width=200, height=40, text="Delete User", color=(150, 0, 0), hover_color=(200, 0, 0), text_color=(255, 255, 255), hover_text_color=(255, 255, 0), action=lambda: delete_user(selected_user))
toggle_role_button = Button( x=50, y=220, width=200, height=40, text="Toggle Admin/User", color=(0, 100, 200), hover_color=(0, 150, 255), text_color=(255, 255, 255), hover_text_color=(0, 0, 0), action=lambda: toggle_user_role(selected_user))
back_to_manage_users_button = Button(x=10, y=10, width=100, height=40,text="Back",color=(150, 0, 0),hover_color=(200, 0, 0),text_color=(255, 255, 255),hover_text_color=(255, 255, 0),action=lambda: switch_screen("manage_users"))
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

current_screen = "login"
running = True
clock = pygame.time.Clock()
while running:
    pygame.event.set_allowed(None)  # Restrict event types
    pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT])
    pygame.key.start_text_input()
    SCREEN.fill((255, 255, 255))
    current_logs = fetch_admin_logs()
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
                    client.send_chat_message(chat_input_text.strip(), current_user)
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
        #if chat_visible:
        #    if event.type == pygame.KEYDOWN:
        #        if event.key == pygame.K_BACKSPACE:
        #            chat_input_text = chat_input_text[:-1]
        #        elif event.key == pygame.K_RETURN:
        #            if chat_input_text.strip() != "":
        #                client.send_chat_message(chat_input_text.strip(),current_user)
        #                chat_input_text = ""
        #        else:
        #            # Add characters to input (handle only printable characters)
        #            if len(event.unicode) > 0 and event.unicode.isprintable():
        #                chat_input_text += event.unicode
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
    elif current_screen == "logs_viewer":
        draw_logs_viewer()
    pygame.display.flip()
    clock.tick(60)

if client.client_connected and client.client_socket:
    try:
        client.client_socket.close()
        client.client_connected = False
        print("[DEBUG] Disconnected from server.")
    except Exception as e:
        print(f"[ERROR] Error closing socket: {e}")

pygame.quit()