"""Publishes a Reel through the Instagram API (resumable upload, so no public video hosting is needed).

Secrets needed: IG_USER_ID, IG_ACCESS_TOKEN.
Optional: IG_GRAPH_HOST (default graph.instagram.com for "Instagram Login";
          use graph.facebook.com if you set up via a Facebook Page), IG_API_VERSION.
"""
import json
import os
import time
import urllib.parse
import urllib.request

HOST = os.environ.get("IG_GRAPH_HOST", "graph.instagram.com")
VER = os.environ.get("IG_API_VERSION", "v21.0")


def _req(method, url, data=None, headers=None, body=None):
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"Instagram API {err.code}: {err.read().decode(errors='ignore')}") from None


def upload(video_path: str, job: dict, share_to_feed: bool = True) -> str:
    token, user = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    caption = (job.get("caption", "") + "\n\n" + " ".join(job.get("hashtags", [])))[:2200]

    # 1) create a resumable Reel container
    container = _req("POST", f"https://{HOST}/{VER}/{user}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": str(share_to_feed).lower(), "access_token": token,
    })["id"]

    # 2) push the bytes
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        _req("POST", f"https://rupload.facebook.com/ig-api-upload/{VER}/{container}",
             headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}, body=f.read())

    # 3) wait for Instagram to process the video
    for _ in range(60):
        st = _req("GET", f"https://{HOST}/{VER}/{container}?fields=status_code,status&access_token={token}")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")

    # 4) publish
    media_id = _req("POST", f"https://{HOST}/{VER}/{user}/media_publish",
                    data={"creation_id": container, "access_token": token})["id"]
    link = _req("GET", f"https://{HOST}/{VER}/{media_id}?fields=permalink&access_token={token}").get("permalink", media_id)
    print(f"[instagram] published {link}")
    return link
