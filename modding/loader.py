import json
from pathlib import Path
from typing import Dict, Any

def deep_merge(a: Dict[str, Any], b: Dict[str, Any]):
    for k, v in b.items():
        if k in a and isinstance(a[k], dict) and isinstance(v, dict):
            deep_merge(a[k], v)
        else:
            a[k] = v
    return a

def layered_load(base: Dict[str, Any], mods_root: Path, filename: str) -> Dict[str, Any]:
    """
    data/mods/*/<filename> 순서대로 base 위에 덮어쓰기
    """
    out = json.loads(json.dumps(base))
    if not mods_root.exists(): return out
    #하위 폴더 이름 순으로 안정적 병합
    for mod_dir in sorted([p for p in mods_root.iterdir() if p.is_dir()]):
        target = mod_dir / filename
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                deep_merge(out, data)
            except Exception:
                continue
    return out