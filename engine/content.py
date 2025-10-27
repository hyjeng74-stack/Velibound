import json
from pathlib import Path

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def load_weapons(path: Path):
    base = _load_json(path, None)
    if base and "weapons" in base: base = base
    else:
        base = {"weapons":{
            "Rusty Sword": {"type":"melee","range":28,"damage":1,"cooldown":0.50},
            "Short Bow":   {"type":"projectile","count":1,"speed":260,"spread":0.0,"damage":1,"cooldown":0.55},
            "Tri Bow":     {"type":"projectile","count":3,"speed":250,"spread":0.12,"damage":1,"cooldown":0.62}
        }}
    # 모딩 레이어 병합
    try:
        from modding.loader import layered_load
        merged = layered_load(base, Path("data")/"mods", "weapons.json")
        return merged["weapons"]
    except Exception:
        return base["weapons"]
    
def load_relics(path: Path):
    data = _load_json(path, None)
    if data and "relics" in data: return data["relics"]
    # fallback
    return {
        "Swift Boots": {"stat":"speed_flat","value":12},
        "Toxic Ring":  {"stat":"poison_chance_add","value":0.15},
    }

