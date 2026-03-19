"""Run this once to generate Dropbox OAuth credentials for Streamlit secrets."""
from dropbox import DropboxOAuth2FlowNoRedirect

app_key = input("Enter DROPBOX_APP_KEY: ").strip()
app_secret = input("Enter DROPBOX_APP_SECRET: ").strip()

flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type="offline")

print("1. Open this URL in your browser:")
print()
print("  ", flow.start())
print()
code = input("2. Paste the auth code here: ").strip()
result = flow.finish(code)

print()
print("=== OAuth result ===")
print("access_token  :", result.access_token)
print("refresh_token :", result.refresh_token)
print("account_id    :", result.account_id)
print()

print("SUCCESS — copy this into .streamlit/secrets.toml:")
print()
print(f'DROPBOX_APP_KEY       = "{app_key}"')
print(f'DROPBOX_APP_SECRET    = "{app_secret}"')
print(f'DROPBOX_REFRESH_TOKEN = "{result.refresh_token}"')
print()
print("Optional legacy fallback only:")
print(f'DROPBOX_ACCESS_TOKEN  = "{result.access_token}"')
