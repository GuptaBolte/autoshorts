"""Run ONCE on your own computer to get the YouTube refresh token.

  pip install google-auth-oauthlib
  python get_youtube_token.py client_secret.json

A browser opens; sign in with the channel's Google account and click Allow.
Copy the three printed values into GitHub > Settings > Secrets and variables > Actions.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1] if len(sys.argv) > 1 else "client_secret.json",
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nYT_CLIENT_ID     =", creds.client_id)
print("YT_CLIENT_SECRET =", creds.client_secret)
print("YT_REFRESH_TOKEN =", creds.refresh_token)
