"""Uploads a Short with the YouTube Data API v3, using a stored OAuth refresh token.

Secrets needed: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (get it once with tools/get_youtube_token.py).
Note: until Google audits your API project, uploads are forced to private.
"""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _client():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video_path: str, job: dict, channel_cfg: dict, privacy: str = "public") -> str:
    yt_cfg = channel_cfg.get("youtube", {})
    title = job["title"][:100]
    description = job.get("caption", "") + "\n\n" + " ".join(job.get("hashtags", []))
    tags = list(dict.fromkeys(yt_cfg.get("default_tags", []) + [h.lstrip("#") for h in job.get("hashtags", [])]))[:30]

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": yt_cfg.get("made_for_kids", False),
        "containsSyntheticMedia": yt_cfg.get("contains_synthetic_media", True),
    }
    body = {
        "snippet": {"title": title, "description": description[:4900], "tags": tags,
                    "categoryId": yt_cfg.get("category_id", "22"), "defaultLanguage": "hi"},
        "status": status,
    }
    request = _client().videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4"),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    url = f"https://youtube.com/shorts/{response['id']}"
    print(f"[youtube] uploaded {url} ({status['privacyStatus']})")
    return url
