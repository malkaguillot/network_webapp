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
    except ImportError:
        raise ImportError("dropbox package not installed. Add 'dropbox' to requirements.txt.")
    return dropbox.Dropbox(
        oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"],
        app_key=st.secrets["DROPBOX_APP_KEY"],
        app_secret=st.secrets["DROPBOX_APP_SECRET"],
    )


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

    files_to_download = {
        f"{base}/outlet_id_record.xlsx": os.path.join(tmpdir, "outlet_id_record.xlsx"),
        f"{base}/Orbis/clean/actionnaires_rang0_with_rang1_TS.csv": os.path.join(
            orbis_clean_dir, "actionnaires_rang0_with_rang1_TS.csv"
        ),
        f"{base}/Orbis/clean/actionnaires_rang1_with_rang2_TS.csv": os.path.join(
            orbis_clean_dir, "actionnaires_rang1_with_rang2_TS.csv"
        ),
        f"{base}/Orbis/clean/actionnaires_rang2_with_rang3_TS.csv": os.path.join(
            orbis_clean_dir, "actionnaires_rang2_with_rang3_TS.csv"
        ),
    }

    for dropbox_path, local_path in files_to_download.items():
        dbx.files_download_to_file(local_path, dropbox_path)

    path_orbis = os.path.join(tmpdir, "Orbis")
    return tmpdir, path_orbis
