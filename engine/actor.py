import pygame

class Actor:
    def __init__(self, x, y, w, h, hp=1, speed=0.0):
        self.rect = pygame.Rect(x, y, w, h)
        self.hp = int(hp)
        self.speed = float(speed)
        self.effects = []
        self.i_frames = 0.0
    def alive(self):
        return self.hp > 0
    def center(self):
        return self.rect.ceterx, self.rect.centery
    def hurt(self, dmg):
        if self.i_frames > 0:
            return
        self.hp = max(0, self.hp - int(dmg))
    def add_effect(self, effect):
        self.effects.append(effect)
        effect.on_apply(self)
        def tick_effects(self, dt):
            if self.i_frames > 0:
                self.i_frames = max(0.0, self.i_frames - dt)
            kept = []
            for eff in self.effects:
                eff.update(self, dt)
                if not eff.done:
                    kept.append(eff)
            self.effects = kept