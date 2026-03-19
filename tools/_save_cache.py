import json, sys
from datetime import datetime, timezone
from pathlib import Path

cache_path = Path(r"C:\Code\CV_crawl\.experience-cache.json")
cache = json.loads(cache_path.read_text(encoding="utf-8"))

key = sys.argv[1]
answer = sys.argv[2] if len(sys.argv) > 2 else None
job_id = int(sys.argv[3]) if len(sys.argv) > 3 else None

if answer:
    cache[key] = {"answer": answer, "job_id": job_id, "ts": datetime.now(timezone.utc).isoformat(), "source": "gap_fill"}
else:
    cache[key] = {"answer": None, "skipped": True}

cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved: {key}")
