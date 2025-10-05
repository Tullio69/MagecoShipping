# src/fs_ops.py
import time, shutil, json
from pathlib import Path

def ensure_dir(p: Path):
    Path(p).mkdir(parents=True, exist_ok=True)

def move_with_collision(src: Path, dest_dir: Path) -> Path:
    ensure_dir(dest_dir)
    target = dest_dir / src.name
    if target.exists():
        stem, suf = src.stem, src.suffix
        i = 1
        while (dest_dir / f"{stem} ({i}){suf}").exists():
            i += 1
        target = dest_dir / f"{stem} ({i}){suf}"
    shutil.move(str(src), str(target))
    return target

def move_with_retry(src: Path, dest_dir: Path, retries: int = 6, delay: float = 0.5) -> Path:
    last_err = None
    for _ in range(retries):
        try:
            return move_with_collision(src, dest_dir)
        except Exception as e:
            last_err = e
            time.sleep(delay)
    raise last_err

def write_reason_json(dest_file: Path, reason: str):
    meta = dest_file.with_suffix(dest_file.suffix + ".reason.json")
    meta.write_text(json.dumps({"reason": reason}, indent=2, ensure_ascii=False), encoding="utf-8")
