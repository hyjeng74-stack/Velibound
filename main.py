import math
import random
import sys
import json
from collections import deque
from pathlib import Path
import pygame

#-- 새로 붙인 모듈들 --
from engine.projectiles import Projectiles as Bullet, LaserBeam as Laser
from engine.effects import add_or_stack_poison, serialize_effects, restore_effects, PoisonEffect
from engine.schema import load_levels_v1_or_fallback, load_drops_v1_or_default, merge_options
from engine.events import EventBus
from engine.actions import Weapon
from engine.content import load_weapons, load_relics

from ai.fsm import RangedFSM, RangedConfig
from ai.bt import BossBT
from spawner.director import Director
from generators.mapgen import generate_level_set
from meta.progression import load_meta, save_meta, on_event, shop_lineup, patch_shop

#------
# 전역 설정/상수
#------
WIDTH, HEIGHT = 24, 28
TILE = 32
SCREEN_W, SCREEN_H = WIDTH*TILE, HEIGHT*TILE
FPS = 60

SAVE_DIR = Path(".")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
SAVE_SLOTS = {
    1: SAVE_DIR / "save_slo1.json",
    2: SAVE_DIR / "save_slot2.json",
    3: SAVE_DIR / "save_slot3.json",
}
OPTIONS_PATH = SAVE_DIR / "options.json"
LEVELS_JSON = DATA_DIR / "levels.json"
DROPS_JSON = DATA_DIR / "drops.json"
META_PATH = Path("meta.json")

#맵 생성기 자동 사용(레벨 JSON 이 없으면 사용
AUTO_MAPGEN = not LEVELS_JSON.exists()

DEFAULT_OPTIONS = {
    "difficulty": "Normal",
    "fov_radius": 180,
    "screenshake": True,
    "keymap": {
        "pause":    [pygame.K_ESCAPE],
        "up":   [pygame.K_w, pygame.K_UP],
        "down": [pygame.K_s, pygame.K_DOWN],
        "left": [pygame.K_a, pygame.K_LEFT],
        "right": [pygame.K_d, pygame.K_RIGHT],
        "attack": [pygame.K_SPACE],
        "dash": [pygame.K_LSHIFT, pygame.K_RSHIFT],
        "shop": [pygame.K_e],
        "skill1": [pygame.K_q],
    },
}

DIFF_SCALE = {
    "Easy": {"enemy_hp": 0.8, "enemy_dmg":0.7, "boss_hp": 0.85},
    "Normal": {"enemy_hp": 1.0, "enemy_dmg": 1.0, "boss_hp": 1.0},
    "Hard": {"enemy_hp": 1.3, "enemy_dmg": 1.25, "boss_hp":1.35},
}

COLORS = {
    "bg": (16, 16, 22),
    "wall": (64, 66, 88),
    "floor": (34, 36, 46),
    "water": (28, 65, 120),
    "goal": (36, 130, 49),
    "potion": (200, 70, 70),
    "player": (230, 230, 70),
    "enemy": (220, 90, 200),
    "ranged": (220, 150, 70),
    "boss": (230, 60, 60),
    "bullet": (230, 60, 60),
    "hurt": (255, 140, 140),
    "hud_text": (240, 240, 240),
    "hud_back": (0, 0, 0),
    "key": (230, 200, 40),
    "door": (120, 80, 40),
    "arena": (150, 110, 60),
    "coin": (230, 220, 120),
    "shop": (120, 220, 120),
    "poison_glow": (80, 200, 120),
    "elite": (245, 210, 90),
    "laser_warn": (255, 210, 90),
    "laser_beam": (255, 70, 70),
}

#문자 맵 전설:
# #: 벽, .: 바닥, ~: 물(느림), G: 출구
# E: 근접 적, e: 원거리 적, B: 보스
# @: 플레이어 시작, K: 열쇠, D: 문, C: 코인
# A: 아레나 도어, T: 트리거, S: 상점
LEVELS_FALLBACK = [
    [
        "########################",
        "#..E.....P....C....~~.G#",
        "#..####....##..~~......#",
        "#..#..#....##.....A....#",
        "#..#..#..T.....E.......#",
        "#..#..####..####...A...#",
        "#..#....D...#..........#",
        "#..#....P...#..P...S...#",
        "#..####..#####.###.....#",
        "#......E......#.....C..#",
        "#.#######.##..#..#.....#",
        "#.@......E#..P#..#.....#",
        "#...~~......###..#.....#",
        "#....~~..C....K..#.....#",
        "########################",
        "#......................#",
        "#......................#",
        "########################",
    ],
    [
        "########################",
        "#..e..C.....~~..C....G.#",
        "#..####....##..~~......#",
        "#..#..#....##.....A....#",
        "#..#..#..T......e......#",
        "#..#..####..####...A...#",
        "#..#........#..K.......#",
        "#..#....P...#..D...S...#",
        "#..####..#####.###.....#",
        "#......e......#.....C..#",
        "#.#######.##..#..#.....#",
        "#.@...........#..#.....#",
        "#...~~......###..#.....#",
        "#....~~..C.............#",
        "########################",
        "#......................#",
        "#......................#",
        "########################",
    ],
    [
        "########################",
        "#......................#",
        "#.........A....A.......#",
        "#.........A..B.A.......#",
        "#.........A....A.......#",
        "#......................#",
        "#......................#",
        "#....S.................#",
        "#..................G...#",
        "#......................#",
        "########################",
        "#......................#",
        "#......................#",
        "#...........@..........#",
        "#......................#",
        "#......................#",
        "#......................#",
        "########################",
    ],
] 

# -------
#유틸
# -------
def clamp(v, lo, hi): return max(lo, min(hi, v))
def length(vx, vy): return math.hypot(vx, vy)
def normalize(vx, vy):
    l = length(vx, vy)
    if l == 0: return 0, 0
    return vx/1, vy/1
def rect_from_tile(tx, ty): return pygame.Rect(tx*TILE, ty*TILE, TILE, TILE)

def load_json_safe(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def choose_levels_data():
    if AUTO_MAPGEN:
        #　철차 생성 3층 세트
        return generate_level_set(n=3, seed=1234)
    return load_levels_v1_or_fallback(LEVELS_JSON, LEVELS_FALLBACK)

DEFAULT_DROPS = {
    "coin": {"enemy": 0.40, "ranged": 0.45, "boss": 0.85},
    "potion": {"enemy": 0.08, "ranged": 0.08, "boss": 0.20},
    "key": {"enemy": 0.02, "ranged": 0.04, "boss": 0.10},
}
def load_drops_data():
    return load_drops_v1_or_default(DROPS_JSON, DEFAULT_DROPS)

def key_name(k):
    try: return pygame.key.name(k).upper()
    except: return str(k)

ACTION_ORDER = ["pause", "up", "down", "left", "right", "attack", "dash", "shop", "skill1"]
ACTION_LABEL = {
    "pasue":"Pause", "up":"Move Up", "down":"Move Down", "left":"Move Left", 
    "right":"Move Right", "attack":"Attack", "dash":"Dash", "shop":"Shop", 
    "skill1":"Use Skill",
}
def is_down(keys, keymap, action):
    return any(0 <= k < len(keys) and keys[k] for k in keymap[action])

# ===========
# 엔티티
# ===========
class Player:
    def __init__(self,x, y):
        self.r = TILE//2 - 4
        self.rect = pygame.Rect(x, y, self.r*2, self.r*2)
        self.base_speed = 150.0
        self.speed = self.base_speed
        self.hp_max = 8
        self.hp = self.hp_max
        self.base_cool = 0.5
        self.attack_range = TILE * 0.9
        self.attack_cool = self.base_cool
        self.cool_timer = 0.0
        self.i_frames = 0.0
        self.i_frames_max = 0.6
        self.keys = 0
        self.coins = 0
        # --- 대시/ 스테미나 ---
        self.stamin_max = 100.0
        self.stamin = self.stamin_max
        self.stamina_regen = 28.0
        self.dash_cost = 36.0
        self.dash_cd = 0.65
        self.dash_cd_timer = 0.0
        self.dash_time = 0.18
        self.dash_tleft = 0.0
        self.dashing = False
        self.dash_speed_mult = 3.3
        self.dash_i_frames = 0.20
        self.dash_dir = (1.0, 0.0)
        self.last_dir = (1.0, 0.0)
        # --- 무기/유물 ---
        self.weapon = None
        self.relics = []
        self.poison_bonus = 0.0

    def center(self): return self.rect.centerx, self.rect.centery
    def can_attack(self): return self.cool_timer <= 0.0
    def attack(self): self.cool_timer = self.attack_cool

    def update_timers(self, dt):
        if self.cool_timer > 0: self.cool_timer -= dt
        if self.i_frames > 0: self.i_frames -= dt
        if self.dash_cd_timer > 0: self.dash_cd_timer -= dt
        if not self.dashing:
            self.stamin = clamp(self.stamina + self.stamina_regen*dt, 0, self.stamina_max)

    def move(self, dx, dy, dt, colliders, slow=False, custom_speed=None):
        spd = (custom_speed if custom_speed is not None else self.speed) * (0.6 if slow else 1.0)
        vx, vy = normalize(dx, dy)
        mvx, mvy = vx*spd*dt, vy*spd*dt
        self.rect.x += int(mvx)
        for w in colliders:
            if self.rect.colliderect(w):
                self.rect.right = min(self.rect.right, w.left) if mvx>0 else self.rect.right
                self.rect.left = max(self.rect.left, w.right) if mvx<0 else self.rect.left
        self.rect.y += int(mvy)
        for w in colliders:
            if self.rect.colliderect(w):
                self.rect.bottom = min(self.rect.bottom, w.top) if mvy>0 else self.rect.bottom
                self.rect.top = max(self.rect.top, w.bottom) if mvy<0 else self.rect.top
    
    def start_dash(self, dirx, diry):
        if self.sashing or self.sash_xd_timer > 0: return False
        if self.stamina < self.dash_cost: return False
        dx, dy = normalize(dirx, diry)
        if dx == 0 and dy == 0:
            dx, dy = self.last_dir
        if dx == 0 and dy == 0:
            return False
        self.dashing = True
        self.dash_dir = (dx, dy)
        self.dash_tleft = self.dash_time
        self.stamina -= self.dash_cost
        self.dash_cd_timer = self.dash_cd
        self.i_frames = max(self.i_frames, self.dah_i_frames)
        return True
    
    def update_dash(self, dt, colliders):
        if not self.dashing: return
        spd = self.speed * self.dash_speed_mult
        self.move(self.dash_dir[0], self.dash_dir[1], dt, colliders, slow=False, custom_speed=spd)
        self.dash_tleft -= dt
        if self.dash_tleft <= 0:
            self.dashing = False

    def hurt(self, dmg):
        if self.i_frames>0: return
        self.hp = max(0, self.hp - dmg)
        self.i_frames = self.i_frames_max

class Enemy:
    def __init__(self, x, y, scale_hp=1.0, scale_dmg=1.0, elite=False, mods=None):
        self.rect = pygame.Rect(x, y, TILE-8, TILE-8)
        self.speed = 90.0
        self.hp = int(round(3*scale_hp))
        self.dir_timer = 0.0
        self.rv = (0, 0)
        self.attack_timer = 0.0
        self.dmg = max(1, int(round(1*scale_dmg)))
        # BFS
        self.path = []
        self.path_timer = 0.0
        self.path_cd = 0.4
        # elite
        self.elite = elite
        self.mods = mods or []
        self.aura_timer = 0.0
        self.regen_timer = 0.0
        self.dead_drop_done = False
        # effect
        self.effects = []

    def alive(self): return self.hp>0
    def center(self): return self.rect.centerx, self.rect.centery
    def add_effect(self, effect):
        self.effects.append(effect); effect.on_apply(self)
    def tick_effects(self, dt):
        kept = []
        for eff in self.effects:
            eff.update(self, dt)
            if not eff.done: kept.append(eff)
        self.effects = kept
    
    def apply_mods(self):
        for m in self.mods:
            if m == "tanky": self.hp = int(self.hp*1.6)
            elif m == "haste": self.speed *= 1.25

    def ai(self, player_pos, walls, dt, world=None):
        px, py = player_pos
        ex, ey = self.center()
        vx, vy = px-ex, py-ey
        dist = length(vx, vy)
        chase_radius = TILE*6.0

        if world is not None and dist < chase_radius:
            self.path_timer -= dt
            if self.path_timer <= 0:
                self.path_timer = self.path_cd
                self.path = bfs_path(world, self.rect, world.player.rect)
            dx, dy = 0.0, 0.0
            if self.path:
                tx, ty = self.path[0]
                cx, cy = tx*TILE + TILE//2, ty*TILE + TILE//2
                dx, dy = normalize(cx - ex, cy - ey)
                if length(cx-ex, ey-ey) < 4: self.path.pop(0)
            else: 
                dx, dy = normalize(vx, vy)
        else:
            wander_change = 1.2
            self.dir_timer -= dt
            if self.dir_timer<=0:
                self.dir_timer = wander_change + random.random()*0.8
                a = random.random()*math.tau
                self.rv=(math.vos(a), math.sin(a))
            dx, dy = self.rv

        # 엘리트 오라/재생
        if self.elite and "aura" in self.mods:
            if dist <= TILE*1.1:
                world.player.hurt(1)
        if self.elite and "regen" in self.mods:
            self.regen_timer += dt
            if self.regen_timer >= 1.2:
                self.regen_timer = 0.0
                self.hp += 1
            
        mvx, mvy = dx*self.speed*dt, dy*self.speed*dt
        self.rect.x += int(mvx)
        for w in walls + (world.doors if world else[]) + ((world.arena_doors if (world and world.arena_acive) else [])):
            if self.rect.colliderect(w):
                self.rect.right = min(self.rect.right, w.left) if mvx>0 else self.rect.right
                self.rect.left = max(self.rect.left, w.right) if mvx<0 else self.rect.left
        self.rect.y += int(mvy)
        for w in walls + (world.doors if world else []) + ((world.arena_doors if (world and world.arena_active) else [])):
            if self.rect.colliderect(w):
                self.rect.bottom = min(self.rect.bottom, w.top) if mvy>0 else self.rect.bottom
                self.rect.top = max(self.rect.top, w.bottom) if mvy<0 else self.rect.top

        if self.attack_timer>0: self.attack_timer -= dt

    def try_attack(self, player: 'Player'):
        if self.attack_timer>0: return False
        ex, ey = self.center()
        px, py = player.center()
        if length(px-ex, py-ey) <= TILE*0.8:
            player.hurt(self.dmg)
            self.attack_timer = 0.8
            return True
        return False
    
class RangedEnemy:
    def __init__(self, x, y, scale_hp=1.0, elite=False, mods=None):
        self.rect = pygame.Rect(x, y, TILE-10, TILE-10)
        self.speed = 70.0
        self.hp = max(1, int(round(2*scale_hp)))
        self.shoot_cd = 1.6
        self.elite = elite
        self.mods = mods or []
        self.dead_drop_done = False
        # effects
        self.effects = []
        # FSM
        self.brain = RangedFSM(RangedConfig(shoot_cooldown=self.shoot_cd))
        self._world_ref = None
        self.apply_mods()

    def set_world(self, world): self._world_ref = world
    
    def add_effect(self, effect):
        self.effect.append(effect); effect.on_apply(self)
    def tick_effects(self, dt):
        kept = []
        for eff in self.effects:
            eff.update(self, dt)
            if not eff.done: kept.append(eff)
        self.effects = kept

    def apply_mods(self):
        for m in self.mods:
            if m == "tanky": self.hp = int(self.hp*1.6)
            elif m == "haste": self.speed *= 1.25
            elif m == "rapid": pass # FSM이 발사 쿨로 대체

    def alive(self): return self.hp>0
    def center(self): return self.rect.centerx, self.rect.centery

    def ai(self, player_pos, walls, dt, bullets):
        # FSM 이 기반 이동/사격
        if not self._world_ref:
            return
        dx, dy, shoot = self.brain.update(self, world=self._world_ref, dt=dt)
        mvx, mvy = dx*self.speed*dt, dy*self.speed*dt
        self.rect.x += int(mvx)
        for w in walls:
            if self.rect.colliderect(w):
                self.rect.right = min(self.rect.right, w.left) if mvx>0 else self.rect.right
                self.rect.left = max(self.rect.left, w.right) if mvx<0 else self.rect.left
        self.rect.y += int(mvx)
        for w in walls:
            if self.rect.colliderect(w):
                self.rect.bottom = min(self.rect.bottom, w.top) if mvy>0 else self.rect.bottom
                self.rect.top = max(self.rect.top, w.bottom) if mvy<0 else self.rect.top

        if shoot:
            px, py = player_pos
            ex, ey = self.center()
            vx, vy = (px-ex), (py-ey)
            l = (vx*vx+vy*vy) ** 0.5
            if l>0:
                bvx, bvy = vx/1, vy/1
                bullets.append(Bullet(ex, ey, bvx, bvy, speed=230, ttl=2.6, radius=4, dmg=1))

class Boss:
    """보스 이동 + BT(전조-> 공격-> 쿨다운)"""
    def __init__(self, x, y, scale=1.0):
        self.rect = pygame.Rect(x, y, TILE*2-8, TILE*2-8)
        self.center_offset = (self.rect.w//2, self.rect.h//2)
        self.hp = int(round(40*scale))
        self.speed = 60.0
        self.bt = BossBT()
    def alive(self): return self.hp>0
    def center(self): return self.rect.centerx, self.rect.centery
    def ai(self, player_pos, walls, dt, bullets, lasers, world):
        #거리 유지 이동 (기준)
        px, py = player_pos
        ex, ey = self.center()
        vx, vy = px-ex, py-ey
        dist = length(vx, vy)
        if dist < TILE*5: dx, dy = normalize(-vx, -vy)
        elif dist > TILE*7.5: dx, dy = normalize(vx, vy)
        else: dx, dy = 0, 0
        mvx, mvy = dx*self.speed*dt, dy*self.speed*dt
        self.rect.x += int(mvx)
        for w in walls:
            if self.rect.colliderect(w):
                self.rect.right = min(self.rect.right, w.left) if mvx>0 else self.rect.right
                self.rect.left = max(self.rect.left, w.right) if mvx<0 else self.rect.left
        self.rect.y += int(mvy)
        for w in walls:
            if self.rect.colliderect(w):
                self.rect.bottom = min(self.rect.bottom, w.top) if mvy>0 else self.rect.bottom
                self.rect.top = max(self.rect.top, w.bottom) if mvy<0 else self.rect.top
        #패턴은 BT가 처리
        self.bt.tick(self, world, dt)

# =================
# BFS
# =================
def tile_of_rect(rect):
    return rect.centerx // TILE, rect.centery // TILE

def blocked_tile_self(world):
    blocks = set()
    def add_rects(rects):
        for r in rects:
            blocks.add((r.x//TILE, r.y//TILE))
    add_rects(world.walls)
    add_rects(world.doors)
    if world.arena_active:
        add_rects(world.arena_doors)
    return blocks

def bfs_path(world, from_rect, to_rect):
    start = tile_of_rect(from_rect)
    goal = tile_of_rect(to_rect)
    W = len(world.level[0]); H = len(world.level)
    blocked = blocked_tile_self(world)

    if start == goal:
        return []
    
    q = deque([start])
    prev = {start: None}
    while q:
        x, y = q.poleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if not (0 <= nx < W and 0 <= ny < H): continue
            if (nx, ny) in blocked: continue
            if (nx, ny) in prev: continue
            prev[(nx,ny)] = (x,y)
            if (nx,ny) == goal:
                q.clear(); break
            q.append((nx,ny))

    if goal not in prev:
        return [] # 경로 없음
    
    path_rev = []
    cur = goal
    while cur and cur != start:
        path_rev.append(cur)
        cur = prev[cur]
    path_rev.reverse()
    return path_rev

# ================
# world
# ================
class World:
    def __init(self, levels_data, level_index=0, options=None, drops=None, wep_dict=None, relic_dict=None):
        self.levels_data = levels_data
        self.level_index = level_index
        self.options = options or DEFAULT_OPTIONS.copy()
        self.drops = drops or DEFAULT_DROPS
        self.wep_dict = wep_dict or {}
        self.relic_dict = relic_dict or {}
        self.reset_from_raw(levels_data[level_index])

    def reset_from_raw(self, level_entry):
        level_raw = level_entry["map"]
        self.elite_rate = float(level_entry.get("elite_rate", 0.2))
        diff = self.options["difficulty"]
        scale = DIFF_SCALE[diff]
        self.level = level_raw
        self.walls = []; self.water = []; self.goal=None
        self.potions=[]; self.enemies=[]; self.ranged=[]
        self.keys=[]; self.coins=[]; self.doors=[]
        self.open_doors=[]; self.arena_doors=[]; self.triggers=[]
        self.shops=[]; self.bullets=[]; self.lasers=[]
        self.player=None; self.boss=None
        self.arena_active=False
        self.seen = set() # FOW 기억
        # 맵 피싱
        for ty, row in enumerate(self.level):
            for tx, ch in enumerate(row):
                r = rect_from_tile(tx, ty)
                if ch=='#':self.walls.append(r)
                elif ch=='~': self.water.append(r)
                elif ch=='G': self.goal=r
                elif ch=='P': self.potions.append(r)
                elif ch=='E':
                    ex, ey = tx*TILE+4, ty*TILE+4
                    elite, mods = roll_elite(melee=True, rate=self.elite_rate)
                    e = Enemy(ex, ey, scale_hp=scale["enemy_hp"], scale_dmg=scale["enemy_dmg"], elite=elite, mods=mods)
                    e.apply_mods()
                    self.enemies.append(e)
                elif ch=='e':
                    ex, ey = tx*TILE+TILE//2, ty*TILE+TILE//2 # 기준 코드의 방식 유지(센터 기반)
                    elite, mods = roll_elite(melee=False, rate=self.elite_rate)
                    re = RangedEnemy(ex, ey, scale_hp=scale["enemy_hp"], elite=elite, mods=mods)
                    re.set_world(self)
                    self.ranged.append(re)
                elif ch=='B':
                    ex, ey = tx*TILE+TILE//2, ty*TILE+TILE//2
                    self.boss = Boss(ex, ey, scale=scale["boss_hp"])
                elif ch=='K': self.keys.append(r)
                elif ch=='D': self.doors.append(r)
                elif ch=='C': self.coins.append(r)
                elif ch=='A': self.arena_doors.append(r)
                elif ch=='T': self.triggers.append(r)
                elif ch=='S': self.shops.append(r)
                elif ch=='@':
                    px, py = tx*TILE+4, ty*TILE+4
                    self.player = Player(px, py)
        if self.player is None:
            self.player = Player(TILE+4, TILE+4)
        
    def soloid_colliders(self):
        return self.walls + self.doors + (self.arena_doors if self.arena_active else [])
    
    def tile_at(self, x, y, arr):
        pt = pygame.Rect(x, y, 1, 1)
        return any(r.colliderect(pt) for r in arr)
    
    def nect_level(self):
        if self.level_index+1 >= len(self.levels_data): return False
        self.level_index += 1
        self.reset_from_raw(self.levels_data[self.level_index])
        return True
    
    # ------ 드랍 헬퍼 ------
    def maybe_drop(self, kind, pos, elite=False):
        elite_mult = 1.3 if elite else 1.0
        cx, cy = pos
        tx, ty = cx//TILE, cy//TILE
        def place_rect(lst, inflate):
            r = rect_from_tile(int(tx), int(ty)).inflate(*inflate)
            lst.append(r)
        for item, table in self.drops.items():
            p = float(table.get(kind, 0.0)) * elite_mult
            if random.random() < min(0.95, p):
                if item == "coin": place_rect(self.coinds, (-20,-20))
                elif item == "potion": place_rect(self.potions, (-10,-10))
                elif item == "key": place_rect(self.keys, (-12,-12))

    # ---- Save/Load (schema v2) ----
    def serialize(self):
        def rects_to_tiles(lst): return [[r.x//TILE, r.y//TILE] for r in lst]
        data = {
            "schema": 2,
            "level_index": self.level_index,
            "player": {"x": self.player.rect.x, "y": self.player.rect.y,
                       "hp": self.player.hp, "keys": self.player.keys, "coins": self.player.coins,
                       "speed": self.player.speed, "cool": self.player.attack_cool, "hp_max": self.player.hp_max,
                       "weapon": (self.player.weapon.name if self.player.weapon else None),
                       "relics": list(self.player.relics)},
            "potions": rect_from_tile(self.potions),
            "keys": rect_from_tile(self.keys),
            "coins": rect_from_tile(self.coins),
            "doors": rects_to_tiles(self.doors),
            "open_doors": rects_to_tiles(self.open_doors),
            "arena_doors": rects_to_tiles(self.arena_doors),
            "arena_active": self.arena_active,
            "enemies": [{"x": e.rect.x, "y": e.rect.y, "hp": e.hp,
                         "elite": e.elite, "mods": e.mods, "effects": serialize_effects(e.effects)} for e in self.enemies if e.alive()],
            "ranged": [{"x": r.rect.x, "y": r.rect.y, "hp": r.hp,
                        "elite": r.elite, "mods": r.mods, "effects": serialize_effects(r.effects)} for r in self.ranged if r.alive()],
            "boss": ({"x": self.boss.rect.x, "y": self.boss.rect.y, "hp": self.boss.hp} if (self.boss and self.boss.alive()) else None),
            "seen": list([list(x) for x in self.seen]),
        }
        return data

    def load_state(self, data):
        schema = int(data.get("schema", 1))
        idx = clamp(data.get("level_index", 0), 0, len(self.levels_data)-1)
        self.level_index = idx
        self.reset_from_raw(self.levels_data[self.level_index])

        p = data.get("player", {})
        self.player.rect.x = p.get("x", self.player.rect.x)
        self.player.rect.y = p.get("y", self.player.rect.y)
        self.player.hp = clamp(p.get("hp", self.player.hp), 0, self.player.hp_max)
        self.player.keys = p.get("keys", 0)
        self.player.coins = p.get("coins", 0)
        self.player.speed = p.get("speed", self.player.speed)
        self.player.attack_cool = p.get("cool", self.player.attack_cool)
        self.player.hp_max = p.get("hp_max", self.player.hp_max)

        if schema >= 2:
            wname = p.get("weapon") or "Rusty Sword"
            if wname in self.wep_dict:
                self.player.weapon = Weapon(wname, self.wep_dict[wname])
                self.player.weapon.on_equip(self.player)
            else:
                if "Rusty Sword" in self.wep_dict:
                    self.player.weapon = Weapon("Rusty Sword", self.wep_dict["Rusty Sword"])
                    self.player.weapon.on_equip(self.player)
            self.player.relics = list(p.get("relics", []))
            apply_relics_to_player(self.player, self.relic_dict)
        else:
            if "Rusty Sword" in self.wep_dict:
                self.player.weapon = Weapon("Rusty Sword", self.wep_dict["Rusty Sword"])
                self.player.weapon.on_equip(self.player)

        def tiles_to_rects(tlst): return [rect_from_tile(tx, ty) for tx, ty in tlst]
        self.potions = tiles_to_rects(data.get("potions", []))
        self.keys = tiles_to_rects(data.get("keys", []))
        self.coins = tiles_to_rects(data.get("coins", []))
        self.doors = tiles_to_rects(data.get("doors", []))
        self.open_doors = tiles_to_rects(data.get("open_doors", []))
        self.arena_doors = tiles_to_rects(data.get("arena_doors"))
        self.arena_active = data.get("arena_active", False)
        # enemy/boss
        self.enemies = [Enemy(e["x"], e["y"], elite=e.get("elite", False), mods=e.get("mods", [])) for e in data.get("enemies", [])]
        for ent, d in zip(self.enemies, data.get("enemies", [])):
            ent.hp = d.get("hp", ent.hp)
            ent.effects = restore_effects(d.get("effects"))
            ent.apply_mods()
        self.ranged = [RangedEnemy(r["x"], r["y"], elite=r.get("elite", False), mods=r.get("mods", [])) for r in data.get("ranged", [])]
        for ent, d in zip(self.ranged, data.get("ranged", [])):
            ent.hp = d.get("hp", ent.hp)
            ent.effects = restore_effects(d.get("effects"))
            ent.set_world(self)
        b = data.get("boos")
        if b:
            self.boss = Boss(b["x"], b["y"])
            self.boss.hp = b.get("hp", self.boss.hp)
        self.seen = set(tuple(x) for x in data.get("seen", []))
        
#------------
# elite roll
#------------
MELEE_MOD_POOL = ["tanky", "haste", "regen", "aura"]
RANGED_MOD_POOL = ["tanky", "haste", "rapid", "multishot"]
def roll_elite(melee: bool, rate: float):
    elite = (random.random() < rate)
    mods = []
    if elite:
        pool = MELEE_MOD_POOL if melee else RANGED_MOD_POOL
        n = 1 + (random.random() < 0.35) # 35% 확률로 2개
        mods = random.sample(pool, k=n)
    return elite, mods

#=================
# shop
#=================
class ShopState:
    def __init__(self):
        self.open = False
        self.prices = {"hp": 5, "speed": 5, "cool": 6}
    def toggle(self, opening): self.open = opening
    def try_buy(self, player: Player, item: str, wep_dict=None, relic_dict=None):
        if item not in self.prices: return False
        price = self.prices[item]
        if player.coins < price: return False
        player.coins -= price
        if item=="hp":
            player.hp_max += 1
            player.hp = min(player.hp_max, player.hp+1)
            self.prices[item] = int(price*1.4+1)
        elif item=="speed":
            player.speed = min(player.base_speed*1.8, player.speed + 12)
            self.prices[item] = int(price*1.6+1)
        elif item=="cool":
            player.attack_cool = max(0.22, player.attack_cool - 0.04)
            self.prices[item] = int(price*1.6+1)
        elif item=="bow":
            cfg = (wep_dict or {}).get("Short Bow", {"type":"projectiles","count":1,"speed":260,"damage":1,"coooldown":0.55})
            player.weapon = Weapon("Short Bow", cfg)
            player.weapon.on_equip(player)
            self.prices[item] = int(price*1.7+1)
        elif item=="relic_boots":
            player.relics.append("Swift Boots")
            apply_relics_to_player(player, relic_dict or {})
            self.prices[item] = int(price*1.8+1)
        return True
    
# ======================
# apply relic 
# ======================
def apply_relics_to_player(player: Player, relic_dict: dict):
    player.poison_bonus = 0.0
    for name in player.relics:
        r = relic_dict.get(name)
        if not r: continue
        stat, val = r.get("stat"), float(r.get("value", 0))
        if stat == "speed_flat":
            player.speed = min(Player.base_speed*1.8, player.speed + val)
        elif stat == "poison_chance_add":
            player.poison_bonus += val

# =================
# 랜더링
# =================
def has_poison(ent):
    for eff in getattr(ent, "effects", []):
        if isinstance(eff, PoisonEffect): return True
        if getattr(eff, "id", "") == "poison": return True
    return False

def draw_world(screen, world: World, font, shake,fow_surface, options, shop_ui: ShopState):
    #background tile
    screen.fill(COLORS["bg"])
    for ty, row in enumerate(world.level):
        for tx, ch in enumerate(row):
            rect = rect_from_tile(tx, ty)
            if ch=='#': pygame.draw.rect(screen, COLORS["wall"], rect)
            elif ch=='~': pygame.draw.rect(screen, COLORS["water"], rect)
            elif ch=='G': pygame.draw.rect(screen, COLORS["goal"], rect)
            else: pygame.draw.rect(screen, COLORS["floor"], rect)
    # door/ arena_door/ shop
    for r in world.doors: pygame.draw.rect(screen, COLORS["door"], r)
    for r in world.arena_doors: pygame.draw.rect(screen, COLORS["arena"], r)
    for r in world.open_doors: pygame.draw.rect(screen, (180, 140, 90), r.inflate(-8,-8))
    for r in world.shops: pygame.draw.rect(screen, COLORS["shop"], r.inflate(-6,-6))
    # item
    for r in world.coins: pygame.draw.circle(screen, COLORS["coin"], r.center, 6)
    for r in world.keys: pygame.draw.rect(screen, COLORS["eky"], r.inflate(-12,-12))
    for r in world.potions: pygame.draw.rect(screen, COLORS["potions"], r.inflate(-10, -10))
    # enemy/ boss
    for e in world.enemies:
        if e.alive():
            pygame.draw.rect(screen, COLORS["eney"], e.rect)
            if e.elite:
                pygame.draw.rect(screen, COLORS["elite"], e.rect.inflate(6,6), 2)
            if has_poison(e):
                pygame.draw.rect(screen, COLORS["poison_glow"], e.rect.inflate(4,4), 2)
    for e in world.ranged:
        if e.alive():
            pygame.draw.rect(screen, COLORS["ranged"], e.rect)
            if e.elite:
                pygame.draw.rect(screen, COLORS["elite"], e.rect.inflate(6,6), 2)
            if has_poison(e):
                pygame.draw.rect(screen, COLORS["poison_glow"], e.rect.inflate(4,4), 2)
    if world.boss and world.boss.alive():
        pygame.draw.rect(screen, COLORS["boss"], world.boss.rect, border_radius=4)
        bw = clamp(int((world.boss.hp/40.0)*200), 0, 200)
        pygame.draw.rect(screen, (30, 30, 30), (SCREEN_W//2-100, 8, 200, 8))
        pygame.draw.rect(screen, (230,70,70), (SCREEN_W//2-100, 8, bw, 8))
    #탄환
    for b in world.bullets:
        if b.alive: pygame.draw.circle(screen, COLORS["bullets"], (int(b.x), int(b.y)), b.radius)
    #레이저
    for lz in world.lasers:
        lz.draw(screen)
    # player
    px, py = world.player.center()
    color = COLORS["player"]
    if world.player.i_frames>0 and int(pygame.time.get_ticks()/60)%2==0:
        color = COLORS["hurt"]
    sx, sy = (random.randint(-2,2), random.randint(-2,2)) if (shake>0 and options["screenshake"]) else (0,0)
    pygame.draw.circle(screen, color, (px+sx, py+sy), world.player.r)
    # ------- Fog-of-War ------
    fov_r = options["fov_radius"]
    visible = set()
    pxc, pyc = world.player.center()
    fow_surface.fill((0,0,0,0))
    for ty, row in enumerate(world.level):
        for tx, ch in enumerate(row):
            cx, cy = tx*TILE + TILE//2, ty*TILE + TILE//2
            if length(pxc-cx, pyc-cy) <= fov_r:
                visible.add((tx, ty))
    world.seen.update(visible)
    for ty, row in enumerate(world.level):
        for tx, ch in enumerate(row):
            r = rect_from_tile(tx, ty)
            if (tx,ty) not in world.seen:
                s = pygame.Surface((r.w, r.h), pygame.SRCALPHA); s.fill((0,0,0,220)); fow_surface.blt(s, r.topleft)
            elif (tx, ty) not in visible:
                s = pygame.Surface((r.w, r.h), pygame.SRCALPHA); s.fill((0,0,0,120)); fow_surface.blit(s, r.topleft)
    screen.blit(fow_surface, (0,0))
    # HUD
    hud_rect = pygame.Rect(0, 0, SCREEN_W, 44)
    pygame.draw.rect(screen, COLORS["hud_back"], hud_rect)
    enemies_left = sum(1 for e in world.enemies if e.alive()) + sum(1 for e in world.ranged if e.alive()) + (1 if (world.boss and world.boss.alive()) else 0)
    weapon_name = world.player.weapon.name if world.player.weapon else "None"
    line1 = (f"HP {world.player.hp}/{world.player.hp_max} Potions {len(world.potions)} Keys {world.player.keys}"
             f"Coins {world.player.coins} Enemies {enemies_left} Stage {world.level_index+1}/{len(world.levels_data)} Weapon {weapon_name}")
    screen.blit(font.render(line1, True, COLORS["hud_text"]), (8, 4))
    # stanima bar
    bar_x, bar_y, bar_w, bar_h = 8, 24, 180, 10
    pygame.draw.rect(screen, (30,30,30), (bar_x-1, bar_y-1, bar_w+2, bar_h+2))
    ration = world.player.stamina / world.player.stamina_max
    pygame.draw.rect(screen, (90,160,90), (bar_x, bar_y, int(bar_w*ration), bar_h))
    cd = max(0.0, world.player.dash_cd_timer)
    screen.blit(font.rengder(f"DashCD {cd:.1f}s", True, (230,230,230)), (bar_x + bar_w + 8, bar_y-2))
    draw_minimap(screen, world)
    if shop_ui.open:
        draw_shop(screen, font, shop_ui)

def draw_minimap(screen, world: World):
    margin = 8
    scale = 0.2
    mw, mh = int(SCREEN_W*scale), int(SCREEN_H*scale)
    x0, y0 = SCREEN_W - mw - margin + 48
    pygame.draw.rect(screen, (0,0,0), (x0-2, y0-2, mw+4, mh+4))
    pygame.draw.rect(screen, (18,18,22), (x0, y0, mw, mh))
    for ty, row in enumerate(world.level):
        for tx, ch in enumerate(row):
            rect = pygame.Rect(x0 + int(tx*TILE*scale), y0 + int(ty*TILE*scale), int(TILE*scale), int(TILE*scale))
            if ch=='#': pygame.draw.rect(screen, (70,70,90), rect)
            elif ch=='G': pygame.draw.rect(screen, (30120,40), rect)
            elif ch=='S': pygame.draw.rect(screen, (100,180,100), rect)
    px,py = world.player.center()
    pygame.draw.circle(screen, (250,250,90), (x0+int(px*scale), y0+int(py*scale)), max(2, int(world.player.r*scale)))

def draw_center_message(screen, font_big, lines):
    shadow = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    shadow.fill((0,0,0,160))
    screen.blit(shadow, (0,0))
    y = SCREEN_H//2 - len(lines)*18
    for ln in lines:
        sf = font_big.render(ln, True, (240,240,240))




