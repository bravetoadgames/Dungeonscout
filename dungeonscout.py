import tkinter as tk
import random
import math
import os
from PIL import Image, ImageTk

# --- CONFIGURATION & BALANCE ---
SETTINGS = {
    "tile_size": 48,
    "map_width": 40,
    "map_height": 40,
    "fov_radius": 3,
    "max_hp": 30,
    "minimap_scale": 4,
    "anim_speed": 0.2, # Hoe hoger, hoe sneller het schuiven (0.1 - 0.5)
}

COLORS = {
    "status_bg": "#222",
    "mm_bg": "#111",
    "mm_wall": "#444",
    "mm_floor": "#888",
    "mm_exit": "#0F0",
}

# ==========================================
# 1. ENTITY HIERARCHY
# ==========================================

class Entity:
    def __init__(self, x, y, sprite_key):
        self.x = x
        self.y = y
        self.sprite_key = sprite_key
        # Visuele positie in pixels voor vloeiende animatie
        self.screen_x = x * SETTINGS["tile_size"]
        self.screen_y = y * SETTINGS["tile_size"]

    def update_animation(self):
        """Schuif de visuele positie naar de logische grid-positie."""
        target_x = self.x * SETTINGS["tile_size"]
        target_y = self.y * SETTINGS["tile_size"]
        
        self.screen_x += (target_x - self.screen_x) * SETTINGS["anim_speed"]
        self.screen_y += (target_y - self.screen_y) * SETTINGS["anim_speed"]

class Enemy(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, 'monster')

    def act(self, player, world):
        dist = math.sqrt((self.x - player.x)**2 + (self.y - player.y)**2)
        if 1 < dist < 8:
            dx = 1 if player.x > self.x else -1 if player.x < self.x else 0
            dy = 1 if player.y > self.y else -1 if player.y < self.y else 0
            nx, ny = self.x + dx, self.y + dy
            if world.is_walkable(nx, ny) and not (nx == player.x and ny == player.y):
                self.x, self.y = nx, ny

class Item(Entity):
    def __init__(self, x, y, item_type):
        mapping = {">": 'exit', "P": 'potion', "$": 'gold'}
        super().__init__(x, y, mapping.get(item_type, 'floor'))
        self.item_type = item_type

class Protagonist(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, 'player')
        self.hp = SETTINGS["max_hp"]
        self.gold = 0
        self.inventory = {"potions": 0}

    def use_potion(self):
        if self.inventory["potions"] > 0 and self.hp < SETTINGS["max_hp"]:
            self.inventory["potions"] -= 1
            heal = 15
            self.hp = min(SETTINGS["max_hp"], self.hp + heal)
            return f"Refreshing! +{heal} HP."
        return None

# ==========================================
# 2. GAME WORLD
# ==========================================

class GameWorld:
    def __init__(self):
        self.width = SETTINGS["map_width"]
        self.height = SETTINGS["map_height"]
        self.tiles = []
        self.discovered = []
        self.items = []
        self.enemies = []

    def generate_level(self):
        self._reset_level_data()
        rooms = self._generate_rooms(max_rooms=25)
        if rooms:
            self._place_exit(rooms[-1])
            self._populate_rooms(rooms[1:-1])
            return self._get_room_center(rooms[0])
        return (1, 1)

    def is_walkable(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x] == "."
        return False

    def update_fov(self, px, py):
        rad = SETTINGS["fov_radius"]
        for y in range(max(0, py - rad), min(self.height, py + rad + 1)):
            for x in range(max(0, px - rad), min(self.width, px + rad + 1)):
                if math.sqrt((py - y)**2 + (px - x)**2) <= rad:
                    self.discovered[y][x] = True

    def _create_tunnel(self, r1, r2):
        x1, y1 = self._get_room_center(r1)
        x2, y2 = self._get_room_center(r2)
        if random.random() > 0.5:
            self._dig_h_line(x1, x2, y1)
            self._dig_v_line(y1, y2, x2)
        else:
            self._dig_v_line(y1, y2, x1)
            self._dig_h_line(x1, x2, y2)

    def _dig_h_line(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1): self.tiles[y][x] = "."

    def _dig_v_line(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1): self.tiles[y][x] = "."

    def _dig_room(self, room):
        for y in range(room['y1'], room['y2']):
            for x in range(room['x1'], room['x2']):
                self.tiles[y][x] = "."

    def _generate_rooms(self, max_rooms):
        rooms = []
        for _ in range(max_rooms):
            rw, rh = random.randint(5, 10), random.randint(4, 7)
            rx, ry = random.randint(1, self.width - rw - 1), random.randint(1, self.height - rh - 1)
            new_room = {'x1': rx, 'y1': ry, 'x2': rx + rw, 'y2': ry + rh}
            if not any(new_room['x1'] <= r['x2'] and new_room['x2'] >= r['x1'] and 
                       new_room['y1'] <= r['y2'] and new_room['y2'] >= r['y1'] for r in rooms):
                self._dig_room(new_room)
                if rooms: self._create_tunnel(rooms[-1], new_room)
                rooms.append(new_room)
        return rooms

    def _get_room_center(self, room):
        return (room['x1'] + room['x2']) // 2, (room['y1'] + room['y2']) // 2

    def _place_exit(self, room):
        tx, ty = self._get_room_center(room)
        self.items.append(Item(tx, ty, ">"))

    def _populate_rooms(self, rooms):
        for room in rooms:
            cx, cy = self._get_room_center(room)
            if random.random() < 0.4:
                self.enemies.append(Enemy(cx, cy))
            
            for _ in range(random.randint(1, 3)):
                if random.random() < 0.6:
                    rx = random.randint(room['x1'] + 1, room['x2'] - 1)
                    ry = random.randint(room['y1'] + 1, room['y2'] - 1)
                    if not any(i.x == rx and i.y == ry for i in self.items):
                        self.items.append(Item(rx, ry, "$"))

            if random.random() < 0.3:
                rx = random.randint(room['x1'] + 1, room['x2'] - 1)
                ry = random.randint(room['y1'] + 1, room['y2'] - 1)
                if not any(i.x == rx and i.y == ry for i in self.items):
                    self.items.append(Item(rx, ry, "P"))

    def _reset_level_data(self):
        self.tiles = [["#" for _ in range(self.width)] for _ in range(self.height)]
        self.discovered = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.items = []
        self.enemies = []

# ==========================================
# 3. GAME LOGIC
# ==========================================

class GameLogic:
    def __init__(self, root):
        self.root = root
        self.root.title("DungeonScout - Smooth Edition")
        self.world = GameWorld()
        self.player = None
        self.level_num = 1
        self.message = ""
        self.game_state = "menu"
        self.sprites = {}
        self.player_visible_on_mm = True
        
        self.sprite_size = SETTINGS["tile_size"]
        self.SPRITE_MAP = {
            'player':  (0, 0), 'monster': (1, 0),
            'floor':   (0, 1), 'wall':    (1, 1), 'exit': (2, 1),
            'potion':  (0, 2), 'gold':    (1, 2),
        }

        self._setup_ui()
        self._load_assets()
        self.show_menu()
        self._animation_loop()

    def _animation_loop(self):
        """De centrale loop voor alle visuele updates."""
        if self.game_state == "playing":
            # Update animatie voor speler
            self.player.update_animation()
            # Update animatie voor alle vijanden
            for e in self.world.enemies:
                e.update_animation()
            self.render()
        
        self.root.after(16, self._animation_loop) # ~60 FPS

    def handle_input(self, event):
        key = event.keysym
        if key == 'Escape': self.root.destroy(); return
        if self.game_state == "menu" and key in ['Return', 'KP_Enter']:
            self.start_game()
        elif self.game_state == "gameover" and key in ['Return', 'KP_Enter']:
            self.show_menu()
        elif self.game_state == "playing":
            # Check of de speler al redelijk dicht bij zijn doel is (voorkomt 'spammen')
            dist = math.sqrt((self.player.x * self.sprite_size - self.player.screen_x)**2 + 
                             (self.player.y * self.sprite_size - self.player.screen_y)**2)
            if dist > 10: return # Wacht tot de animatie bijna klaar is

            k = key.lower()
            if k in ['w', 'a', 's', 'd']:
                dx, dy = {'w':(0,-1), 's':(0,1), 'a':(-1,0), 'd':(1,0)}[k]
                self.turn(dx, dy)
            elif k == 'h':
                res = self.player.use_potion()
                if res: self.message = res

    def start_game(self):
        self.game_state = "playing"
        px, py = self.world.generate_level()
        self.player = Protagonist(px, py)
        self.level_num = 1
        self.message = "Welcome to the Dungeon!"
        self.world.update_fov(px, py)
        self._toggle_minimap_player_blink()

    def turn(self, dx, dy):
        nx, ny = self.player.x + dx, self.player.y + dy
        enemy = next((e for e in self.world.enemies if e.x == nx and e.y == ny), None)
        
        if enemy:
            dmg = random.randint(4, 8)
            self.player.hp -= dmg
            self.world.enemies.remove(enemy)
            self.message = f"Combat! -{dmg} HP."
        elif self.world.is_walkable(nx, ny):
            self.player.x, self.player.y = nx, ny
            self._check_items()

        if self.player.hp <= 0:
            self.game_state = "gameover"
        else:
            for e in self.world.enemies: e.act(self.player, self.world)
            self.world.update_fov(self.player.x, self.player.y)

    def _check_items(self):
        item = next((i for i in self.world.items if i.x == self.player.x and i.y == self.player.y), None)
        if item:
            if item.item_type == ">":
                self.level_num += 1
                px, py = self.world.generate_level()
                self.player.x, self.player.y = px, py
                # Reset visuele positie direct om schuiven van vorige trap te voorkomen
                self.player.screen_x, self.player.screen_y = px*self.sprite_size, py*self.sprite_size
            elif item.item_type == "P":
                self.player.inventory["potions"] += 1
                self.message = "Found a potion!"
                self.world.items.remove(item)
            elif item.item_type == "$":
                val = random.randint(10, 25)
                self.player.gold += val
                self.message = f"Gold! (+{val})"
                self.world.items.remove(item)

    def render(self):
        self.canvas.delete("all")
        if self.game_state == "gameover":
            self.mm_canvas.place_forget()
            self.canvas.create_text(500, 350, text="GAME OVER", fill="red", font=("Courier", 40, "bold"))
            return

        ts = self.sprite_size
        c_w, c_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if c_w < 10: c_w, c_h = 1000, 750 # Fallback voor eerste frame

        # CAMERA gebaseerd op screen_x van de speler
        ox = self.player.screen_x - (c_w / 2) + (ts / 2)
        oy = self.player.screen_y - (c_h / 2) + (ts / 2)

        # Draw World
        for y in range(self.world.height):
            for x in range(self.world.width):
                if self.world.discovered[y][x]:
                    vx, vy = x*ts - ox, y*ts - oy
                    # Optimalisatie: teken alleen wat in beeld is
                    if -ts < vx < c_w and -ts < vy < c_h:
                        t_key = 'floor' if self.world.tiles[y][x] == "." else 'wall'
                        self.canvas.create_image(vx, vy, anchor="nw", image=self.sprites[t_key])
                        
                        item = next((i for i in self.world.items if i.x == x and i.y == y), None)
                        if item: self.canvas.create_image(vx, vy, anchor="nw", image=self.sprites[item.sprite_key])

        # Draw Enemies (gebruik screen_x)
        for e in self.world.enemies:
            if self.world.discovered[e.y][e.x]:
                self.canvas.create_image(e.screen_x - ox, e.screen_y - oy, anchor="nw", image=self.sprites[e.sprite_key])

        # Draw Player (altijd in het midden van de camera focus)
        self.canvas.create_image(self.player.screen_x - ox, self.player.screen_y - oy, anchor="nw", image=self.sprites['player'])
        
        stat = f"LVL: {self.level_num} | HP: {self.player.hp}/{SETTINGS['max_hp']} | POTIONS: {self.player.inventory['potions']} | GOLD: {self.player.gold} | {self.message}"
        self.status_label.config(text=stat, fg="white")
        self._render_minimap()

    def _load_assets(self):
        filename = "dungeon_sheet.png"
        if not os.path.exists(filename): return
        sheet = Image.open(filename).convert('RGBA')
        for name, (col, row) in self.SPRITE_MAP.items():
            img = sheet.crop((col*ts, row*ts, (col+1)*ts, (row+1)*ts))
            self.sprites[name] = ImageTk.PhotoImage(img)

    def _setup_ui(self):
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.status_label = tk.Label(self.root, font=("Courier", 12, "bold"), fg="white", bg=COLORS["status_bg"], pady=5)
        self.status_label.pack(fill=tk.X)
        self.mm_canvas = tk.Canvas(self.root, width=160, height=160, bg=COLORS["mm_bg"], highlightthickness=1)
        self.root.bind("<KeyPress>", self.handle_input)

    def _render_minimap(self):
        if self.game_state != "playing": return
        if not self.mm_canvas.winfo_ismapped(): 
            self.mm_canvas.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        
        self.mm_canvas.delete("all")
        sc = SETTINGS["minimap_scale"]
        
        # 1. Teken de ontdekte tegels (muren en vloeren)
        for y in range(self.world.height):
            for x in range(self.world.width):
                if self.world.discovered[y][x]:
                    color = COLORS["mm_floor"] if self.world.tiles[y][x] == "." else COLORS["mm_wall"]
                    self.mm_canvas.create_rectangle(x*sc, y*sc, x*sc+sc, y*sc+sc, fill=color, outline="")
        
        # 2. Teken de ontdekte items (Trap, Goud, Potions)
        for i in self.world.items:
            if self.world.discovered[i.y][i.x]:
                # De trap wordt groen, de rest geel
                color = COLORS["mm_exit"] if i.item_type == ">" else "yellow"
                self.mm_canvas.create_rectangle(i.x*sc, i.y*sc, i.x*sc+sc, i.y*sc+sc, fill=color, outline="")

        # 3. Teken de vijanden (rood)
        for e in self.world.enemies:
            if self.world.discovered[e.y][e.x]:
                self.mm_canvas.create_rectangle(e.x*sc, e.y*sc, e.x*sc+sc, e.y*sc+sc, fill="red", outline="")

        # 4. Teken de speler (blinkende cyan cursor)
        if self.player_visible_on_mm:
            self.mm_canvas.create_rectangle(self.player.x*sc, self.player.y*sc, self.player.x*sc+sc, self.player.y*sc+sc, fill="cyan", outline="")
            

    def _toggle_minimap_player_blink(self):
        if self.game_state == "playing":
            self.player_visible_on_mm = not self.player_visible_on_mm
            self.root.after(500, self._toggle_minimap_player_blink)

    def show_menu(self):
        self.game_state = "menu"
        self.canvas.delete("all")
        self.canvas.create_text(500, 340, text="DUNGEONSCOUT", fill="white", font=("Courier", 32, "bold"))
        self.canvas.create_text(500, 400, text="[ PRESS ENTER ]", fill="gray", font=("Courier", 18))

if __name__ == "__main__":
    ts = SETTINGS["tile_size"]
    root = tk.Tk()
    root.geometry("1000x750")
    game = GameLogic(root)
    root.mainloop()