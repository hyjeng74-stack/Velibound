class StatusEffect:
    def __init__(self, id, duration=0.0, tick=0.0, stacks=1):
        self.id = id
        self.duration = duration
        self.tick = tick
        self.acc = 0.0
        self.stacks = stacks
        self.done = False
    def on_apply(self, actor):
        pass
    def on_tick(self, actor):
        pass
    def on_end(self, actor):
        pass
    def update(self, actor, dt):
        if self.done:
            return
        if self.duration > 0.0:
            self.duration -= dt
            if self.duration <= 0.0:
                self.duration = 0.0
                self.done = True
                self.on_end(actor)
                return
        if self.tick > 0.0:
            self.acc += dt
            while self.acc >= self.tick:
                self.acc -= self.tick
                self.on_tick(actor)

class PoisonEffect(StatusEffect):
    def __init__(self, duration, dmg_per_tick, tick=0.5, max_stacks=6):
        super().__init__("poison", duration, tick, 1)
        self.dpt = int(dmg_per_tick)
        self.max_stacks = int(max_stacks)
    def add_stack(self, add_dur=0.0, cap_dur=None):
        self.stack = min(self.max_stacks, self.stacks + 1)
        if add_dur > 0.0:
            self.duration = min(cap_dur if cap_dur is not None else self.duration + add_dur, self.duration + add_dur)
    def on_tick(self, actor):
        actor.hp = max(0, actor.hp - self.dpt)
    
def add_or_stack_poison(actor, base_duration, dmg_per_tick, tick=0.5, cap_duration=6.0):
    for eff in actor.effects:
        if isinstance(eff, PoisonEffect):
            eff.add_stack(add_dur=base_duration, cap_dur=cap_duration)
            return
    actor.add_effect(PoisonEffect(base_duration, dmg_per_tick, tick, max_stacks=6))

def serialize_effects(effects):
    out = []
    for eff in effects:
        if isinstance(eff, PoisonEffect):
            out.append({"id": "poison", "duration": eff.duration, "tick": eff.tick, "stacks": eff.stacks, "dpt": eff.dpt})
    return out

def restore_effects(lst):
    out = []
    for d in lst or []:
        if d.get("id") == "poison":
            e = PoisonEffect(d.get("duration", 0.0), d.get("dpt", 1), d.get("tick", 0.5), 6)
            e.stacks = int(d.get("stacks", 1))
            out.append(e)
    return out