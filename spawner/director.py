import random
import math

class Director:
    """
    난이도 예산(budget) 기반 스폰:
    - 목표 생존 적 수 = base + stage 계수 - 현재 생존 수 보정
    - 플레이어 HP 낮으면 공격성 완화
    - arena_active일 때 적극 스폰
    """
    def __init__(self, world, factories: dict, base_target=6):
        self.world = world
        self.factories = factories # {"enemy": EnemyClass, "ranged": RangedClass}
        self.base_target = base_target
        self.accum = 0.0
        self.spawn_rate = 1.6 # budget/s
        self.stage_mult = 0.8

    def update(self, dt):
        w = self.world
        alive = sum(e.alive() for e in w.enemies) + sum(e.alive() for e in w.ranged) + (1 if (w.boss and w.boss.alive()) else 0)
        if w.boss and w.boss.alive(): #보스전에는 스폰 중지
            return
        if not (w.arena_active): #아레나일 때만 (원하면 조건 제거)
            return
        
        #목표 적 수와 예산
        stage = max(0, w.level_index)
        hp_ratio = w.player.hp / max(1, w.player.hp_max)
        target = int(self.base_target + self.stage_mult*stage)
        # Hp 낮으면 목표 줄이기
        if hp_ratio < 0.4: target = max(2, int(target*0.6))

        if alive >= target: return

        self.accum += self.spawn_rate * dt
        costs = {"enemy":1.0, "ranged":1.5}
        while alive < target and self.accum >= 1.0:
            kind = "ranged" if random.random() < 0.35 else "enemy"
            if self.accum < costs[kind]: break
            pos = self._pick_spawn_pos(mis_dist=5*32)
            if not pos: break
            self._spawn(kind, *pos)
            self.accum -= costs[kind]
            alive +=1

    # ---- helpers ----
    def _spawn(self, kind, x, y):
        cls = self.factories[kind]
        if kind == "enemy":
            e = cls(x, y, elite=False)
            self.world.enemies.append(e)
        else:
            r = cls(x, y, elite=False)
            self.world.ranged.append(r)

    def _pick_spawn_pos(self, min_dist=160):
        """바닥('.') 타일 중 플레이어와 멀고, 벽과 겹치지 않는 곳"""
        level = self.world.level
        tiles = []
        for ty, row in enumerate(level):
            for tx, ch in enumerate(row):
                if ch == '.':
                    cx, cy = tx*32+16, ty*32+16
                    tiles.append((cx, cy))
        random.shuffle(tiles)
        px, py = self.world.player.center()
        for cx, cy in tiles:
            if math.hypot(px-cx, py-cy) < min_dist: continue
            #벽 충돌 피하기
            ok = True
            for w in self.world.walls + self.world.doors + (self.world.arena_doors if self.world.arena_active else[]):
                if w.collidepoint(cx, cy):
                    ok = False; break
            if ok: return (cx, cy)
        return None



        


