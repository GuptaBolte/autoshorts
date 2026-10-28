"""Processes jobs/queue: renders each due job, then posts it (mode=post) or parks it for review (mode=draft).

A job is due when publish_at is empty or in the past (ISO 8601, e.g. 2026-10-30T13:30:00+05:30).
Results are written back into the job file, which moves to jobs/done, jobs/drafts or jobs/failed.
"""
import datetime as dt
import glob
import json
import os
import shutil
import sys
import traceback

from . import render

ROOT = render.ROOT
OUT = os.path.join(ROOT, "out")
MAX_JOBS = int(os.environ.get("MAX_JOBS_PER_RUN", "3"))
MAX_ATTEMPTS = 3


def now():
    return dt.datetime.now(dt.timezone.utc)


def is_due(job):
    when = job.get("publish_at")
    if not when:
        return True
    return dt.datetime.fromisoformat(when.replace("Z", "+00:00")) <= now()


def has(*names):
    return all(os.environ.get(n) for n in names)


def move(path, job, folder):
    dest_dir = os.path.join(ROOT, "jobs", folder)
    os.makedirs(dest_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    shutil.move(path, os.path.join(dest_dir, os.path.basename(path)))


def process(path):
    with open(path, encoding="utf-8") as f:
        job = json.load(f)
    if not is_due(job):
        print(f"[queue] {job['id']} not due until {job['publish_at']}")
        return False

    cfg = render.load_channel(job["channel"])
    video = render.render(path, OUT, offline=os.environ.get("OFFLINE") == "1")
    job.setdefault("results", {})["rendered_at"] = now().isoformat()

    if job.get("mode", "post") == "draft":
        job["results"]["status"] = "draft_ready"
        move(path, job, "drafts")
        return True

    platforms = job.get("platforms") or cfg.get("platforms", [])
    if "youtube" in platforms:
        if has("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
            from . import upload_youtube
            job["results"]["youtube"] = upload_youtube.upload(video, job, cfg)
        else:
            job["results"]["youtube"] = "skipped: YouTube secrets not set"
    if "instagram" in platforms:
        if has("IG_USER_ID", "IG_ACCESS_TOKEN"):
            from . import upload_instagram
            job["results"]["instagram"] = upload_instagram.upload(video, job)
        else:
            job["results"]["instagram"] = "skipped: Instagram secrets not set"
    job["results"]["status"] = "posted"
    job["results"]["posted_at"] = now().isoformat()
    move(path, job, "done")
    return True


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "jobs", "queue", "*.json")))
    if len(sys.argv) > 1:  # optional: only a specific job id
        files = [f for f in files if sys.argv[1] in os.path.basename(f)]
    done = 0
    for path in files:
        if done >= MAX_JOBS:
            break
        try:
            if process(path):
                done += 1
        except Exception as exc:
            traceback.print_exc()
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            job["attempts"] = job.get("attempts", 0) + 1
            job.setdefault("results", {})["last_error"] = f"{type(exc).__name__}: {exc}"[:1000]
            if job["attempts"] >= MAX_ATTEMPTS:
                move(path, job, "failed")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(job, f, ensure_ascii=False, indent=2)
    print(f"[queue] processed {done} job(s)")


if __name__ == "__main__":
    main()
