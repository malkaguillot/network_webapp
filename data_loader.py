"""
Locate the 5 app-ready CSVs for the ownership-network webapp.

The files are produced by the companion project (build_app_data.py) and live in
`data/source/Orbis/network/app/`:
    app_edges_by_year.csv
    app_outlet_se_by_year.csv
    app_groups_by_year.csv
    app_outlet_stats_by_year.csv
    app_changes.csv

Loading modes (tried in order):
1) Dropbox shared links  — DROPBOX_URL_APP_* (one per file), works everywhere.
2) Local Dropbox folder  — DROPBOX_LOCAL_APP_FOLDER (folder with the 5 CSVs), dev only.
3) Dropbox API           — DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN + DROPBOX_APP_DATA_FOLDER.

`download_data_files()` returns the path to a folder containing the 5 CSVs.
"""
import os
import shutil
import tempfile
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import streamlit as st


# secret key -> file name
_SHARED_LINK_KEYS = {
    "DROPBOX_URL_APP_EDGES": "app_edges_by_year.csv",
    "DROPBOX_URL_APP_OUTLET_SE": "app_outlet_se_by_year.csv",
    "DROPBOX_URL_APP_GROUPS": "app_groups_by_year.csv",
    "DROPBOX_URL_APP_STATS": "app_outlet_stats_by_year.csv",
    "DROPBOX_URL_APP_CHANGES": "app_changes.csv",
}

_REQUIRED_FILES = list(_SHARED_LINK_KEYS.values())


def _to_direct_download_url(url: str) -> str:
    """Force Dropbox share links to file-download mode (dl=1)."""
    parsed = urlparse(url)
    if "dropbox.com" not in parsed.netloc.lower():
        return url
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["dl"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _download_url_to_file(url: str, local_path: str):
    direct_url = _to_direct_download_url(url)
    req = Request(direct_url, headers={"User-Agent": "network-webapp/1.0"})
    with urlopen(req, timeout=120) as response, open(local_path, "wb") as out:
        if "text/html" in response.headers.get("Content-Type", "").lower():
            raise RuntimeError(
                f"URL did not return a file payload: {url}. Check sharing permissions."
            )
        shutil.copyfileobj(response, out)


def _download_from_shared_links():
    urls = {k: st.secrets.get(k, "") for k in _SHARED_LINK_KEYS}
    configured = {k: bool(v) for k, v in urls.items()}

    if any(configured.values()) and not all(configured.values()):
        missing = [k for k, ok in configured.items() if not ok]
        raise RuntimeError("Partial Dropbox URL config. Missing: " + ", ".join(missing))
    if not all(configured.values()):
        return None

    tmpdir = tempfile.mkdtemp(prefix="network_webapp_urls_")
    try:
        for key, fname in _SHARED_LINK_KEYS.items():
            _download_url_to_file(urls[key], os.path.join(tmpdir, fname))
        return tmpdir
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _validate_local_folder(folder: str):
    missing = [f for f in _REQUIRED_FILES if not os.path.exists(os.path.join(folder, f))]
    if missing:
        raise RuntimeError(
            f"DROPBOX_LOCAL_APP_FOLDER is set but files are missing: {', '.join(missing)}"
        )


def _get_dropbox_client():
    try:
        import dropbox
        from dropbox.exceptions import AuthError
    except ImportError:
        raise ImportError("dropbox package not installed. Add 'dropbox' to requirements.txt.")

    app_key = st.secrets.get("DROPBOX_APP_KEY")
    app_secret = st.secrets.get("DROPBOX_APP_SECRET")
    refresh_token = st.secrets.get("DROPBOX_REFRESH_TOKEN")
    access_token = st.secrets.get("DROPBOX_ACCESS_TOKEN")

    if app_key and app_secret and refresh_token:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token, app_key=app_key, app_secret=app_secret
        )
    elif access_token:
        dbx = dropbox.Dropbox(oauth2_access_token=access_token)
    else:
        raise RuntimeError(
            "Missing Dropbox credentials. Set (DROPBOX_APP_KEY, DROPBOX_APP_SECRET, "
            "DROPBOX_REFRESH_TOKEN) or DROPBOX_ACCESS_TOKEN."
        )

    try:
        dbx.users_get_current_account()
    except AuthError as e:
        raise RuntimeError("Dropbox authentication failed. Re-run get_refresh_token.py.") from e
    return dbx


@st.cache_resource(show_spinner="Loading data from Dropbox...")
def download_data_files():
    """Return the path to a folder containing the 5 app-ready CSVs."""
    # 1) Shared links (no auth)
    try:
        folder = _download_from_shared_links()
        if folder is not None:
            return folder
    except Exception as e:
        st.error(f"Shared link download failed: {e}")
        st.info("Attempting fallback modes...")

    # 2) Local folder (dev)
    local = st.secrets.get("DROPBOX_LOCAL_APP_FOLDER", "").rstrip("/")
    if local:
        _validate_local_folder(local)
        return local

    # 3) Dropbox API
    try:
        dbx = _get_dropbox_client()
    except RuntimeError as e:
        st.error(f"All data loading modes failed: {e}")
        st.code(
            "# Option 1 (recommended): Dropbox shared links\n"
            'DROPBOX_URL_APP_EDGES     = "https://www.dropbox.com/..."\n'
            'DROPBOX_URL_APP_OUTLET_SE = "https://www.dropbox.com/..."\n'
            'DROPBOX_URL_APP_GROUPS    = "https://www.dropbox.com/..."\n'
            'DROPBOX_URL_APP_STATS     = "https://www.dropbox.com/..."\n'
            'DROPBOX_URL_APP_CHANGES   = "https://www.dropbox.com/..."\n\n'
            "# Option 2 (local dev):\n"
            'DROPBOX_LOCAL_APP_FOLDER  = "/Users/.../Orbis/network/app"\n',
            language="toml",
        )
        raise

    base = st.secrets.get("DROPBOX_APP_DATA_FOLDER", "").rstrip("/")
    if not base:
        raise RuntimeError("API mode selected but DROPBOX_APP_DATA_FOLDER not set.")

    tmpdir = tempfile.mkdtemp(prefix="network_webapp_")
    for fname in _REQUIRED_FILES:
        try:
            dbx.files_download_to_file(os.path.join(tmpdir, fname), f"{base}/{fname}")
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError(f"Dropbox path not found: {base}/{fname}") from e
    return tmpdir
