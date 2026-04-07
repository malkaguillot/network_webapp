# Ownership Network Explorer

Interactive Streamlit app for exploring the ownership structure of news outlets over time.

## Deployment (Streamlit Community Cloud)

### Recommended: Dropbox Shared Links (works everywhere)

This is the default and recommended mode for **both local development and cloud deployment**.

No API keys or authentication needed — just Dropbox shared links.

1. Generate Dropbox shared links for your data files:

   - In Dropbox web interface: right-click each file → **Share** → **Copy link**
   - Save the links
2. Configure secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

```toml
# Primary (recommended): Dropbox shared links
DROPBOX_URL_OUTLET_ID_RECORD = "https://www.dropbox.com/.../outlet_id_record.xlsx?..."
DROPBOX_URL_RANG0            = "https://www.dropbox.com/.../actionnaires_rang0_with_rang1_TS.csv?..."
DROPBOX_URL_RANG1            = "https://www.dropbox.com/.../actionnaires_rang1_with_rang2_TS.csv?..."
DROPBOX_URL_RANG2            = "https://www.dropbox.com/.../actionnaires_rang2_with_rang3_TS.csv?..."
```

The app automatically converts `?dl=0` to `?dl=1` for direct download.

This works on: 

- Local development (macOS, Linux, Windows)
- Streamlit Community Cloud
- Any other deployment

### Optional: Local Dropbox Desktop folder (dev only)

```toml
DROPBOX_LOCAL_DATA_FOLDER = "/Users/yourname/Dropbox/.../data/source"
```

This folder must contain:

```
outlet_id_record.xlsx
Orbis/clean/actionnaires_rang0_with_rang1_TS.csv
Orbis/clean/actionnaires_rang1_with_rang2_TS.csv
Orbis/clean/actionnaires_rang2_with_rang3_TS.csv
```

### Legacy: Dropbox API (not recommended)

If shared links don't work for your use case, you can fall back to Dropbox API credentials.
See `.streamlit/secrets.toml.example` for instructions.

`secrets.toml` is gitignored — it never gets committed.

## Deploy on Streamlit Cloud

Push this repo to GitHub, then:

1. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Select your repo, branch `main`, main file `app.py`
3. In **Advanced settings → Secrets**, paste your secrets (Dropbox URLs)
4. Deploy

## Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

You must have `.streamlit/secrets.toml` configured with your Dropbox URLs (or local folder / API credentials).
