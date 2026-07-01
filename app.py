"""
Interactive webapp for ownership-network visualization (yearly).

Two sections per media:
  1. Réseau     — the ownership network for a selected year, with observed vs
                  estimated edges (solid vs dashed) and a media-group panel.
  2. Évolution  — time series of network statistics, with vertical bars marking
                  ownership-change events (lifi/orbis/claude).

Data comes from 5 app-ready CSVs (see data_loader.py / network_utils.py).
"""
import altair as alt
import pandas as pd
import streamlit as st

from data_loader import download_data_files
from network_utils import (
    CHANGE_SOURCE_COLORS,
    EDGE_STATUS_COLORS,
    EDGE_STATUS_DASHES,
    EDGE_STATUS_LABELS,
    build_outlet_graph,
    build_pyvis_network,
    get_available_years,
    get_group_info,
    get_outlets,
    group_color,
    load_app_data,
)

st.set_page_config(
    page_title="Ownership Network Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Ownership Network Explorer")
st.markdown(
    "Explorez la structure d'actionnariat des médias, année par année. "
    "Les liens sont colorés selon leur origine : **observé** (Orbis), **propagé** "
    "(report en attendant une nouvelle observation) ou **estimé** (résiduel)."
)


@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_all_data():
    try:
        folder = download_data_files()
        return load_app_data(folder), None
    except Exception as e:
        return None, str(e)


def _edge_legend():
    parts = []
    for status in ("observed", "propagated", "estimated"):
        color = EDGE_STATUS_COLORS[status]
        border = "dashed" if EDGE_STATUS_DASHES[status] else "solid"
        parts.append(
            f"<span style='display:inline-block;margin-right:16px;'>"
            f"<span style='display:inline-block;width:28px;border-top:3px {border} "
            f"{color};vertical-align:middle;'></span> {EDGE_STATUS_LABELS[status]}</span>"
        )
    st.markdown("<div style='margin:6px 0'>" + "".join(parts) + "</div>",
                unsafe_allow_html=True)


def render_network(data, id_news, year, color_by, height, show_labels):
    """Render the pyvis network + metrics + group panel for a media-year."""
    G = build_outlet_graph(year, id_news, data)
    if G is None or G.number_of_nodes() == 0:
        st.info("Pas de données réseau pour cette année.")
        return

    group = get_group_info(data, id_news, year)
    group_label = group["label"] if group else None

    html = build_pyvis_network(
        G,
        node_color_by=color_by,
        group_label=group_label,
        height=f"{height}px",
        show_labels=show_labels,
    )
    st.components.v1.html(html, height=height + 50, scrolling=False)
    _edge_legend()

    c1, c2 = st.columns(2)
    c1.metric("Nœuds", G.number_of_nodes())
    c2.metric("Arêtes", G.number_of_edges())

    if group:
        chip = (
            f"<span style='background:{group_color(group_label)};color:white;"
            f"padding:2px 8px;border-radius:4px'>{group_label}</span>"
        )
        st.markdown(f"**Groupe :** {chip}", unsafe_allow_html=True)
        if group["sibling_names"]:
            st.caption(
                f"{group['size']} médias dans ce groupe en {year}. "
                f"Autres médias : {', '.join(group['sibling_names'])}"
            )
        else:
            st.caption(f"Seul média de son groupe en {year}.")


# Statistic panels: (column(s), human title)
STAT_PANELS = [
    (["n_nodes", "n_edges"], "Taille du réseau (nœuds & arêtes)"),
    (["hhi_direct", "hhi_ultimate"], "Concentration (HHI direct & ultime)"),
    (["n_ultimate_owners", "max_depth"], "Propriétaires ultimes & profondeur"),
    (["n_edges_observed", "n_edges_propagated", "n_edges_estimated"],
     "Arêtes : observées / propagées / estimées"),
]


def render_evolution(data, id_news):
    """Render 4 Altair line charts over time + change-event vertical bars."""
    stats = data["stats"][data["stats"]["id_news"] == id_news].copy()
    if stats.empty:
        st.info("Pas de séries statistiques pour ce média.")
        return
    stats["date"] = pd.to_datetime(stats["year"].astype(str) + "-01-01")

    changes = data["changes"][data["changes"]["id_news"] == id_news].copy()

    for cols, title in STAT_PANELS:
        st.markdown(f"**{title}**")
        cols = [c for c in cols if c in stats.columns]
        long = stats.melt(
            id_vars=["date"], value_vars=cols, var_name="série", value_name="valeur"
        ).dropna(subset=["valeur"])
        line = (
            alt.Chart(long)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="Année",
                        axis=alt.Axis(format="%Y", labelAngle=0, tickCount=6)),
                y=alt.Y("valeur:Q", title=""),
                color=alt.Color("série:N", title=""),
                tooltip=["date:T", "série:N", "valeur:Q"],
            )
        )
        layers = [line]
        if not changes.empty:
            rule = (
                alt.Chart(changes)
                .mark_rule(strokeWidth=2, strokeDash=[4, 3])
                .encode(
                    x="date:T",
                    color=alt.Color(
                        "source:N",
                        title="Changement",
                        scale=alt.Scale(
                            domain=list(CHANGE_SOURCE_COLORS.keys()),
                            range=list(CHANGE_SOURCE_COLORS.values()),
                        ),
                    ),
                    tooltip=["source:N", "date:T"],
                )
            )
            layers.append(rule)
        st.altair_chart(
            alt.layer(*layers)
            .resolve_scale(color="independent")
            .properties(
                height=220,
                autosize=alt.AutoSizeParams(type="fit", contains="padding"),
            ),
            width="stretch",
        )

    st.caption(
        "Barres verticales = changements d'actionnariat : "
        "**lifi**/**claude** à l'année, **orbis** au mois."
    )


def main():
    data, load_error = load_all_data()
    if load_error:
        st.error(f"Impossible de charger les données : {load_error}")
        st.info("Vérifiez les secrets Streamlit (voir `secrets.toml.example`).")
        return

    with st.sidebar:
        st.header("Configuration")

        outlets = get_outlets(data)
        outlet_options = {
            f"{row['name_outlet']} (id={row['id_news']})": int(row["id_news"])
            for _, row in outlets.iterrows()
        }
        selected_label = st.selectbox("Média", options=list(outlet_options.keys()))
        id_news = outlet_options[selected_label]

        years = get_available_years(data, id_news)
        if not years:
            st.warning("Aucune année disponible pour ce média.")
            return

        st.subheader("Année")
        compare_mode = st.checkbox("Comparer deux années", value=False)
        year1 = st.selectbox("Année 1", options=years, index=len(years) - 1, key="year1")
        year2 = None
        if compare_mode:
            year2 = st.selectbox(
                "Année 2", options=years, index=max(0, len(years) - 2), key="year2"
            )

        st.subheader("Couleur des nœuds")
        color_by = st.radio(
            "Colorer par",
            options=["type", "country", "group"],
            format_func=lambda x: {
                "type": "Type (outlet/SE/personne/société)",
                "country": "Pays",
                "group": "Groupe (propriétaire ultime)",
            }[x],
        )

        st.subheader("Affichage")
        show_labels = st.checkbox("Étiquettes des nœuds", value=True)
        height = st.slider("Hauteur du graphe (px)", 400, 900, 600)

    tab_net, tab_evo = st.tabs(["🕸️ Réseau", "📈 Évolution"])

    with tab_net:
        if compare_mode and year2 is not None:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"📅 {year1}")
                render_network(data, id_news, year1, color_by, height, show_labels)
            with col2:
                st.subheader(f"📅 {year2}")
                render_network(data, id_news, year2, color_by, height, show_labels)
        else:
            st.subheader(f"Réseau — {year1}")
            render_network(data, id_news, year1, color_by, height, show_labels)
            st.caption(
                "**Survolez** les nœuds pour le détail, **glissez** pour déplacer, "
                "**molette** pour zoomer."
            )

    with tab_evo:
        st.subheader(f"Évolution — {selected_label}")
        render_evolution(data, id_news)


if __name__ == "__main__":
    main()
