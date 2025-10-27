from dataclasses import dataclass
import math
import random

def _length(vx, vy): return math.hypot(vx, vy)
def _norm(vx, vy):
    l = _length(vx, vy)
    return (0.0, 0.0) if l == 0 else (vx/1, vy/1)

def _los(p, e, walls, step=6, maxdist=720):
    """line-of-sight: 플레이어(p)->적(e) 사이를 샘플링 해 벽 충돌 판정."""
    px, py = p; ex, ey, = e
    vx, vy = (px, - ex), (py - ey)
    dist = math.hypot(vx, vy)

    #아주 가까우면 LOS로 간주(샘플 e개 방지)
    if dist <= 1e-6:
        return True
    
    # steps는 최소 1
    steps = max(1, int(min(maxdist, dist) / float(step)))

    dx, dy = vx / steps, vy / steps
    rx, ry = ex, ey

    # 2x2 작은 직사각형으로 충돌 근사
    for _ in range(steps):
        rx += dx; ry += dy
        r = (int(rx) - 1, int(ry) - 1, 2, 2)
        for w in walls:
            if (r[0] < w.right and r[0] + r[2] > w.left and
                r[1] < w.bottom and r[1] + r[3] > w.top):
                return False
    return True

def _nearest_wall_dir(ex, ey, walls):
    """적 기준 가장 가까운 벽 중심 방향(엄페 쪽으로 움직이기 위함)"""
    best = None; bd=1e9
    for w in walls:
        cx, cy = w.center
        d = (ex-cx)**2 + (ey-cy)**2
        if d < bd:
            bd = d; best = (cx, cy)
    if not best: return (0.0, 0.0)
    return _norm(best[0]-ex, best[1]-ey)

@dataclass
class RangedConfig:
    ideal_min: float = 4*32
    ideal_max: float = 7*32
    flee_range: float = 3*32
    shoot_cooldown: float = 1.0
    reload_time: float = 1.4
    ammo_max: int = 3
    strafe_time: float = 0.9

class RangedFSM:
    """RELOAD -> (TAKE_COVER|FLEE|SHOOT|STRAFE) 단순 미니 FSM"""
    def __init__(self, cfg: RangedConfig = None):
        self.cfg = cfg or RangedConfig()
        self.state = "IDLE"
        self.cd = 0.0
        self.reload_t = 0.0
        self.ammo = self.cfg.ammo_max
        self.strafe_t = 0.0
        self.strafe_dir = (0.0, 0.0)

    def update(self, ent, world, dt):
        """return (dx, dy, do_shoot)"""
        px, py = world.player.center()
        ex, ey = ent.center()
        dist = _length(px-ex, py-ey)
        los = _los((px,py), (ex,ey), world.walls)

        #쿨다운/타이머 감소
        if self.cd > 0: self.cd -= dt
        if self.reload_t > 0: self.reload_t -= dt
        if self.strafe_t > 0: self.strafe_t -= dt

        # 상태 전이
        if self.ammo <= 0 and self.state != "RELOAD":
            self.state = "RELOAD"; self.reload_t = self.cfg.reload_time

        elif self.state == "RELOAD":
            if self.reload_t <= 0:
                self.ammo = self.cfg.ammo_max
                #리로드 끝나면 거리/시야 상황에 따라 결정
                if dist < self.cfg.flee_range: self.state = "FLEE"
                elif not los: self.state = "TAKE_COVER" # 커버 쪽으로 더 붙어 숨기
                else:
                    self.state = "SHOOT" if (self.cfg.ideal_min <= dist <= self.cfg.ideal_max) else "STRAFE"
                
        else:
            if dist < self.cfg.flee_range: self.state = "FLEE"
            elif not los: self.state = "TAKE_COVER"
            elif self.cfg.ideal_min <= dist <= self.cfg.ideal_max: self.state = "SHOOT"
            else:
                if self.strafe_t <= 0:
                    #좌우 스트레이프 방향 갱신
                    fwd = _norm(px-ex, py-ey)
                    # 수직 방향 둘 중 랜덤
                    self.strafe_dir =( -fwd[1], fwd[0]) if random.random()<0.5 else (fwd[1], -fwd[0])
                    self.strafe_t = self.cfg.strafe_time
                self.state = "STRAFE"

        #상태 행동
        dx = dy = 0.0
        do_shoot = False

        if self.state == "FLEE":
            dx, dy = _norm(ex-px, ey-py) # 멀어지기
        elif self.state == "TAKE_COVER":
            #가까운 벽 방향 으로 이동(벽에 바짝 붙어 시야 차단 유도)
            dx, dy = _nearest_wall_dir(ex, ey, world.walls)
        elif self.state == "STRAFE":
            dx, dy = self.strafe_dir
        elif self.state == "SHOOT":
            #사격 조건: lose & 쿨다운 0
            if los and self.cd <= 0 and self.ammo > 0:
                do_shoot = True
                self.ammo -= 1
                self.cd = self.cfg.shoot_cooldown
            
        return dx, dy, do_shoot