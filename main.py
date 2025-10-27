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
def rect_from_tiles(tx, ty): return pygame.Rect(tx*TILE, ty*TILE, TILE, TILE)

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
        self.weapom = None
        self.relivs = []
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


    