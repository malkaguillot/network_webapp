"""
Download data files from Dropbox to a temporary directory.
Credentials and paths are read from Streamlit secrets.

Required secrets (set in Streamlit Cloud or .streamlit/secrets.toml):
    Preferred for local development (Dropbox Desktop):
        DROPBOX_LOCAL_DATA_FOLDER = "/Users/.../Dropbox/.../data/source"

    Preferred (robust, auto-refresh):
        DROPBOX_APP_KEY        = "..."
        DROPBOX_APP_SECRET     = "..."
        DROPBOX_REFRESH_TOKEN  = "..."

    Legacy fallback (less robust):
        DROPBOX_ACCESS_TOKEN   = "sl.u..."

    DROPBOX_DATA_FOLDER    = "/path/to/your/data/source"  # Dropbox path
"""
import os
import shutil
import tempfile
import streamlit as st
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


_REQUIRED_RELATIVE_FILES = [
    "outlet_id_record.xlsx",
    "Orbis/clean/actionnaires_rang0_with_rang1_TS.csv",
    "Orbis/clean/actionnaires_rang1_with_rang2_TS.csv",
    "Orbis/clean/actionnaires_rang2_with_rang3_TS.csv",
]

_REQUIRED_SHARED_LINK_KEYS = {
    "DROPBOX_URL_OUTLET_ID_RECORD": "outlet_id_record.xlsx",
    "DROPBOX_URL_RANG0": "Orbis/clean/actionnaires_rang0_with_rang1_TS.csv",
    "DROPBOX_URL_RANG1": "Orbis/clean/actionnaires_rang1_with_rang2_TS.csv",
    "DROPBOX_URL_RANG2": "Orbis/clean/actionnaires_rang2_with_rang3_TS.csv",
}


def _validate_local_data_folder(local_base: str):
    missing = [
        rel_path
        for rel_path in _REQUIRED_RELATIVE_FILES
        if not os.path.exists(os.path.join(local_base, rel_path))
    ]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "DROPBOX_LOCAL_DATA_FOLDER is set, but required files are missing: "
            f"{missing_list}"
        )


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
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type.lower():
            raise RuntimeError(
                f"URL did not return a file payload: {url}. "
                "Check sharing permissions and ensure the link is correct."
            )
        shutil.copyfileobj(response, out)


def _download_from_shared_links():
    urls = {k: st.secrets.get(k, "") for k in _REQUIRED_SHARED_LINK_KEYS}
    configured = {k: bool(v) for k, v in urls.items()}

    if any(configured.values()) and not all(configured.values()):
        missing = [k for k, ok in configured.items() if not ok]
        raise RuntimeError(
            "Partial Dropbox URL configuration. Missing keys: " + ", ".join(missing)
        )
    if not all(configured.values()):
        st.warning("No Dropbox shared links configured (DROPBOX_URL_* keys missing)")
        return None

    tmpdir = tempfile.mkdtemp(prefix="network_webapp_urls_")
    try:
        for secret_key, rel_path in _REQUIRED_SHARED_LINK_KEYS.items():
            dest = os.path.join(tmpdir, rel_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                _download_url_to_file(urls[secret_key], dest)
            except Exception as e:
                st.error(f"Failed to download {secret_key}: {str(e)}")
                raise
        return tmpdir, os.path.join(tmpdir, "Orbis")
    except Exception as e:
        st.error(f"Shared link download failed. Falling back to other modes...")
        # Clean up temp directory on failure
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise


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

    # Preferred mode: short-lived access token refreshed automatically by SDK.
    if app_key and app_secret and refresh_token:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )
        auth_mode = "refresh_token"
    elif access_token:
        # Backward-compatible fallback.
        dbx = dropbox.Dropbox(oauth2_access_token=access_token)
        auth_mode = "access_token"
    else:
        raise RuntimeError(
            "Missing Dropbox credentials in secrets. Set either: "
            "(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN) "
            "or DROPBOX_ACCESS_TOKEN."
        )

    try:
        dbx.users_get_current_account()
    except AuthError as e:
        raise RuntimeError(
            "Dropbox authentication failed. "
            f"Current auth mode: {auth_mode}. "
            "Re-run get_refresh_token.py and update Streamlit secrets."
        ) from e

    return dbx


@st.cache_resource(show_spinner="Downloading data from Dropbox...")
def download_data_files():
    """
    Load required data using one of these modes (in order):
    1) Dropbox shared links (direct URLs)
    2) local Dropbox Desktop synced folder
    3) Dropbox API download to temp directory

    Returns (path_data, path_orbis) suitable for passing to network_utils.load_data().
    Cached for the lifetime of the app process.
    """
    # Try shared links first (no auth needed)
    try:
        url_mode = _download_from_shared_links()
        if url_mode is not None:
            st.success("✓ Data loaded from Dropbox shared links")
            return url_mode
    except Exception as e:
        st.error(f"Shared link download failed: {e}")
        st.info("Attempting fallback modes...")

    # Try local folder
    local_base = st.secrets.get("DROPBOX_LOCAL_DATA_FOLDER", "").rstrip("/")
    if local_base:
        try:
            _validate_local_data_folder(local_base)
            st.success("✓ Data loaded from local Dropbox Desktop folder")
            return local_base, os.path.join(local_base, "Orbis")
        except RuntimeError as e:
            st.error(f"Local folder validation failed: {e}")
            st.info("Attempting Dropbox API...")

    # Try API (fallback)
    try:
        dbx = _get_dropbox_client()
    except RuntimeError as e:
        st.error(f"All data loading modes failed: {e}")
        st.error("Configuration required. Set one of these in `.streamlit/secrets.toml`:")
        st.code("""
# Option 1 (RECOMMENDED - no auth needed):
DROPBOX_URL_OUTLET_ID_RECORD = "https://www.dropbox.com/..."
DROPBOX_URL_RANG0            = "https://www.dropbox.com/..."
DROPBOX_URL_RANG1            = "https://www.dropbox.com/..."
DROPBOX_URL_RANG2            = "https://www.dropbox.com/..."

# Option 2 (Local dev only):
DROPBOX_LOCAL_DATA_FOLDER = "/Users/yourname/Dropbox/.../data/source"

# Option 3 (Legacy):
DROPBOX_APP_KEY       = "..."
DROPBOX_APP_SECRET    = "..."
DROPBOX_REFRESH_TOKEN = "..."
""", language="toml")
        raise
    
    base = st.secrets.get("DROPBOX_DATA_FOLDER", "").rstrip("/")
    if not base:
        raise RuntimeError(
            "API mode selected but DROPBOX_DATA_FOLDER not set. "
            "Specify the Dropbox path where your data files are located."
        )

    tmpdir = tempfile.mkdtemp(prefix="network_webapp_")
    orbis_clean_dir = os.path.join(tmpdir, "Orbis", "clean")
    os.makedirs(orbis_clean_dir, exist_ok=True)

    def _download_with_fallback(local_path, candidates):
        last_error = None
        for dropbox_path in candidates:
            try:
                dbx.files_download_to_file(local_path, dropbox_path)
                return
            except Exception as e:
                last_error = e
        candidate_list = " or ".join(candidates)
        raise RuntimeError(
            f"Dropbox path not found or inaccessible: {candidate_list}. "
            "Check DROPBOX_DATA_FOLDER and app permissions."
        ) from last_error

    _download_with_fallback(
        os.path.join(tmpdir, "outlet_id_record.xlsx"),
        [f"{base}/outlet_id_record.xlsx"],
    )
    _download_with_fallback(
        os.path.join(orbis_clean_dir, "actionnaires_rang0_with_rang1_TS.csv"),
        [
            f"{base}/Orbis/clean/actionnaires_rang0_with_rang1_TS.csv",
            f"{base}/actionnaires_rang0_with_rang1_TS.csv",
        ],
    )
    _download_with_fallback(
        os.path.join(orbis_clean_dir, "actionnaires_rang1_with_rang2_TS.csv"),
        [
            f"{base}/Orbis/clean/actionnaires_rang1_with_rang2_TS.csv",
            f"{base}/actionnaires_rang1_with_rang2_TS.csv",
        ],
    )
    _download_with_fallback(
        os.path.join(orbis_clean_dir, "actionnaires_rang2_with_rang3_TS.csv"),
        [
            f"{base}/Orbis/clean/actionnaires_rang2_with_rang3_TS.csv",
            f"{base}/actionnaires_rang2_with_rang3_TS.csv",
        ],
    )

    path_orbis = os.path.join(tmpdir, "Orbis")
    return tmpdir, path_orbis
