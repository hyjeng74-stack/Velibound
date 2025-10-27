import json
from pathlib import Path

DEFAULT = {"unlocked": [], "stats": {"arenas_cleared":0, "kills":0, "coins":0}}

def load_meta(path: Path):
    try:
        if path.exists(): return json.loads(path.read_text(encoding="utf-8"))
    except: pass
    return json.loads(json.dumps(DEFAULT))

def save_meta(path: Path, meta: dict):
    try:
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except: pass
    
def unlock(meta: dict, key: str):
    if key not in meta["unlocked"]:
        meta["unlocked"].append(key)

def on_event(meta: dict, name: str, **kw):
    if name == "arena_clear":
        meta["stats"]["arenas_cleared"] += 1
        # 예시 해금 규칙
        if meta["stats"]["arenas_cleared"] >= 1: unlock(meta, "bow")
        if meta["stats"]["arenas_cleared"] >= 2: unlock(meta, "relic_boots")
    elif name == "enemy_died":
        meta["stats"]["kills"] +=1
    elif name == "pickup" and kw.get("item")=="coin":
        meta["stats"]["coins"] += 1

def shop_lineup(meta: dict):
    base = {"hp":5, "speed":5, "cool":6}
    if "bow" in meta["unlocked"]:
        base["bow"] = 7
    if "relic_boots" in meta["unlocked"]:
        base["relic_boots"] = 8
    return base

def patch_shop(shop_state, lineup: dict):
    #가격표를 해금 상태에 맞춰 갱신
    for k in list(shop_state.prices.keys()):
        if k not in lineup: shop_state.prices.pop(k, None)
    for k, v in lineup.items():
        if k not in shop_state.prices:
            shop_state.prices[k] = v