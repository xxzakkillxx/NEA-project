from time import sleep

import pygame
import sys
import textwrap
import time
pygame.init()
screen_width, screen_height = 800, 700
surface = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("escape room game")
player_inventory = ["knife","note book","key"]

BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
PINK = (255, 192, 203)
BROWN = (165, 42, 42)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
WHITE = (255, 255, 255)
PEACH = (255, 218, 185)
rune_name = None

BG = (50, 50, 50)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BUTTON_COLOR = (0, 200, 0)
BUTTON_HOVER = (0, 255, 0)
rune_sheet_image = pygame.image.load('rune_sheet.png').convert_alpha()
sprite_sheet_image = pygame.image.load('spritecharacterwalk.png').convert_alpha()

def get_image(sheet, x, y, width, height, colorkey=(255, 255, 255)):
    image = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
    image.blit(sheet, (0, 0), (x, y, width, height))
    image.set_colorkey(colorkey)
    return image
rune_list = []
for a in range(0,8):
    rune_list.append(get_image(rune_sheet_image, (a * 56), (0 * 93), (56), (93)))
for b in range(0,8):
    if b==0:
        pass
    else:
        rune_list.append(get_image(rune_sheet_image, (b * 56), (1 * 93), (56), (93)))
for c in range(0,8):
    rune_list.append(get_image(rune_sheet_image, (c * 56), (2 * 93), (56), (93)))
for d in range(0,8):
    rune_list.append(get_image(rune_sheet_image, (d * 56), (3 * 93), (56), (93)))
for e in range(0,8):
    rune_list.append(get_image(rune_sheet_image, (e * 56), (4 * 93), (56), (93)))
down_frames = []
down_frames.append(get_image(sprite_sheet_image,15,0,32,64))
down_frames.append(get_image(sprite_sheet_image,79,0,32,64))
down_frames.append(get_image(sprite_sheet_image,143,0,32,64))
down_frames.append(get_image(sprite_sheet_image,207,0,32,64))
right_frames = []
right_frames.append(get_image(sprite_sheet_image,15,139,64,64))
right_frames.append(get_image(sprite_sheet_image,79,139,64,64))
right_frames.append(get_image(sprite_sheet_image,143,139,64,64))
right_frames.append(get_image(sprite_sheet_image,207,139,64,64))
left_frames = []
left_frames.append(get_image(sprite_sheet_image,15,77,64,64))
left_frames.append(get_image(sprite_sheet_image,79,77,64,64))
left_frames.append(get_image(sprite_sheet_image,143,77,64,64))
left_frames.append(get_image(sprite_sheet_image,207,77,64,64))
up_frames = []
up_frames.append(get_image(sprite_sheet_image,15,205,32,64))
up_frames.append(get_image(sprite_sheet_image,79,205,32,64))
up_frames.append(get_image(sprite_sheet_image,143,205,32,64))
up_frames.append(get_image(sprite_sheet_image,207,205,32,64))

class Character(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.images = {"down": down_frames, "left": left_frames, "right": right_frames, "up": up_frames}
        self.direction = "down"
        self.image_index = 0
        self.image = self.images[self.direction][self.image_index]
        self.rect = self.image.get_rect(topleft=(x, y))
        self.correct = 0
        self.cube_count = 0
        self.hitbox_offset_top = 5
        self.hitbox_offset_side = 5
        self.hitbox_height_adjust = 15

        self.update_hitbox()

        self.frame_delay = 1
        self.frame_count = 0

    def update_hitbox(self):
        if self.direction in ["left", "right"]:
            self.hitbox = pygame.Rect(
                self.rect.x + self.hitbox_offset_side,
                self.rect.y + self.hitbox_offset_top,
                self.rect.width - (2 * self.hitbox_offset_side),
                self.rect.height - self.hitbox_height_adjust
            )
        else:
            self.hitbox = pygame.Rect(
                self.rect.x + self.hitbox_offset_side,
                self.rect.y + self.hitbox_offset_top,
                self.rect.width - (2 * self.hitbox_offset_side),
                self.rect.height
            )

    def movement(self):
        keys = pygame.key.get_pressed()
        speed = 3
        moved = False

        if keys[pygame.K_RIGHT]:
            self.rect.x += speed
            self.direction = "right"
            moved = True
            self.update_hitbox()
            if pygame.sprite.spritecollide(self, walls, False, collided=lambda s, w: s.hitbox.colliderect(w.rect)):
                self.rect.x -= speed

        elif keys[pygame.K_LEFT]:
            self.rect.x -= speed
            self.direction = "left"
            moved = True
            self.update_hitbox()
            if pygame.sprite.spritecollide(self, walls, False, collided=lambda s, w: s.hitbox.colliderect(w.rect)):
                self.rect.x += speed

        elif keys[pygame.K_UP]:
            self.rect.y -= speed
            self.direction = "up"
            moved = True
            self.update_hitbox()
            if pygame.sprite.spritecollide(self, walls, False, collided=lambda s, w: s.hitbox.colliderect(w.rect)):
                self.rect.y += speed

        elif keys[pygame.K_DOWN]:
            self.rect.y += speed
            self.direction = "down"
            moved = True
            self.update_hitbox()
            if pygame.sprite.spritecollide(self, walls, False, collided=lambda s, w: s.hitbox.colliderect(w.rect)):
                self.rect.y -= speed

        elif keys[pygame.K_ESCAPE]:
            global game_state
            game_state = STATE_MENU

        elif keys[pygame.K_h]:
            global game_State
            game_State = STATE_HISTORY
            historyscreen()

        task_collision = pygame.sprite.spritecollide(self, tasks, False)
        for task in task_collision:
            if task.colour not in chosen_colours:
                chosen_colours.append(task.colour)

        if moved:
            self.frame_count += 1
            if self.frame_count >= self.frame_delay:
                self.frame_count = 0
                self.image_index = (self.image_index + 1) % len(self.images[self.direction])
                self.image = self.images[self.direction][self.image_index]

    def update(self):
        self.movement()
        display_tasks.empty()
        j = -50
        for mark in chosen_colours:
            j = j + 75
            display_tasks.add(display_task(j, 625, 75, 75, mark))
        self.correct = 0
        correct_ord = [(255, 0, 255), (0, 0, 255), (255, 255, 0), (128, 0, 128), (255, 255, 255), (255, 192, 203), (255, 218, 185), (255, 165, 0), (165, 42, 42), (0, 255, 255)]
        for t, i in enumerate(chosen_colours):
            if i == correct_ord[t]:
                self.correct += 1
        #if len(chosen_colours) == 10:
        #    x=-65
        #    y=50
        #    display_tasks.empty()
        #    for mark in chosen_colours:
        #        x=x + 65
        #        if x==720:
        #            y=y+65
        #            x=0
        #        display_tasks2.add(display_task(x+15,y,65,65,mark))

        cell_size = 65
        row_length = 3
        cube_width = row_length * cell_size + cell_size

        x_start = self.cube_count * cube_width
        y_start = 50

        x = x_start
        y = y_start

        # Add new display task blocks in a 3x3 layout
        for i, mark in enumerate(chosen_colours):
            if i == 9:
                x = x_start + (row_length * cell_size)
                y = y_start
                display_tasks2.add(display_task(x, y, cell_size, cell_size * 3, mark))
            else:
                display_tasks2.add(display_task(x, y, cell_size, cell_size, mark))

            if i < 9:
                x += cell_size
                if (i + 1) % row_length == 0:
                    x = x_start
                    y += cell_size
        self.cube_count += 1
class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height,colour):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.colour = colour
        self.image.fill(self.colour)
        self.rect = self.image.get_rect(topleft=(x, y))

walls = pygame.sprite.Group()
walls.add(Wall(0,0, 225, 25,BLACK),Wall(300,0,500,25,BLACK), Wall(0, 0, 25, 800,BLACK),
          Wall(0, 700, 800, 25,BLACK),Wall(775, 0, 25, 800,BLACK),Wall(0,600,350,25,BLACK),
          Wall(425,600,375,25,BLACK),Wall(425,500,25,125,BLACK),Wall(325,500,25,100,BLACK),
          Wall(300,0,25,125,BLACK),Wall(300,100,150,25,BLACK),Wall(575,100,100,25,BLACK),
          Wall(650,100,25,325,BLACK),Wall(450,500,200,25,BLACK),Wall(100,100,25,275,BLACK),
          Wall(200,100,100,25,BLACK),Wall(200,400,50,125,BLACK),Wall(325,400,100,25,BLACK),
          Wall(425,300,25,125,BLACK),Wall(550,100,25,325,BLACK),Wall(200,200,25,125,BLACK),
          Wall(100,200,100,25,BLACK),Wall(300,200,25,125,BLACK),Wall(100,450,100,25,BLACK),
          Wall(300,200,150,25,BLACK),Wall(450,100,25,125,BLACK),Wall(225,300,75,25,BLACK),
          Wall(100,450,25,150,BLACK))

walls.add(Wall(225,0,75,25,RED))

class task(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height,colour):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(colour)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.colour = colour

tasks = pygame.sprite.Group()

tasks.add(task(325,25,75,75,PINK),task(675,25,100,100,ORANGE),task(225,25,75,75,CYAN),
          task(575,125,75,75,PURPLE),task(375,125,75,75,WHITE),task(325,225,100,100,BROWN),
          task(125,225,75,75,PEACH),task(125,475,75,125,MAGENTA),task(450,525,75,75,YELLOW),
          task(25,525,75,75,BLUE))
chosen_colours = []

class display_task(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height,colour):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(colour)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.colour = colour
display_tasks = pygame.sprite.Group()
display_tasks2 = pygame.sprite.Group()


players = pygame.sprite.Group()
player1 = Character(375, 600)
players.add(player1)

class Button:
    def __init__(self, x, y, width, height, text, action,BUTTON_HOVER,BUTTON_COLOR):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.font = pygame.font.SysFont(None, 40)
        self.BUTTON_HOVER = BUTTON_HOVER
        self.BUTTON_COLOR = BUTTON_COLOR

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        color = self.BUTTON_HOVER if self.rect.collidepoint(mouse_pos) else self.BUTTON_COLOR
        pygame.draw.rect(surface, color, self.rect, border_radius=10)

        if self.text:
            wrapped_text = textwrap.wrap(self.text, width=30)
            text_height = self.font.get_height()
            total_text_height = len(wrapped_text) * text_height
            start_y = self.rect.centery - total_text_height // 2

            for line in wrapped_text:
                text_surface = self.font.render(line, True, BLACK)
                text_rect = text_surface.get_rect(center=(self.rect.centerx, start_y))
                surface.blit(text_surface, text_rect)
                start_y += text_height

    def check_click(self):
        if pygame.mouse.get_pressed()[0]:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                if self.action == None:
                    pass
                else:
                    self.action()
                    sleep(0.3)

STATE_MENU = "menu"
STATE_GAME = "game"
STATE_INVENTORY = "inventory"
STATE_INTRO = "intro"
STATE_HISTORY = "history"
STATE_RUNE = "rune"
STATE_RUNE_INFO = "rune info"
game_state = STATE_MENU
rune_info = "11"
def reset_game():
    global chosen_colours, player_inventory
    chosen_colours = []
    player_inventory = ["knife", "note book", "key"]
    player1.rect.topleft = (375, 600)
def restart_game():
    reset_game()
    global game_state
    game_state = STATE_GAME

def start_game():
    global game_state
    game_state = STATE_GAME

def invscreen():
    global game_state
    game_state = STATE_INVENTORY

def infoscreen():
    global game_state
    game_state = STATE_INTRO

def terminate_game():
    pygame.quit()
    sys.exit()

def open_menu():
    global game_state
    game_state = STATE_MENU

def historyscreen():
    global game_state
    game_state = STATE_HISTORY

def rune_screen():
    global game_state
    game_state = STATE_RUNE

def rune_11_b():
    global game_state
    global rune_info
    global rune_name
    game_state = STATE_RUNE_INFO
    rune_info = "11"
    rune_name = "rune 1"
def rune_12_b():
    global game_state
    global rune_info
    global rune_name
    game_state = STATE_RUNE_INFO
    rune_info = "12"
    rune_name = "rune 2"
def rune_13_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "13"
    rune_name = "rune 3"
def rune_14_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "14"
    rune_name = "rune 4"
def rune_15_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "15"
    rune_name = "rune 5"
def rune_16_b():
    global game_state
    global rune_info
    global rune_name
    game_state = STATE_RUNE_INFO
    rune_info = "16"
    rune_name = "rune 6"
def rune_17_b():
    global game_state
    global rune_info
    global rune_name
    game_state = STATE_RUNE_INFO
    rune_info = "17"
    rune_name = "rune 7"
def rune_21_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "21"
    rune_name = "rune 8"
def rune_22_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "22"
    rune_name = "rune 9"
def rune_23_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "23"
    rune_name = "rune 10"
def rune_24_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "24"
    rune_name = "rune 11"
def rune_25_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "25"
    rune_name = "rune 12"
def rune_26_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "26"
    rune_name = "rune 13"
def rune_27_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "27"
    rune_name = "rune 14"
def rune_31_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "31"
    rune_name = "rune 15"
def rune_32_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "32"
    rune_name = "rune 16"
def rune_33_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "33"
    rune_name = "rune 17"
def rune_34_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "34"
    rune_name = "rune 18"
def rune_35_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "35"
    rune_name = "rune 19"
def rune_36_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "36"
    rune_name = "rune 20"
def rune_37_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "37"
    rune_name = "rune 21"
def rune_41_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "41"
    rune_name = "rune 22"
def rune_42_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "42"
    rune_name = "rune 23"
def rune_43_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "43"
    rune_name = "rune 24"
def rune_44_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "44"
    rune_name = "rune 25"
def rune_45_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "45"
    rune_name = "rune 26"
def rune_46_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "46"
    rune_name = "rune 27"
def rune_47_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "47"
    rune_name = "rune 28"
def rune_51_b():
    global rune_name
    global game_state
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "51"
    rune_name = "rune 29"
def rune_52_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "52"
    rune_name = "rune 30"
def rune_53_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "53"
    rune_name = "rune 31"
def rune_54_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "54"
    rune_name = "rune 32"
def rune_55_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "55"
    rune_name = "rune 33"
def rune_56_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "56"
    rune_name = "rune 34"
def rune_57_b():
    global game_state
    global rune_name
    global rune_info
    game_state = STATE_RUNE_INFO
    rune_info = "57"
    rune_name = "rune 35"

start_button = Button(300, 350, 200, 60, "Start Game", start_game,(0,255,0),(0,200,0))
welcome_title = Button(175,0,450,60,"welcome to the escape room !",None,(255,0,0),(255,0,0))
exit_button = Button(300,430,200,60,"exit",terminate_game,(255,0,0),(200,0,0))
inventory_button = Button(300,270,200,60,"inventory",invscreen,(100,0,100),(128,0,128))
inv_back_button = Button(0,0,200,60,"back", open_menu,(200,200,200),(255,255,255))
l_colour_bg_button = Button(150,100,500,500,None,None,RED,RED)
l_overlay1_colour_bg_button = Button(150,150,500,100,"the colours arent in order...",None,RED,RED)
l_retry_colour_bg_button = Button(300,300,200,100,"try again ?",restart_game,BLUE,RED)
w_colour_bg_button = Button(150,100,500,500,None,None,GREEN,GREEN)
w_overlay1_colour_bg_button = Button(150,150,500,100,"All colours are in order !!!",None,GREEN,GREEN)
w_victory_colour_bg_button = Button(300,300,200,100,"you passed the first mini game !",None,GREEN,GREEN)
colour_intro_button = Button(150,100,500,500,"welcome to the escape room... "
                                             "your first challenge will be to guess and choose colours from the map in the correct order "
                                             "by steping on the coloured platforms. "
                                             "the colours you choose are shown at the bottom of the screen. "
                                             "once you have picked all 10 colours you will get to see how many you got in the correct order. "
                                             "using this you will be abe to determine the correct sequence of colours... eventually.... "
                                             "GL ! (click purple to continue...) ",start_game,PURPLE,PURPLE)
history_back_button = Button(0,0,200,50,"back", start_game,(200,200,200),(255,255,255))
rune_title_button = Button(200,0,400,50,"RUNES : Click a rune for info.",None,PEACH,PEACH)
rune_back_button = Button(0,0,100,50,"back", open_menu,PEACH,PEACH)
rune_button = Button(300,190,200,60,"runes",rune_screen,BROWN,BROWN)
rune_11_button = Button(51,50,56,93,None,rune_11_b,PINK,PINK)
rune_12_button = Button(158,50,56,93,None,rune_12_b,PINK,PINK)
rune_13_button = Button(265,50,56,93,None,rune_13_b,PINK,PINK)
rune_14_button = Button(372,50,56,93,None,rune_14_b,PINK,PINK)
rune_15_button = Button(479,50,56,93,None,rune_15_b,PINK,PINK)
rune_16_button = Button(586,50,56,93,None,rune_16_b,PINK,PINK)
rune_17_button = Button(693,50,56,93,None,rune_17_b,PINK,PINK)
rune_21_button = Button(51,189,56,93,None,rune_21_b,PINK,PINK)
rune_22_button = Button(158,189,56,93,None,rune_22_b,PINK,PINK)
rune_23_button = Button(265,189,56,93,None,rune_23_b,PINK,PINK)
rune_24_button = Button(372,189,56,93,None,rune_24_b,PINK,PINK)
rune_25_button = Button(479,189,56,93,None,rune_25_b,PINK,PINK)
rune_26_button = Button(586,189,56,93,None,rune_26_b,PINK,PINK)
rune_27_button = Button(693,189,56,93,None,rune_27_b,PINK,PINK)
rune_31_button = Button(51,328,56,93,None,rune_31_b,PINK,PINK)
rune_32_button = Button(158,328,56,93,None,rune_32_b,PINK,PINK)
rune_33_button = Button(265,328,56,93,None,rune_33_b,PINK,PINK)
rune_34_button = Button(372,328,56,93,None,rune_34_b,PINK,PINK)
rune_35_button = Button(479,328,56,93,None,rune_35_b,PINK,PINK)
rune_36_button = Button(586,328,56,93,None,rune_36_b,PINK,PINK)
rune_37_button = Button(693,328,56,93,None,rune_37_b,PINK,PINK)
rune_41_button = Button(51,467,56,93,None,rune_41_b,PINK,PINK)
rune_42_button = Button(158,467,56,93,None,rune_42_b,PINK,PINK)
rune_43_button = Button(265,467,56,93,None,rune_43_b,PINK,PINK)
rune_44_button = Button(372,467,56,93,None,rune_44_b,PINK,PINK)
rune_45_button = Button(479,467,56,93,None,rune_45_b,PINK,PINK)
rune_46_button = Button(586,467,56,93,None,rune_46_b,PINK,PINK)
rune_47_button = Button(693,467,56,93,None,rune_47_b,PINK,PINK)
rune_51_button = Button(51,606,56,93,None,rune_51_b,PINK,PINK)
rune_52_button = Button(158,606,56,93,None,rune_52_b,PINK,PINK)
rune_53_button = Button(265,606,56,93,None,rune_53_b,PINK,PINK)
rune_54_button = Button(372,606,56,93,None,rune_54_b,PINK,PINK)
rune_55_button = Button(479,606,56,93,None,rune_55_b,PINK,PINK)
rune_56_button = Button(586,606,56,93,None,rune_56_b,PINK,PINK)
rune_57_button = Button(693,606,56,93,None,rune_57_b,PINK,PINK)
rune_info_back_button = Button(0,0,200,60,"back", rune_screen,PEACH,PEACH)

clock = pygame.time.Clock()
running = True
while running:
    surface.fill(BG)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    if game_state == STATE_MENU:
        surface.fill(WHITE)
        start_button.draw(surface)
        start_button.check_click()
        welcome_title.draw(surface)
        exit_button.draw(surface)
        exit_button.check_click()
        inventory_button.draw(surface)
        inventory_button.check_click()
        rune_button.draw(surface)
        rune_button.check_click()

    elif game_state == STATE_GAME:
        tasks.draw(surface)
        display_tasks.update()
        display_tasks.draw(surface)
        players.update()
        players.draw(surface)
        walls.draw(surface)
        if len(chosen_colours) == 10:
            if player1.correct < 10:
                l_colour_bg_button.draw(surface)
                l_overlay1_colour_bg_button.draw(surface)
                overlay2_colour_bg_button = Button(150, 450, 500, 100, ("you got " + str(player1.correct) + " in order..."),None, RED, RED)
                overlay2_colour_bg_button.draw(surface)
                l_retry_colour_bg_button.draw(surface)
                l_retry_colour_bg_button.check_click()
            elif player1.correct == 10:
                w_colour_bg_button.draw(surface)
                w_overlay1_colour_bg_button.draw(surface)
                w_victory_colour_bg_button.draw(surface)


    elif game_state == STATE_INVENTORY:
        surface.fill((128, 0, 128))
        inv_back_button.draw(surface)
        inv_back_button.check_click()
        font = pygame.font.SysFont(None, 40)
        inventory_title = font.render("Inventory", True, (255, 255, 255))
        surface.blit(inventory_title, (surface.get_width() // 2 - 50, 20))
        y_offset = 100
        for item in player_inventory:
            item_text = font.render(item, True, (255, 255, 255))
            surface.blit(item_text, (50, y_offset))
            y_offset += 40
#    elif game_state == STATE_INTRO:
#        surface.fill(WHITE)
#        colour_intro_button.draw(surface)
#        if colour_intro_button.check_click() != None:
#            STATE_INTRO = "game"
#            f=2
    elif game_state == STATE_HISTORY:
        surface.fill((0, 255, 0))
        history_back_button.draw(surface)
        history_back_button.check_click()
        display_tasks2.update()
        display_tasks2.draw(surface)
    elif game_state == STATE_RUNE:
        surface.fill(PURPLE)
        y_offset = 50
        x_offset = 51
        i=0
        #for rune in rune_list:
        #    i+=1
        #    surface.blit(rune, (x_offset, y_offset))
        #    y_offset += 0
        #    x_offset += 56
        #    if i == 7:
        #        y_offset +=93
        #    if i==7:
        #        x_offset=100
        for rune in rune_list:
            i+=1
            surface.blit(rune, (x_offset, y_offset))
            x_offset+=56+51
            if i==7 or i==15 or i==23 or i==31:
                y_offset+=93+46
                x_offset=51
        rune_title_button.draw(surface)
        rune_back_button.draw(surface)
        rune_back_button.check_click()
        rune_11_button.check_click()
        rune_12_button.check_click()
        rune_13_button.check_click()
        rune_14_button.check_click()
        rune_15_button.check_click()
        rune_16_button.check_click()
        rune_17_button.check_click()
        rune_21_button.check_click()
        rune_22_button.check_click()
        rune_23_button.check_click()
        rune_24_button.check_click()
        rune_25_button.check_click()
        rune_26_button.check_click()
        rune_27_button.check_click()
        rune_31_button.check_click()
        rune_32_button.check_click()
        rune_33_button.check_click()
        rune_34_button.check_click()
        rune_35_button.check_click()
        rune_36_button.check_click()
        rune_37_button.check_click()
        rune_41_button.check_click()
        rune_42_button.check_click()
        rune_43_button.check_click()
        rune_44_button.check_click()
        rune_45_button.check_click()
        rune_46_button.check_click()
        rune_47_button.check_click()
        rune_51_button.check_click()
        rune_52_button.check_click()
        rune_53_button.check_click()
        rune_54_button.check_click()
        rune_55_button.check_click()
        rune_56_button.check_click()
        rune_57_button.check_click()
    elif game_state == STATE_RUNE_INFO:
        surface.fill(PURPLE)
        rune_name_button = Button(300, 50, 200, 50, (rune_name), None, PEACH, PEACH)
        rune_name_button.draw(surface)
        rune_info_back_button.draw(surface)
        rune_info_back_button.check_click()
        if rune_info == "11":
            surface.blit(rune_list[0],(375,150))
        elif rune_info == "12":
            surface.blit(rune_list[1], (375, 150))
        elif rune_info == "13":
            surface.blit(rune_list[2], (375, 150))
        elif rune_info == "14":
            surface.blit(rune_list[3], (375, 150))
        elif rune_info == "15":
            surface.blit(rune_list[4], (375, 150))
        elif rune_info == "16":
            surface.blit(rune_list[5], (375, 150))
        elif rune_info == "17":
            surface.blit(rune_list[6], (375, 150))
        elif rune_info == "21":
            surface.blit(rune_list[7], (375, 150))
        elif rune_info == "22":
            surface.blit(rune_list[8], (375, 150))
        elif rune_info == "23":
            surface.blit(rune_list[9], (375, 150))
        elif rune_info == "24":
            surface.blit(rune_list[10], (375, 150))
        elif rune_info == "25":
            surface.blit(rune_list[11], (375, 150))
        elif rune_info == "26":
            surface.blit(rune_list[12], (375, 150))
        elif rune_info == "27":
            surface.blit(rune_list[13], (375, 150))
        elif rune_info == "31":
            surface.blit(rune_list[15], (375, 150))
        elif rune_info == "32":
            surface.blit(rune_list[16], (375, 150))
        elif rune_info == "33":
            surface.blit(rune_list[17], (375, 150))
        elif rune_info == "34":
            surface.blit(rune_list[18], (375, 150))
        elif rune_info == "35":
            surface.blit(rune_list[19], (375, 150))
        elif rune_info == "36":
            surface.blit(rune_list[20], (375, 150))
        elif rune_info == "37":
            surface.blit(rune_list[21], (375, 150))
        elif rune_info == "41":
            surface.blit(rune_list[23], (375, 150))
        elif rune_info == "42":
            surface.blit(rune_list[24], (375, 150))
        elif rune_info == "43":
            surface.blit(rune_list[25], (375, 150))
        elif rune_info == "44":
            surface.blit(rune_list[26], (375, 150))
        elif rune_info == "45":
            surface.blit(rune_list[27], (375, 150))
        elif rune_info == "46":
            surface.blit(rune_list[28], (375, 150))
        elif rune_info == "47":
            surface.blit(rune_list[29], (375, 150))
        elif rune_info == "51":
            surface.blit(rune_list[31], (375, 150))
        elif rune_info == "52":
            surface.blit(rune_list[32], (375, 150))
        elif rune_info == "53":
            surface.blit(rune_list[33], (375, 150))
        elif rune_info == "54":
            surface.blit(rune_list[34], (375, 150))
        elif rune_info == "55":
            surface.blit(rune_list[35], (375, 150))
        elif rune_info == "56":
            surface.blit(rune_list[36], (375, 150))
        elif rune_info == "57":
            surface.blit(rune_list[37], (375, 150))
    pygame.display.update()
    clock.tick(60)

pygame.quit()
sys.exit()