import json

def load_json_safe(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return default

def merge_options(base, ext):
    out = json.loads(json.dumps(base))
    for k, v in ext.items():
        if k != "keymap":
            out[k] = v
        else:
            km = out.setdefault("keymap", {})
            for ak, arr in v.items():
                km[ak] = [int(x) for x in arr]
    return out

def load_levels_v1_or_fallback(path, fallback_maps):
    data = load_json_safe(path, None)
    if not data:
        return [{"map": m, "elite_rate": 0.2} for m in fallback_maps]
    if isinstance(data, dict) and "levels" in data:
        lvls = []
        for lv in data["levels"]:
            m = lv.get("map")
            if not m:
                continue
            lvls.append({"map": m, "elite_rate": float(lv.get("elite_rate", 0.2))})
        return lvls or [{"map": m, "elite_rate": 0.2} for m in fallback_maps]
    if isinstance(data, list):
        return [{"map":m, "elite_rate": 0.2} for m in data]
    return [{"map": m, "elite_rate": 0.2} for m in fallback_maps]

def load_drops_v1_or_default(path, default_table):
    data = load_json_safe(path, None)
    if not data:
        return default_table
    out = json.loads(json.dumps(default_table))
    src = data.get("drops", data)
    for item, mp in src.items():
        out.setdefault(item, {})
        for kind, p in mp.items():
            out[item][kind] = float(p)
    return out
    
