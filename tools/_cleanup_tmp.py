import json, os
from pathlib import Path

to_delete = [
    r"C:\Code\CV_crawl\.cv-apply-evidence-pack-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-slot-plan-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-coverage-plan-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-coverage-review-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-jd-keywords-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-project-selections.json",
    r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-meta-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-context-tmp.json",
    r"C:\Code\CV_crawl\.cv-apply-jd-tmp.txt",
]
for f in to_delete:
    try:
        os.remove(f)
        print(f"Deleted: {f}")
    except FileNotFoundError:
        pass
print("Cleanup complete.")
