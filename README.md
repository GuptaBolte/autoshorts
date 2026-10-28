# autoshorts

Idea in chat → script → Hindi voice → AI images → captions + music → YouTube Shorts + Instagram Reels. Runs on GitHub Actions at ₹0.

## How you use it (from the Claude chat)

| You say | What happens |
|---|---|
| `post: <idea>` | Claude writes the script, adds a job to `jobs/queue`, the workflow renders and publishes. Links come back in the job file. |
| `draft: <idea>` | Same, but the video only renders. Claude sends it to you to watch. |
| `approve <id>` | The draft is re-queued in post mode and goes live. |
| `schedule: <idea> at 7pm tomorrow` | Job gets `publish_at`; it posts at the next check after that time. |
| nothing | A daily scheduled Claude task picks a fresh topic (avoiding past ones) and queues it. |

## Pieces

- `pipeline/render.py`: job JSON → 1080x1920 MP4 (edge-tts voice, Pollinations images, slow zoom, ASS captions, music bed)
- `pipeline/upload_youtube.py`, `pipeline/upload_instagram.py`: publishing
- `pipeline/run_queue.py`: processes due jobs, moves them to `done/`, `drafts/` or `failed/` with results
- `channels/<name>/`: `config.json` (voice, visual style, platforms) and `style_bible.md` (how scripts are written)
- `.github/workflows/publish.yml`: runs on every new job and 4x daily for scheduled ones

## Free-tier limits

- GitHub Actions (private repo): 2,000 min/month; one video takes about 3-5 min.
- YouTube API: about 6 uploads/day on the default quota.
- edge-tts and Pollinations are free, unofficial services. If either breaks, swap in a paid provider in one file.

Test locally without network: `OFFLINE=1 python -m pipeline.run_queue`
