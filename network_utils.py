"""
Network graph utilities for ownership network visualization.
Extracted from network_id_news_over_time.ipynb
"""
import os
import pandas as pd
import numpy as np
import networkx as nx
from pyvis.network import Network
from typing import Optional, Dict, Any, Tuple

# ISO country codes (common ones for BvD IDs)
COUNTRY_CODES = {
    "FR": "France", "BE": "Belgium", "LU": "Luxembourg", "DE": "Germany",
    "ES": "Spain", "IT": "Italy", "NL": "Netherlands", "GB": "United Kingdom",
    "CH": "Switzerland", "US": "United States", "ZZ": "Unknown",
}

# Default colors for country-based coloring
COUNTRY_COLORS = {
    "France": "#3498db",
    "Belgium": "#9b59b6",
    "Luxembourg": "#e67e22",
    "Germany": "#1abc9c",
    "Spain": "#e74c3c",
    "Italy": "#2ecc71",
    "Netherlands": "#f39c12",
    "United Kingdom": "#34495e",
    "Switzerland": "#16a085",
    "United States": "#2980b9",
    "Person": "#2c3e50",
    "Unknown": "#95a5a6",
}


def get_country_from_bvd_id(bvd_id: str) -> str:
    """Extract country from BvD ID. First 2 chars are ISO code, or P for person."""
    if pd.isna(bvd_id) or not isinstance(bvd_id, str):
        return "Unknown"
    s = str(bvd_id).strip()
    if s.startswith("P") or s.startswith("ZZ"):
        return "Person" if s.startswith("P") else COUNTRY_CODES.get("ZZ", "Unknown")
    code = s[:2].upper() if len(s) >= 2 else ""
    return COUNTRY_CODES.get(code, code or "Unknown")


def load_data(path_data: str, path_orbis: str) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Load outlet-societe editrice and ownership edge data."""
    # Outlet ↔ société éditrice
    outletXsocietee_editriceXdate = pd.read_excel(
        os.path.join(path_data, "outlet_id_record.xlsx"),
        sheet_name="outletXsocietee_editriceXdate",
        header=1,
    )

    outlet_societe_editrice_date = outletXsocietee_editriceXdate[
        outletXsocietee_editriceXdate["bvd_id_se"].notna()
        & outletXsocietee_editriceXdate["name_outlet"].notna()
        & outletXsocietee_editriceXdate["date_event"].notna()
    ][["name_outlet", "id_news", "name_se", "bvd_id_se", "date_event"]]

    outlet_societe_editrice_date["date_event"] = pd.to_datetime(
        outlet_societe_editrice_date["date_event"]
    )

    # Expand to monthly rows per outlet and carry the latest known editor backward in time.
    end_date = pd.Timestamp("2025-01-01")
    monthly_frames = []
    for (name_outlet, id_news), grp in outlet_societe_editrice_date.groupby(
        ["name_outlet", "id_news"], sort=False
    ):
        grp = grp.sort_values("date_event").drop_duplicates("date_event", keep="last")

        monthly = pd.DataFrame(
            {
                "date": pd.date_range(
                    start=grp["date_event"].min(),
                    end=end_date,
                    freq="MS",
                )
            }
        )
        source = grp[["date_event", "name_se", "bvd_id_se"]].rename(
            columns={"date_event": "date"}
        )

        expanded = pd.merge_asof(
            monthly.sort_values("date"),
            source.sort_values("date"),
            on="date",
            direction="backward",
        )
        expanded["name_outlet"] = name_outlet
        expanded["id_news"] = id_news
        monthly_frames.append(expanded[["name_outlet", "id_news", "name_se", "bvd_id_se", "date"]])

    outlet_societe_editrice = pd.concat(monthly_frames, ignore_index=True)

    # Parent-child ownership
    df_parents_of_rang0 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang0_with_rang1_TS.csv")
    )
    df_parents_of_rang0["date"] = pd.to_datetime(df_parents_of_rang0["date"])

    df_parents_of_rang1 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang1_with_rang2_TS.csv")
    )
    df_parents_of_rang1["date"] = pd.to_datetime(df_parents_of_rang1["date"])

    df_parents_of_rang2 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang2_with_rang3_TS.csv")
    )
    df_parents_of_rang2["date"] = pd.to_datetime(df_parents_of_rang2["date"])

    df_parents_of_rang3 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang3_with_rang4_TS.csv")
    )
    df_parents_of_rang3["date"] = pd.to_datetime(df_parents_of_rang3["date"])

    df_parents_of_rang4 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang4_with_rang5_TS.csv")
    )
    df_parents_of_rang4["date"] = pd.to_datetime(df_parents_of_rang4["date"])

    df_parents_of_rang5 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang5_with_rang6_TS.csv")
    )
    df_parents_of_rang5["date"] = pd.to_datetime(df_parents_of_rang5["date"])

    df_parents_of_rang6 = pd.read_csv(
        os.path.join(path_orbis, "clean", "actionnaires_rang6_with_rang7_TS.csv")
    )
    df_parents_of_rang6["date"] = pd.to_datetime(df_parents_of_rang6["date"])

    return outlet_societe_editrice, {
        "rang0": df_parents_of_rang0,
        "rang1": df_parents_of_rang1,
        "rang2": df_parents_of_rang2,
        "rang3": df_parents_of_rang3,
        "rang4": df_parents_of_rang4,
        "rang5": df_parents_of_rang5,
        "rang6": df_parents_of_rang6,
    }


def build_graph_at_date(
    date: pd.Timestamp,
    outlet_societe_editrice: pd.DataFrame,
    df_edges: Dict[str, pd.DataFrame],
    rang0_nodes: set,
) -> nx.DiGraph:
    """Build the full ownership graph for a given date."""
    G = nx.DiGraph()
    date_str = date.strftime("%Y-%m-%d")

    # Outlet → société éditrice
    se_at_date = outlet_societe_editrice[outlet_societe_editrice["date"] == date]
    for _, row in se_at_date.iterrows():
        G.add_node(
            row["id_news"],
            is_outlet=True,
            is_se=False,
            parent_is_person=False,
            name=row["name_outlet"],
        )
        G.add_node(
            row["bvd_id_se"],
            is_outlet=False,
            is_se=True,
            parent_is_person=False,
            name=row["name_se"],
        )
        G.add_edge(row["id_news"], row["bvd_id_se"], weight=100)

    # Rang 0 to 2: parent → child
    all_edges = pd.concat(
        [
            df_edges["rang0"][df_edges["rang0"]["date"] == date],
            df_edges["rang1"][df_edges["rang1"]["date"] == date],
            df_edges["rang2"][df_edges["rang2"]["date"] == date],
            df_edges["rang3"][df_edges["rang3"]["date"] == date],
            df_edges["rang4"][df_edges["rang4"]["date"] == date],
            df_edges["rang5"][df_edges["rang5"]["date"] == date],
            df_edges["rang6"][df_edges["rang6"]["date"] == date],
        ],
        ignore_index=True,
    )

    if all_edges.empty:
        wccs = list(nx.weakly_connected_components(G))
        nodes_to_keep = set()
        for comp in wccs:
            if comp & rang0_nodes:
                nodes_to_keep |= comp
        if nodes_to_keep:
            G = G.subgraph(nodes_to_keep).copy()
        return G

    all_edges = all_edges.copy()
    all_edges["parent_is_person"] = (
        all_edges["parent_bvd_id"].str.startswith("P")
        | all_edges["parent_name"].str.startswith(("MME ", "MR "), na=False)
    )

    for bvd_id in pd.unique(all_edges[["child_bvd_id", "parent_bvd_id"]].values.ravel("K")):
        is_se = bvd_id in rang0_nodes
        parent_is_person = False
        if bvd_id in all_edges["parent_bvd_id"].values:
            rows = all_edges[all_edges["parent_bvd_id"] == bvd_id]
            if not rows.empty:
                parent_is_person = bool(rows["parent_is_person"].iloc[0])
        name = None
        if bvd_id in all_edges["child_bvd_id"].values:
            name = all_edges[all_edges["child_bvd_id"] == bvd_id]["child_name"].iloc[0]
        elif bvd_id in all_edges["parent_bvd_id"].values:
            name = all_edges[all_edges["parent_bvd_id"] == bvd_id]["parent_name"].iloc[0]
        G.add_node(
            bvd_id,
            is_outlet=False,
            is_se=is_se,
            parent_is_person=parent_is_person,
            name=name,
        )

    for _, row in all_edges.iterrows():
        G.add_edge(
            row["parent_bvd_id"],
            row["child_bvd_id"],
            weight=row["ownership_direct"],
        )

    wccs = list(nx.weakly_connected_components(G))
    nodes_to_keep = set()
    for comp in wccs:
        if comp & rang0_nodes:
            nodes_to_keep |= comp
    G = G.subgraph(nodes_to_keep).copy()
    return G


def get_outlet_subgraph(
    G: nx.DiGraph, id_news: int, bvd_id_se: Optional[str]
) -> Optional[nx.DiGraph]:
    """Extract subgraph for outlet + société éditrice + ownership chain."""
    if bvd_id_se is None or bvd_id_se not in G:
        return None
    nodes = {bvd_id_se} | nx.ancestors(G, bvd_id_se)
    if id_news in G:
        nodes = nodes | {id_news}
    return G.subgraph(nodes).copy()


def get_name_map(
    G: nx.DiGraph,
    df_edges: pd.DataFrame,
    outlet_societe_editrice: pd.DataFrame,
    date: pd.Timestamp,
) -> Dict[str, str]:
    """Build node id → display name mapping."""
    name_map = {}
    if not df_edges.empty:
        name_map.update(dict(zip(df_edges["child_bvd_id"], df_edges["child_name"])))
        name_map.update(dict(zip(df_edges["parent_bvd_id"], df_edges["parent_name"])))
    se_at_date = outlet_societe_editrice[outlet_societe_editrice["date"] == date]
    for _, row in se_at_date.iterrows():
        name_map[row["id_news"]] = row["name_outlet"]
        name_map[str(row["id_news"])] = row["name_outlet"]
        name_map[row["bvd_id_se"]] = row["name_se"]
    for node, data in G.nodes(data=True):
        if node not in name_map and "name" in data:
            name_map[node] = data["name"]
    return name_map


def build_pyvis_network(
    G: nx.DiGraph,
    name_map: Dict[str, str],
    title: str = "Ownership Network",
    node_color_by: str = "type",
    color_scheme: Optional[Dict[str, str]] = None,
    height: str = "600px",
) -> str:
    """
    Build pyvis Network and return HTML string.
    node_color_by: 'type' (outlet/se/person/company) or 'country'
    """
    if color_scheme is None:
        color_scheme = {
            "outlet": "#e74c3c",
            "societe_editrice": "#f39c12",
            "person": "#2c3e50",
            "company": "#3498db",
        }

    net = Network(height=height, width="100%", directed=True, notebook=False)
    net.set_options("""
    var options = {
      "nodes": {
        "font": {"size": 14},
        "borderWidth": 2
      },
      "edges": {
        "arrows": {"to": {"enabled": true}},
        "smooth": {"type": "cubicBezier"}
      },
      "physics": {
        "enabled": true,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "springLength": 150,
          "springConstant": 0.08
        }
      }
    }
    """)

    node_id_map = {}

    def _to_pyvis_id(value: Any):
        if isinstance(value, (str, int)):
            return value
        if isinstance(value, np.integer):
            return int(value)
        return str(value)

    for node, data in G.nodes(data=True):
        node_id = _to_pyvis_id(node)
        node_id_map[node] = node_id

        label = name_map.get(node, name_map.get(str(node), str(node)))
        country = get_country_from_bvd_id(node) if isinstance(node, str) else "N/A"

        if node_color_by == "country":
            color = COUNTRY_COLORS.get(country, "#95a5a6")
        else:
            if data.get("is_outlet"):
                color = color_scheme.get("outlet", "#e74c3c")
            elif data.get("is_se"):
                color = color_scheme.get("societe_editrice", "#f39c12")
            elif data.get("parent_is_person"):
                color = color_scheme.get("person", "#2c3e50")
            else:
                color = color_scheme.get("company", "#3498db")

        node_type = "Outlet" if data.get("is_outlet") else (
            "Société éditrice" if data.get("is_se") else (
                "Person" if data.get("parent_is_person") else "Company"
            )
        )

        tooltip = f"<b>{label}</b><br>Type: {node_type}<br>Country: {country}"
        if isinstance(node, str) and node.startswith(("FR", "BE", "LU")):
            tooltip += f"<br>BvD ID: {node}"
        net.add_node(node_id, label=str(label), color=color, title=tooltip)

    seen = set()
    for u, v, data in G.edges(data=True):
        w = data.get("weight")
        pct = float(w) if w is not None and not (isinstance(w, float) and np.isnan(w)) else 0
        u_id = node_id_map.get(u, _to_pyvis_id(u))
        v_id = node_id_map.get(v, _to_pyvis_id(v))
        key = (u_id, v_id)
        if key in seen:
            continue
        seen.add(key)
        net.add_edge(u_id, v_id, value=max(0.5, pct / 20), title=f"{pct}%")

    return net.generate_html(notebook=False)
