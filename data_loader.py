"""
Download data files from Dropbox to a temporary directory.
Credentials and paths are read from Streamlit secrets.

Required secrets (set in Streamlit Cloud or .streamlit/secrets.toml):
    DROPBOX_APP_KEY        = "..."
    DROPBOX_APP_SECRET     = "..."
    DROPBOX_REFRESH_TOKEN  = "..."
    DROPBOX_DATA_FOLDER    = "/path/to/your/data/source"  # Dropbox path
"""
import os
import tempfile
import streamlit as st


def _get_dropbox_client():
    try:
        import dropbox
        from dropbox.exceptions import AuthError
    except ImportError:
        raise ImportError("dropbox package not installed. Add 'dropbox' to requirements.txt.")

    # The OAuth2 no-redirect flow with token_access_type="offline" produces a
    # long-lived access token (sl.u.xxx) stored in DROPBOX_ACCESS_TOKEN.
    # It is used directly — no app key/secret needed at runtime.
    dbx = dropbox.Dropbox(oauth2_access_token=st.secrets["DROPBOX_ACCESS_TOKEN"])
    try:
        dbx.users_get_current_account()
    except AuthError as e:
        raise RuntimeError(
            "Dropbox authentication failed. Regenerate DROPBOX_ACCESS_TOKEN via "
            "get_refresh_token.py and update .streamlit/secrets.toml."
        ) from e
    return dbx


@st.cache_resource(show_spinner="Downloading data from Dropbox...")
def download_data_files():
    """
    Download all required data files from Dropbox to a temp directory.
    Returns (path_data, path_orbis) suitable for passing to network_utils.load_data().
    Cached for the lifetime of the app process.
    """
    dbx = _get_dropbox_client()
    base = st.secrets["DROPBOX_DATA_FOLDER"].rstrip("/")

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
