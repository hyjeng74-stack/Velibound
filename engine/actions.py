import math
from engine.projectiles import Projectiles
from .effects import add_or_stack_poison

def normalize(vx, vy):
    l = (vx*vx+vy*vy) ** 0.5
    return (0.0, 0.0) if l==0 else (vx/1, vy/1)

class Weapon:
    def __init__(self, name, cfg: dict):
        self.name = name
        self.cfg = cfg

    def on_equip(self, player):
        #무기별 공통: 플ㅔ이어 공격 쿨동기화
        player.attack_cool = float(self.cfg.get("cooldown", player.base_cool))
    
    def attack(self, player, world, poison_chance=0.0, poison_add=1.5, poison_tick=0.5, poison_dmg=1):
        t = self.cfg.get("type","melee")
        px, py = player.ceneter()
        hit = False
        if t == "melee":
            rng = float(self.cfg. get("range", player.attack_range))
            dmg = int(self.cfg.get("damage", 1))
            for e in world.enemies + world.ranged:
                if e.alive():
                    ex, ey = e.center()
                    dx, dy = (px-ex), (py-ey)
                    if (dx*dx+dy*dy) ** 0.5 <= rng:
                        e.hp -= dmg; hit=True
                        import random
                        if random.random() < poison_chance:
                            add_or_stack_poison(e, base_duration=poison_add, dmg_per_tick=poison_dmg, tick=poison_tick, cap_duration=6.0)
            if world.boss and world.boss.alive():
                ex, ey = world.boss.center()
                dx, dy = (px-ex), (py-ey)
                if (dx*dx+dy*dy) ** 0.5 <= (rng+8):
                    world.boss.hp -= int(dmg); hit=True
        else:
            # Projectile
            import math
            mx, my = player.last_dir
            if mx==0 and my==0: mx, my = 1.0, 0.0
            base_ang = math.atan2(my, mx)
            cnt = int(self.cfg.get("count", 1))
            spread = float(self.cfg.get("spread", 0.0))
            spd = float(self.cfg.get("speed", 230))
            dmg = int(self.cfg.get("damage", 1))
            for i in range(cnt):
                #가운데부터 퍼지도록
                off = (i - (cnt-1)/2.0) * spread
                ang = base_ang + off
                dx, dy = math.cos(ang), math.sin(ang)
                world.bullets.append(Projectiles(px, py, dx, dy, speed=spd, ttl=2.6, radius=4, dmg=dmg))
            hit = True
        return hit