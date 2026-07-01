# Ownership Network Explorer

Interactive Streamlit app for exploring the ownership structure of news outlets **year by year**.

For each media, two sections:
1. **Réseau** — the ownership network for a selected year. Observed links are drawn solid,
   estimated (propagated) links dashed. Nodes can be colored by type, country, or **media group**
   (common ultimate owner). A panel lists the other media of the same group.
2. **Évolution** — time series of network statistics (network size, HHI concentration, number of
   ultimate owners, depth, observed vs estimated share), with **vertical bars marking
   ownership-change events** (lifi / orbis / claude; lifi & claude at yearly resolution, orbis at
   the month of the observed snapshot).

## Data

The app consumes **5 "app-ready" CSVs** produced by the companion project
`journalism-quality` (`code/2-clean-merge-sources/orbis/build_app_data.py`), written to
`data/source/Orbis/network/app/`:

```
app_edges_by_year.csv        # yearly ownership edges + is_estimated flag
app_outlet_se_by_year.csv    # outlet <-> société éditrice (yearly)
app_groups_by_year.csv       # media group = claude_ultimate_owner label (yearly)
app_outlet_stats_by_year.csv # per-media network-statistics time series
app_changes.csv              # ownership-change events (bars)
```

To regenerate them, run in the companion project:

```bash
python code/2-clean-merge-sources/orbis/build_app_data.py
```

## Configuration

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and choose one mode:

- **Dropbox shared links (recommended, works everywhere)** — set all 5 `DROPBOX_URL_APP_*` links.
  The app forces `?dl=1` automatically.
- **Local folder (dev only)** — `DROPBOX_LOCAL_APP_FOLDER = ".../data/source/Orbis/network/app"`.
- **Dropbox API (legacy)** — `DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN` + `DROPBOX_APP_DATA_FOLDER`.

`secrets.toml` is gitignored — it never gets committed.

## Deploy on Streamlit Cloud

Push this repo to GitHub, then:

1. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Select your repo, branch `main`, main file `app.py`
3. In **Advanced settings → Secrets**, paste the 5 `DROPBOX_URL_APP_*` links
4. Deploy

## Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

You must have `.streamlit/secrets.toml` configured (shared links or local folder).
