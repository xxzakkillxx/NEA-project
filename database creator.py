import sqlite3
import json
import hashlib
import os

monsters = []
conn = sqlite3.connect('game_data.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS Monsters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    min_level INTEGER,
    max_level INTEGER,
    base_hp INTEGER,
    base_damage INTEGER,
    skills_json TEXT,
    general_element TEXT,
    rarity TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    salt TEXT,
    role TEXT
)
''')
def create_default_users():
    default_users = [
        {"username": "zak",
        "password": "password",
        "role": "admin"},
        {"username": "zak1",
        "password": "password1",
        "role": "user"}]

    for user in default_users:
        cursor.execute("SELECT * FROM users WHERE username = ?", (user["username"],))
        if cursor.fetchone() is None:
            salt = os.urandom(16).hex()
            hashed_password = hashlib.sha256((user["password"] + salt).encode()).hexdigest()
            cursor.execute(
                "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
                (user["username"], hashed_password, salt, user["role"]))
create_default_users()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        message TEXT,
        timestamp TEXT
    )
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    user_type TEXT,
    skill_type TEXT,
    damage INTEGER,
    cost INTEGER,
    element TEXT,
    duration INTEGER,
    effects_json TEXT,
    rarity TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    min_level INTEGER,
    general_element TEXT,
    rarity TEXT,
    uses INTEGER,
    cost INTEGER,
    effect_json TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS NPCs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    dialogue TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS GameState (
    id INTEGER PRIMARY KEY,
    current_level INTEGER,
    current_map TEXT,
    story_flag TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Variables (
    id INTEGER PRIMARY KEY,
    name TEXT,
    int_val INTEGER,
    str_val TEXT
)
''')
conn.commit()
conn.close()

def get_variable(name, default=None):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM Variables WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result else default

def set_variable(name, value):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    value_json = json.dumps(value)
    cursor.execute('''
        INSERT INTO Variables (name, value)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET value = excluded.value
    ''', (name, value_json))
    conn.commit()
    conn.close()

def add_skill(name, skill_type, damage, cost, element, duration, effects_list, user_type, rarity):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    effects_json = json.dumps(effects_list)
    cursor.execute('''
    INSERT INTO Skills (name, skill_type, user_type, damage, cost, element, duration, effects_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, skill_type, user_type, damage, cost, element, duration, effects_json))
    conn.commit()
    conn.close()
add_skill("dash","mobility",None,20,None,1,([{"type":"invincibility", "duration":1.0},{"type": "speed_boost", "multiplier": 2.0, "duration": 1.0}]),"player", "common")

def add_monster(name, min_level, max_level, base_hp, base_damage, skills, general_element, rarity):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    skills_json = json.dumps(skills)
    if name in monsters:
        pass
    else:
        monsters.append(name)
        cursor.execute('''
        INSERT INTO Monsters (name, min_level, max_level, base_hp, base_damage, skills_json, general_element, rarity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, min_level, max_level, base_hp, base_damage, skills_json, general_element, rarity))
    conn.commit()
    conn.close()


add_monster("green slime",1,5,10,1,None,None,"common")
add_monster("poison slime",5,15,15,5,None,None,"common")
add_monster("metalic slime",15,25,30,25,"jugernaut","earth","common")
add_monster("goblin",25,50,90,70,"death cry","nature","common")
add_monster("skeleton",50,75,200,160,None,"dark","common")
add_monster("wolf",75,100,500,300,"scratch",None,"common")
add_monster("Bandit",100,120,1200,600,None,None,"uncommon")
add_monster("zombie",120,145,2500,1100,"devour","dark","uncommon")
add_monster("spider",145,170,5000,2000,"web bind","nature","uncommon")
add_monster("cultist",170,200,9500,3500,"blood sacrifice","dark","uncommon")
add_monster("orc",200,225,17000,6000,"rampage","nature","uncommon")
add_monster("wraith",225,250,30000,10000,"possession","dark","uncommon")
add_monster("troll",250,300,60000,20000,"regeneration","dark","rare")
add_monster("demon",300,350,80000,35000,"evil eye","dark","rare")
add_monster("golem",300,350,140000,65000,"rage mode",None,"rare")
add_monster("vampire",350,400,220000,100000,"blood thirst","dark","rare")
add_monster("wyvern",400,450,380000,150000,"weaker dragons breath","nature","rare")
add_monster("lich",450,500,500000,200000,"cursed touch","dark","rare")
add_monster("death knight",500,600,700000,300000,"death aura","dark","mythic")
add_monster("behemoth",600,700,1000000,400000,"energy blast","natural","mythic")
add_monster("hydra",700,800,1300000,600000,"elemental burst",None,"mythic")
add_monster("dragon",800,900,2000000,850000,"dragons breath","natural","mythic")
add_monster("archdemon",900,1000,3000000,1300000,"ruller","dark","anchient")

def add_item(name, min_level, general_element, rarity, cost, uses, type, effect):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    effect_json = json.dumps(effect)
    cursor.execute('''
    INSERT INTO Items (name, min_level, general_element, rarity, cost, uses, type, effect_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, min_level, general_element, rarity, cost, uses, type, effect_json))
    conn.commit()
    conn.close()
add_item("wooden sword",1,None,"common",10,None,"weapon",([{"type":"damage", "extra damage points":1.0}]))
print(monsters)