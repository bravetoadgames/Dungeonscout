import tkinter as tk
import random, math, os
from PIL import Image, ImageTk

# --- CONFIG ---
S = {
    "ts": 48, "w": 40, "h": 40, "fov": 4, "hp": 40, "ms": 4, "speed": 0.4
}
C = {
    "st_bg": "#222", "mm_bg": "#111", "mm_w": "#444", "mm_f": "#888", "mm_e": "#0F0"
}

# ==========================================
# 1. ENTITIES
# ==========================================

class Entity:
    def __init__(self, x, y, sprite_key):
        self.x, self.y = x, y
        self.sprite_key = sprite_key
        self.sx, self.sy = x * S["ts"], y * S["ts"]

    def update_anim(self):
        self.sx += (self.x * S["ts"] - self.sx) * S["speed"]
        self.sy += (self.y * S["ts"] - self.sy) * S["speed"]

    @property
    def pos(self): return (self.x, self.y)

class Enemy(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, 'monster')
        self.hp = 25
        self.stunned = False

    def take_dmg(self, amount, world, dx, dy):
        self.hp -= amount
        self.stunned = True
        nx, ny = self.x + dx, self.y + dy
        if world.is_walkable(nx, ny):
            self.x, self.y = nx, ny 
            return f"BOOM! Enemy pushed back ({self.hp} HP)"
        else:
            self.hp -= 5 
            return f"CRUNCH! Wall slam! ({self.hp} HP)"
        
    def act(self, p, world):
        if self.stunned:
            self.stunned = False
            return
            
        dist = math.hypot(self.x - p.x, self.y - p.y)
        if 1 < dist < 8:
            dx = 1 if p.x > self.x else -1 if p.x < self.x else 0
            dy = 1 if p.y > self.y else -1 if p.y < self.y else 0
            if world.is_walkable(self.x + dx, self.y + dy) and (self.x+dx, self.y+dy) != p.pos:
                self.x += dx; self.y += dy

class Item(Entity):
    def __init__(self, x, y, char):
        mapping = {">": 'exit', "P": 'potion', "$": 'gold'}
        super().__init__(x, y, mapping.get(char, 'floor'))
        self.char = char

class Protagonist(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, 'player')
        self.hp, self.gold, self.pots = S["hp"], 0, 0

# ==========================================
# 2. GAME WORLD
# ==========================================

class GameWorld:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tiles = [["#" for _ in range(S["w"])] for _ in range(S["h"])]
        self.discovered = [[False for _ in range(S["w"])] for _ in range(S["h"])]
        self.items, self.enemies = [], []

    def is_walkable(self, x, y):
        return 0 <= x < S["w"] and 0 <= y < S["h"] and self.tiles[y][x] == "."

    def generate(self):
        self.reset()
        rooms = []
        for _ in range(25):
            w, h = random.randint(5,10), random.randint(4,7)
            x, y = random.randint(1, S["w"]-w-1), random.randint(1, S["h"]-h-1)
            new = {'x1':x, 'y1':y, 'x2':x+w, 'y2':y+h, 'c':(x+w//2, y+h//2)}
            if not any(new['x1']<=r['x2'] and new['x2']>=r['x1'] and new['y1']<=r['y2'] and new['y2']>=r['y1'] for r in rooms):
                for ty in range(y, y+h):
                    for tx in range(x, x+w): self.tiles[ty][tx] = "."
                if rooms:
                    prev_c = rooms[-1]['c']
                    self._tunnel(prev_c[0], prev_c[1], new['c'][0], new['c'][1])
                rooms.append(new)
        
        # WILLEKEURIGE TRAP LOCATIE
        lr = rooms[-1]
        self.items.append(Item(random.randint(lr['x1'], lr['x2']-1), random.randint(lr['y1'], lr['y2']-1), ">"))
        
        self._populate(rooms[1:-1])
        
        # WILLEKEURIGE START LOCATIE
        sr = rooms[0]
        return (random.randint(sr['x1'], sr['x2']-1), random.randint(sr['y1'], sr['y2']-1))

    def _tunnel(self, x1, y1, x2, y2):
        for x in range(min(x1, x2), max(x1, x2) + 1): self.tiles[y1][x] = "."
        for y in range(min(y1, y2), max(y1, y2) + 1): self.tiles[y][x2] = "."

    def _populate(self, rooms):
        for r in rooms:
            if random.random() < 0.7: 
                self.enemies.append(Enemy(*r['c']))
            for char, prob in [("$", 0.8), ("P", 0.5)]:
                max_items = 4 if char == "$" else 2
                for _ in range(max_items):
                    if random.random() < prob:
                        rx, ry = random.randint(r['x1']+1, r['x2']-1), random.randint(r['y1']+1, r['y2']-1)
                        if not any(i.pos == (rx, ry) for i in self.items): 
                            self.items.append(Item(rx, ry, char))

# ==========================================
# 3. LOGIC & UI
# ==========================================

class GameLogic:
    def __init__(self, root):
        self.root = root
        self.world, self.sprites = GameWorld(), {}
        self.state, self.level, self.msg = "menu", 1, ""
        self.blink, self.shake = True, 0
        self._setup_ui()
        self._load_assets()
        self.show_menu()
        self._loop()

    def _setup_ui(self):
        self.can = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.can.pack(fill=tk.BOTH, expand=True)
        self.stat = tk.Label(self.root, font=("Courier", 12, "bold"), bg=C["st_bg"], fg="white", pady=10)
        self.stat.pack(fill=tk.X)
        self.mm = tk.Canvas(self.root, width=160, height=160, bg=C["mm_bg"], highlightthickness=1)
        self.root.bind("<KeyPress>", self.input)

    def _load_assets(self):
        if not os.path.exists("dungeon_sheet.png"): return
        sheet = Image.open("dungeon_sheet.png").convert('RGBA')
        m = {'player':(0,0), 'monster':(1,0), 'floor':(0,1), 'wall':(1,1), 'exit':(2,1), 'potion':(0,2), 'gold':(1,2)}
        for k, (c, r) in m.items():
            img = sheet.crop((c*S["ts"], r*S["ts"], (c+1)*S["ts"], (r+1)*S["ts"]))
            self.sprites[k] = ImageTk.PhotoImage(img)

    def start(self):
        self.state, self.level = "playing", 1
        self.shake = 0 # Camera reset
        self.player = Protagonist(*self.world.generate())
        self.msg = "Explore the depths!"
        self._update_fov()
        self.render()
        self._blink_loop()

    def input(self, e):
        if e.keysym == 'Escape': self.root.destroy()
        if self.state != "playing":
            if e.keysym in ['Return', 'KP_Enter']: 
                if self.state == "menu" or self.state == "gameover": self.start()
                else: self.show_menu()
            return

        if math.hypot(self.player.x*S["ts"] - self.player.sx, self.player.y*S["ts"] - self.player.sy) > 10: return
        
        k = e.keysym.lower()
        if k in 'wasd':
            self.turn(*{'w':(0,-1), 's':(0,1), 'a':(-1,0), 'd':(1,0)}[k])
        elif k == 'h' and self.player.pots > 0:
            self.player.pots -= 1; self.player.hp = min(S["hp"], self.player.hp + 15)
            self.msg = "Potion used: +15 Health"

    def turn(self, dx, dy):
        nx, ny = self.player.x + dx, self.player.y + dy
        target = next((e for e in self.world.enemies if e.pos == (nx, ny)), None)
        
        player_hit_enemy = False
        if target:
            player_hit_enemy = True
            damage = random.randint(8, 14)
            self.msg = target.take_dmg(damage, self.world, dx, dy)
            if target.hp <= 0:
                self.world.enemies.remove(target)
                self.player.gold += 5
                self.msg = "VICTORY! Enemy defeated (+5 Gold)"
        elif self.world.is_walkable(nx, ny):
            self.player.x, self.player.y = nx, ny
            self._check_items()

        for e in self.world.enemies:
            dist = math.hypot(e.x - self.player.x, e.y - self.player.y)
            if dist < 1.1 and not e.stunned:
                dmg = random.randint(3, 6)
                self.player.hp -= dmg
                if not player_hit_enemy: self.msg = f"OUCH! Enemy hits you for {dmg}"
                self.shake = 12
                self._flash_red()
            else:
                e.act(self.player, self.world)

        if self.player.hp <= 0:
            self.player.hp = 0
            self.state = "gameover"
            self.msg = "YOU DIED!"
            self.render()
            return 
        
        self._update_fov()

    def _flash_red(self):
        self.stat.config(bg="red")
        self.root.after(100, lambda: self.stat.config(bg=C["st_bg"]))

    def _check_items(self):
        i = next((i for i in self.world.items if i.pos == self.player.pos), None)
        if not i: return
        if i.char == ">":
            self.level += 1
            new_pos = self.world.generate()
            self.player.x, self.player.y = new_pos
            self.player.sx, self.player.sy = self.player.x*S["ts"], self.player.y*S["ts"]
            self.msg = f"Entering level {self.level}..."
        else:
            if i.char == "P": self.player.pots += 1; self.msg = "Found a Potion!"
            else: val = random.randint(10,25); self.player.gold += val; self.msg = f"Found {val} Gold!"
            self.world.items.remove(i)

    def _update_fov(self):
        px, py = self.player.pos
        for y in range(max(0, py-S["fov"]), min(S["h"], py+S["fov"]+1)):
            for x in range(max(0, px-S["fov"]), min(S["w"], px+S["fov"]+1)):
                if math.hypot(px-x, py-y) <= S["fov"]: self.world.discovered[y][x] = True

    def _loop(self):
        if self.state == "playing" and hasattr(self, 'player'):
            self.player.update_anim()
            for e in self.world.enemies: e.update_anim()
            if self.shake > 0: self.shake -= 1
            self.render()
        self.root.after(16, self._loop)

    def render(self):
        self.can.delete("all")
        if self.state == "gameover":
            self.mm.place_forget()
            self.can.create_rectangle(0, 0, 2000, 2000, fill="black")
            self.can.create_text(500, 320, text="GAME OVER", fill="red", font=("Courier", 50, "bold"))
            self.can.create_text(500, 400, text=f"Level reached: {self.level} | Gold: {self.player.gold}", fill="white", font=("Courier", 20))
            self.can.create_text(500, 480, text="[ PRESS ENTER TO RESTART ]", fill="gray", font=("Courier", 15))
            self.stat.config(text=f"Level: {self.level} | Health: 0/{S['hp']} | Potions: {self.player.pots} | Gold: {self.player.gold} | {self.msg}", bg="maroon")
            return

        ts, (cw, ch) = S["ts"], (self.can.winfo_width(), self.can.winfo_height())
        if cw < 10: cw, ch = 1000, 750
        
        sx = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        sy = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        ox, oy = self.player.sx - cw/2 + ts/2 + sx, self.player.sy - ch/2 + ts/2 + sy

        for y in range(S["h"]):
            for x in range(S["w"]):
                if self.world.discovered[y][x]:
                    vx, vy = x*ts - ox, y*ts - oy
                    if -ts < vx < cw and -ts < vy < ch:
                        self.can.create_image(vx, vy, anchor="nw", image=self.sprites['floor' if self.world.tiles[y][x]=="." else 'wall'])
                        it = next((i for i in self.world.items if i.pos == (x,y)), None)
                        if it: self.can.create_image(vx, vy, anchor="nw", image=self.sprites[it.sprite_key])

        for e in self.world.enemies:
            if self.world.discovered[e.y][e.x]:
                self.can.create_image(e.sx - ox, e.sy - oy, anchor="nw", image=self.sprites['monster'])

        self.can.create_image(self.player.sx - ox, self.player.sy - oy, anchor="nw", image=self.sprites['player'])
        
        display_hp = max(0, self.player.hp)
        self.stat.config(text=f"Level: {self.level} | Health: {display_hp}/{S['hp']} | Potions: {self.player.pots} | Gold: {self.player.gold} | {self.msg}", bg=C["st_bg"])
        self._render_mm()

    def _render_mm(self):
        self.mm.delete("all")
        if not self.mm.winfo_ismapped(): self.mm.place(relx=1, rely=0, anchor="ne", x=-10, y=10)
        ms = S["ms"]
        for y in range(S["h"]):
            for x in range(S["w"]):
                if self.world.discovered[y][x]:
                    c = C["mm_f"] if self.world.tiles[y][x] == "." else C["mm_w"]
                    self.mm.create_rectangle(x*ms, y*ms, (x+1)*ms, (y+1)*ms, fill=c, outline="")
        for i in self.world.items:
            if self.world.discovered[i.y][i.x]:
                self.mm.create_rectangle(i.x*ms, i.y*ms, (i.x+1)*ms, (i.y+1)*ms, fill=C["mm_e"] if i.char==">" else "yellow", outline="")
        if self.blink: self.mm.create_rectangle(self.player.x*ms, self.player.y*ms, (self.player.x+1)*ms, (self.player.y+1)*ms, fill="cyan", outline="")

    def _blink_loop(self):
        if self.state == "playing":
            self.blink = not self.blink
            self.root.after(500, self._blink_loop)

    def show_menu(self):
        self.state = "menu"
        self.can.delete("all")
        self.mm.place_forget()
        self.can.create_text(500, 340, text="DUNGEONSCOUT", fill="white", font=("Courier", 32, "bold"))
        self.can.create_text(500, 400, text="[ ENTER TO START ]", fill="gray", font=("Courier", 18))

if __name__ == "__main__":
    root = tk.Tk()
    root.title("DungeonScout")
    root.geometry("1000x750")
    GameLogic(root)
    root.mainloop()