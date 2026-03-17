# Ownership Network Explorer

Interactive Streamlit app for exploring the ownership structure of news outlets over time.

## Deployment (Streamlit Community Cloud)

### 1. Set up Dropbox credentials

Create a Dropbox app at [dropbox.com/developers](https://www.dropbox.com/developers/apps):
- Choose **Scoped access** → **Full Dropbox** (or a scoped folder)
- Note your **App key** and **App secret**

Generate a **refresh token** (long-lived):
```bash
pip install dropbox
python - <<'EOF'
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect

APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"

auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET, token_access_type="offline")
print("Go to:", auth_flow.start())
code = input("Enter auth code: ").strip()
result = auth_flow.finish(code)
print("Refresh token:", result.refresh_token)
EOF
```

### 2. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

```toml
DROPBOX_APP_KEY       = "..."
DROPBOX_APP_SECRET    = "..."
DROPBOX_REFRESH_TOKEN = "..."
DROPBOX_DATA_FOLDER   = "/path/in/dropbox/to/data/source"
```

`secrets.toml` is gitignored — it never gets committed.

### 3. Deploy on Streamlit Cloud

1. Push this repo to GitHub (public)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select repo, branch `main`, main file `app.py`
4. In **Advanced settings → Secrets**, paste the contents of your `secrets.toml`
5. Deploy

### Local development

```bash
pip install -r requirements.txt
# fill in .streamlit/secrets.toml
streamlit run app.py
```

## Data files expected in Dropbox

Under `DROPBOX_DATA_FOLDER`:
```
outlet_id_record.xlsx
Orbis/clean/actionnaires_rang0_with_rang1_TS.csv
Orbis/clean/actionnaires_rang1_with_rang2_TS.csv
Orbis/clean/actionnaires_rang2_with_rang3_TS.csv
```
