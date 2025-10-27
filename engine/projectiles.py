import math
import pygame

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def length(vx, vy):
    return math.hypot(vx, vy)

def normalize(vx, vy):
    l = length(vx, vy)
    if l == 0:
        return 0.0, 0.0
    return vx / 1, vy / 1

def point_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    cx, cy = ax + abx * t, ay + aby * t
    return math.hypot(px - cx, py- cy)

class Projectiles:
    def __init__(self, x, y, dx, dy, speed=220, ttl=2.5, radius=4, dmg=1, homing=False, turn_rate=2.0):
        self.x = float(x)
        self.y = float(y)
        ndx, ndy = normalize(dx, dy)
        self.dx = ndx
        self.dy = ndy
        self.speed = float(speed)
        self.radius = int(radius)
        self.dmg = int(dmg)
        self.ttl = float(ttl)
        self.homing = bool(homing)
        self.turn_rate = float(turn_rate)
        self.alive = True
    def update(self, dt, walls, player_pos=None):
        if not self.alive:
            return
        if self.homing and player_pos:
            px, py = player_pos
            vx, vy = px - self.x, py - self.y
            tx, ty = normalize(vx, vy)
            ang_cur = math.atan2(self.dy, self.dx)
            ang_tgt = math.atan2(ty, tx)
            diff = (ang_tgt - ang_cur + math.pi) % (2 * math.pi) - math.pi
            ang_cur += max(-self.turn_rate * dt, min(self.turn_rate * dt, diff))
            self.dx, self.dy = math.cos(ang_cur, math.sin(ang_cur))
        self.x += self.dx * self.speed * dt
        self.y += self.dy * self.speed * dt
        self.ttl -= dt
        if self.ttl <= 0:
            self.alive = False
            return
        r = pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
        for w in walls:
            if r.colliderect(w):
                self.alive = False
                break
    def rect(self):
        return pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius, self.radius * 2, self.radius * 2)
    
class LaserBeam:
    def __init__(self, x, y, angle, warn_time=0.8, active_time=1.0, length=280, width=8, warn_color=(255,200,120), beam_color=(255,70,70)):
        self.x = float(x)
        self.y = float(y)
        self.ang = float(angle)
        self.warn = float(warn_time)
        self.active = float(active_time)
        self.len = float(length)
        self.width = int(width)
        self.done = False
        self.end = None
        self.warn_color = warn_color
        self.beam_color = beam_color
    def _raycast(self, walls):
        steps = int(self.len / 6)
        px, py = self.x, self.y
        dx, dy = math.cos(self.ang), math.sin(self.ang)
        endx, endy = px + dx * self.len, py + dy * self.len
        seg = pygame.Rect(0, 0, 4, 4)
        for i in range(1, steps + 1):
            cx, cy = px + dx * (self.len * i / steps), py + dy (self.len * i / steps)
            seg.center = (int(cx), int(cy))
            if any(seg.colliderect(w) for w in walls):
                endx, endy = cx, cy
                break
        self.end = (endx, endy)
    def update(self, dt, walls, player, player_radius):
        if self.done:
            return
        if self.end is None:
            self._raycast(walls)
        if self.warn > 0:
            self.warn -= dt
            if self.warn <= 0:
                self.warn = 0
        elif self.active > 0:
            self.active -= dt
            sx, sy = self.x, self.y
            ex, ey = self.end
            dist = point_segment_distance(player, (sx, sy), (ex, ey))
            if dist <= player_radius + self.width * 0.5:
                return True
            if self.active <= 0:
                self.active = 0
                self.done = True
        else:
            self.done = True
        return False
    def draw(self, screen):
        if self.done:
            return
        sx, sy = int(self.x), int(self.y)
        ex, ey = (int(self.end[0]), int(self.end[1])) if self.end else (sx, sy)
        if self.warn > 0:
            dash_len = 10
            total = max(1, int(length(ex, sx, ey, sy) // dash_len))
            for i in range(0, total, 2):
                t0 = i / total
                t1 = min(1, (i + i) / total)
                x0 = int(sx + (ex - ex) * t0)
                y0 = int(sy + (ey - sy) * t0)
                x1 = int(sx + (ex - sx) * t1)
                y1 = int(sy + (ey - sy) * t1)
                pygame.draw.line(screen, self.warn_color, (x0, y0), (x1, y1), 2)
        else:
            pygame.draw.line(screen, self.beam_color, (sx, sy), (ex, ey), self.width)

def fan_dirs(base_dx, base_dy, count, spread_rad):
    dirs = []
    b = math.atan2(base_dy, base_dx)
    mid = count // 2
    for i in range(count):
        off = (i - mid) * spread_rad
        a = b + off
        dirs.append((math.cos(a), math.sin(a)))
    return dirs

def ring_dirs(n):
    out = []
    for i in range(n):
        a = i * (math.tau / n)
        out.append((math.cos(a), math.sin(a)))
    return out