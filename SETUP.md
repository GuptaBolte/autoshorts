# One-time setup (about 1-2 hours, done once)

Everything here needs you personally: your accounts, your consent clicks. After this, posting runs without you.

## 1. GitHub (5 min)
1. Go to https://github.com/new, name the repo `autoshorts`, choose **Private**, and leave it empty (no README).
2. Tell Claude it exists. Claude pushes the code.

## 2. YouTube (30-40 min)
1. Create the channel: YouTube → profile picture → **Create a channel** (a separate brand channel is best).
2. Open https://console.cloud.google.com → **New project** → name it `autoshorts`.
3. **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.
4. **APIs & Services → OAuth consent screen** → **External** → fill in the app name and your email → on Scopes, add `.../auth/youtube.upload` → add your Gmail as a **Test user** → save.
5. On the consent screen page, click **Publish app** (move it to "In production"). This matters: in Testing mode the token dies after 7 days. The "unverified app" warning is fine for your own use.
6. **Credentials → Create credentials → OAuth client ID → Desktop app** → **Download JSON**, saved as `client_secret.json`.
7. On your computer (needs Python):
   ```
   pip install google-auth-oauthlib
   python tools/get_youtube_token.py client_secret.json
   ```
   Sign in with the channel's account, choose the channel, and click **Allow**. Copy the three printed values.
8. Apply for the audit (lifts the private-only upload lock): search "YouTube API Services Audit and Quota Extension Form" and submit it. Until it's approved, videos upload as **private**, and you flip them public in YouTube Studio with one click.

## 3. Instagram (20-30 min)
1. In the Instagram app: **Settings → Account type and tools → Switch to professional account** (Creator or Business).
2. Go to https://developers.facebook.com → **My Apps → Create app** → use case **"Manage messaging & content on Instagram"**.
3. In the app: **Instagram → API setup with Instagram login** → **Add account** → log in with the Instagram account → **Generate token**.
   Make sure the permissions include `instagram_business_basic` and `instagram_business_content_publish`.
4. Copy the **access token** and the **Instagram user ID** shown there.
   No app review is needed, because you're publishing only to your own account.
5. The token lasts 60 days. Claude can remind you to refresh it.

## 4. Add secrets to GitHub (5 min)
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `YT_CLIENT_ID` | from step 2.7 |
| `YT_CLIENT_SECRET` | from step 2.7 |
| `YT_REFRESH_TOKEN` | from step 2.7 |
| `IG_USER_ID` | from step 3.4 |
| `IG_ACCESS_TOKEN` | from step 3.4 |

Never paste these into the chat; they go only into GitHub secrets.

## 5. Music (optional, 10 min)
Download 5-10 calm instrumental tracks from YouTube Studio → **Audio Library** (filter: no attribution required) and put the MP3s in `assets/music/spiritual/`. Without music, videos have voice only.

## Done
Say `post: <idea>` in the chat.
