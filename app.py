"""
Interactive webapp for ownership network visualization.
Data is loaded from Dropbox using credentials stored in Streamlit secrets.

Local development: set .streamlit/secrets.toml (see secrets.toml.example)
Deployment: set secrets in Streamlit Cloud app settings
"""
import streamlit as st
import pandas as pd
from data_loader import download_data_files
from network_utils import (
    load_data,
    build_graph_at_date,
    get_outlet_subgraph,
    get_name_map,
    build_pyvis_network,
    get_country_from_bvd_id,
)

st.set_page_config(
    page_title="Ownership Network Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Ownership Network Explorer")
st.markdown(
    "Explore the ownership structure of news outlets over time. "
    "Select an outlet, choose a date, and customize the visualization."
)


@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_all_data():
    """Download from Dropbox and load into dataframes."""
    try:
        path_data, path_orbis = download_data_files()
        outlet_societe_editrice, df_edges_dict = load_data(path_data, path_orbis)
        return outlet_societe_editrice, df_edges_dict, None
    except Exception as e:
        return None, None, str(e)


def get_available_dates(outlet_societe_editrice, id_news):
    """Get dates with data for the selected outlet."""
    subset = outlet_societe_editrice[outlet_societe_editrice["id_news"] == id_news]
    dates = subset["date"].dropna().unique()
    return sorted([pd.Timestamp(d) for d in dates if pd.notna(d)])


def main():
    outlet_societe_editrice, df_edges_dict, load_error = load_all_data()

    if load_error:
        st.error(f"Could not load data: {load_error}")
        st.info(
            "Check that your Streamlit secrets are correctly set. "
            "See `secrets.toml.example` for the required keys."
        )
        return

    # Sidebar: configuration
    with st.sidebar:
        st.header("Configuration")

        # Outlet selection
        outlets = (
            outlet_societe_editrice[["id_news", "name_outlet"]]
            .drop_duplicates()
            .sort_values("name_outlet")
        )
        outlet_options = {
            f"{row['name_outlet']} (id={row['id_news']})": row["id_news"]
            for _, row in outlets.iterrows()
        }

        selected_outlet_label = st.selectbox(
            "Select outlet",
            options=list(outlet_options.keys()),
            index=min(0, len(outlet_options) - 1),
        )
        id_news = outlet_options[selected_outlet_label]

        available_dates = get_available_dates(outlet_societe_editrice, id_news)
        if not available_dates:
            st.warning("No dates available for this outlet.")
            return

        # Date selection
        st.subheader("Date selection")
        compare_mode = st.checkbox("Compare two dates", value=False)

        date_options = [d.strftime("%Y-%m") for d in available_dates]
        default_idx = len(date_options) - 1 if date_options else 0

        date1_label = st.selectbox(
            "Date 1",
            options=date_options,
            index=default_idx,
            key="date1",
        )
        date1 = pd.Timestamp(f"{date1_label}-01")

        if compare_mode:
            date2_label = st.selectbox(
                "Date 2",
                options=date_options,
                index=max(0, default_idx - 1),
                key="date2",
            )
            date2 = pd.Timestamp(f"{date2_label}-01")
        else:
            date2 = None

        # Color customization
        st.subheader("Node colors")
        color_by = st.radio(
            "Color nodes by",
            options=["type", "country"],
            format_func=lambda x: "Type (outlet/SE/person/company)" if x == "type" else "Country",
        )

        st.subheader("Display options")
        show_labels = st.checkbox("Show node labels", value=True)
        height = st.slider("Graph height (px)", 400, 900, 600)

    # Build graphs
    rang0_nodes = set(
        df_edges_dict["rang0"][df_edges_dict["rang0"]["date"] == date1]["child_bvd_id"].unique()
    )

    se_at_date1 = outlet_societe_editrice[
        (outlet_societe_editrice["date"] == date1) & (outlet_societe_editrice["id_news"] == id_news)
    ]
    bvd_id_se1 = se_at_date1["bvd_id_se"].iloc[0] if not se_at_date1.empty else None

    G1_full = build_graph_at_date(
        date1, outlet_societe_editrice, df_edges_dict, rang0_nodes
    )
    G1 = get_outlet_subgraph(G1_full, id_news, bvd_id_se1)

    df_edges_date1 = pd.concat(
        [
            df_edges_dict["rang0"][df_edges_dict["rang0"]["date"] == date1],
            df_edges_dict["rang1"][df_edges_dict["rang1"]["date"] == date1],
            df_edges_dict["rang2"][df_edges_dict["rang2"]["date"] == date1],
        ],
        ignore_index=True,
    )
    name_map1 = get_name_map(G1_full, df_edges_date1, outlet_societe_editrice, date1)

    if compare_mode and date2 is not None:
        rang0_nodes2 = set(
            df_edges_dict["rang0"][df_edges_dict["rang0"]["date"] == date2]["child_bvd_id"].unique()
        )
        se_at_date2 = outlet_societe_editrice[
            (outlet_societe_editrice["date"] == date2)
            & (outlet_societe_editrice["id_news"] == id_news)
        ]
        bvd_id_se2 = se_at_date2["bvd_id_se"].iloc[0] if not se_at_date2.empty else None

        G2_full = build_graph_at_date(
            date2, outlet_societe_editrice, df_edges_dict, rang0_nodes2
        )
        G2 = get_outlet_subgraph(G2_full, id_news, bvd_id_se2)

        df_edges_date2 = pd.concat(
            [
                df_edges_dict["rang0"][df_edges_dict["rang0"]["date"] == date2],
                df_edges_dict["rang1"][df_edges_dict["rang1"]["date"] == date2],
                df_edges_dict["rang2"][df_edges_dict["rang2"]["date"] == date2],
            ],
            ignore_index=True,
        )
        name_map2 = get_name_map(G2_full, df_edges_date2, outlet_societe_editrice, date2)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"📅 {date1_label}")
            if G1 is None or G1.number_of_nodes() == 0:
                st.info("No network data for this date.")
            else:
                html1 = build_pyvis_network(
                    G1,
                    name_map1,
                    title=f"Network {date1_label}",
                    node_color_by=color_by,
                    height=f"{height}px",
                )
                st.components.v1.html(html1, height=height + 50, scrolling=False)

        with col2:
            st.subheader(f"📅 {date2_label}")
            if G2 is None or G2.number_of_nodes() == 0:
                st.info("No network data for this date.")
            else:
                html2 = build_pyvis_network(
                    G2,
                    name_map2,
                    title=f"Network {date2_label}",
                    node_color_by=color_by,
                    height=f"{height}px",
                )
                st.components.v1.html(html2, height=height + 50, scrolling=False)

        if G1 and G2:
            st.subheader("Summary")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(f"Nodes ({date1_label})", G1.number_of_nodes())
            with c2:
                st.metric(f"Edges ({date1_label})", G1.number_of_edges())
            with c3:
                st.metric(f"Nodes ({date2_label})", G2.number_of_nodes())
            with c4:
                st.metric(f"Edges ({date2_label})", G2.number_of_edges())

    else:
        st.subheader(f"Network — {date1_label}")
        if G1 is None or G1.number_of_nodes() == 0:
            st.info("No network data for this date.")
        else:
            html = build_pyvis_network(
                G1,
                name_map1,
                title=f"Network {date1_label}",
                node_color_by=color_by,
                height=f"{height}px",
            )
            st.components.v1.html(html, height=height + 50, scrolling=False)

            st.caption(
                "**Hover** over nodes to see firm name, type, and country. "
                "**Drag** to pan, **scroll** to zoom."
            )

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Nodes", G1.number_of_nodes())
            with c2:
                st.metric("Edges", G1.number_of_edges())


if __name__ == "__main__":
    main()
