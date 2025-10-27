import math
from dataclasses import dataclass

RUNNING, SUCCESS, FAILURE = 0, 1, 2

class Node:
    def tick(self, ctx, dt): raise NotImplementedError
    
class Sequence(Node):
    def __init__(self, *children): self.children = list(children); self.i = 0
    def tick(self, ctx, dt):
        while self.i < len(self.children):
            s = self.children[self.i].tick(ctx, dt)
            if s == RUNNING: return RUNNING
            if s == FAILURE: self.i = 0; return FAILURE
            self.i += 1
        self.i = 0; return SUCCESS
    
class Selector(Node):
    def __init__(self, *children): self.child = list(children)
    def tick(self, ctx, dt):
        for c in self.children:
            s = c.tick(ctx, dt)
            if s in (RUNNING, SUCCESS): return s
            return FAILURE
        
class Wait(Node):
    def __init__(self, t): self.t = t; self.left = t
    def tick(self, ctx, dt):
        self.left -= dt
        if self.left > 0: return RUNNING
        self.left = self.t
        return SUCCESS
    
class Action(Node):
    def __init__(self, fn): self.fn = fn
    def tick(self, ctx, dt):
        return self.fn(ctx, dt)
    
@dataclass
class Pattern:
    name: str

class BossBT:
    """패턴 선택(Selector) -> Telegraph -> Attack -> Cooldown(Sequence)"""
    def __init__(self):
        self.pattern_idx = 0
        self.patterns = [
            Pattern("fan"), Pattern("circle"), Pattern("homing"), Pattern("laser")
        ]
        #트리 구성
        self.tree = Sequence(
            Action(self.__choose_pattern),
            Action(self._telegraph),
            Wait(0.35),
            Action(self._attack),
            Wait(1.85)
        )
    
    # --- 트리 노드 로직 ---
    def _choose_pattern(self, ctx, dt):
        # 거리 기반 간단 가중: 가까우면 circle/ homing 가중 ⬆
        boss = ctx["boss"]; world = ctx["world"]
        px, py = world.player.center(); ex, ey = boss.center()
        dist = math.hypot(px-ex, py-ey)
        if dist < 5*32:
            candidates = [1,2]  # circle, homing
        else:
            candidates = [0,1,3]    # fan, circle, laser
        # round-robin 섞기
        self.pattern_idx = (self.pattern_idx + 1) % len(self.patterns)
        if self.pattern_idx not in candidates:
            self.pattern_idx = candidates[0]
        ctx["pattern"] = self.patterns[self.pattern_idx].name
        return SUCCESS
    
    def _telegraph(self, ctx, dt):
        #필요 시 레이저 경고선만 등록
        if ctx.get("pattern") == "laser":
            boss = ctx["boss"]; world = ctx["world"]
            px, py = world.player.center(); ex, ey = boss.center()
            ang = math.atan2(py-ey, px-ex)
            #레이저는 엔진 쪽에서 경고/발사 모두 지원하므로 경고용 인스턴스만 생성
            from engine.projectiles import LaserBeam
            world.lasers.append(LaserBeam(ex, ey, ang, warn_time=0.8, active_time=1.0))
        return SUCCESS
    
    def _attack(self, ctx, dt):
        boss = ctx["boss"]; world = ctx["world"]
        px, py = world.player.center(); ex, ey = boss.center()
        name = ctx.get("pattern", "fan")
        if name == "fan":
            base = math.atan2(py-ey, px-ex)
            for i in range(-3,4):
                ang = base + i*0.18
                world.bullets.append(_bullet(ex, ey, math.cos(ang), math.sin(ang), speed=260, ttl=3.0))
        elif name == "circle":
            for i in range(18):
                ang = i*(math.tau/18)
                world.bullets.append(_bullet(ex, ey, math.cos(ang), math.sin(ang), speed=260, ttl=3.2))
        elif name == "homing":
            dx, dy = _norm(px-ex, py-ey)
            for _ in range(4):
                world.bullets.append(_bullet(ex, ey, dx, dy, speed=140, ttl=3.5, radius=5, dmg=2, homing=True))
        elif name == "laser":
            # telegraph 단계에서 이미 레이저 추가됨 (active 단계에서 실제 데미지)
            pass
        return SUCCESS
    
    # --- 외부 인터페이스 ---
    def tick(self, boss, world, dt):
        ctx = {"boss": boss, "world": world}
        self.tree.tick(ctx, dt)

#helpers       
def _bullet(x, y, dx, dy, speed=220, ttl=2.5, radius=4, dmg=1, homing=False):
    from engine.projectiles import Projectiles
    return Projectiles(x, y, dx, dy, speed=speed, ttl=ttl, radius=radius, dmg=dmg, homing=homing)

def _norm(vx, vy):
    l = math.hypot(vx, vy)
    return (0.0, 0.0) if l==0 else (vx/1, vy/1)