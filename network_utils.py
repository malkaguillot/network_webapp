"""
Network graph utilities for the ownership-network webapp.

Consumes the yearly "app-ready" CSVs produced by the companion project
(build_app_data.py): one observation per YEAR, with a clean observed/estimated
edge flag and a media-group label.

Files (see data_loader.py):
- app_edges_by_year.csv      : year, rank, child_bvd_id, child_name,
                               parent_bvd_id, parent_name, ownership_direct,
                               link_status (observed|propagated|estimated), parent_is_person
- app_outlet_se_by_year.csv  : year, id_news, name_outlet, name_se, bvd_id_se
- app_groups_by_year.csv     : year, id_news, group_label, group_size
- app_outlet_stats_by_year.csv : year, id_news, n_nodes, n_edges,
                               n_edges_observed, n_edges_propagated, n_edges_estimated,
                               share_observed, share_propagated, share_estimated,
                               hhi_direct, hhi_ultimate, n_ultimate_owners, max_depth
- app_changes.csv            : id_news, source (lifi|orbis|claude), date
"""
import os
import hashlib
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import networkx as nx
from pyvis.network import Network

# ISO country codes (common ones for BvD IDs)
COUNTRY_CODES = {
    "FR": "France", "BE": "Belgium", "LU": "Luxembourg", "DE": "Germany",
    "ES": "Spain", "IT": "Italy", "NL": "Netherlands", "GB": "United Kingdom",
    "CH": "Switzerland", "US": "United States", "ZZ": "Unknown",
}

COUNTRY_COLORS = {
    "France": "#3498db", "Belgium": "#9b59b6", "Luxembourg": "#e67e22",
    "Germany": "#1abc9c", "Spain": "#e74c3c", "Italy": "#2ecc71",
    "Netherlands": "#f39c12", "United Kingdom": "#34495e", "Switzerland": "#16a085",
    "United States": "#2980b9", "Person": "#2c3e50", "Unknown": "#95a5a6",
}

TYPE_COLORS = {
    "outlet": "#e74c3c",
    "societe_editrice": "#f39c12",
    "person": "#2c3e50",
    "company": "#3498db",
}

# Edge colors by provenance (3-way link_status)
EDGE_STATUS_COLORS = {
    "observed": "#2c3e50",    # solid dark — raw Orbis observation
    "propagated": "#2980b9",  # dashed blue — value carried forward from an observation
    "estimated": "#e67e22",   # dashed orange — residual reconstruction
}
EDGE_STATUS_LABELS = {
    "observed": "observé",
    "propagated": "propagé",
    "estimated": "estimé",
}
# Dash pattern per status. NB: dashes render poorly with cubicBezier smoothing and get
# swallowed on thick strokes -> the graph uses "continuous" + an explicit modest width.
EDGE_STATUS_DASHES = {
    "observed": False,
    "propagated": [10, 14],
    "estimated": [2, 12],
}

# Qualitative palette for group coloring (indexed by a stable hash of the label)
GROUP_PALETTE = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324",
    "#800000", "#aaffc3", "#808000", "#000075", "#a9a9a9", "#e6beff",
]

# Change-source colors (for the vertical bars in the evolution chart)
CHANGE_SOURCE_COLORS = {
    "lifi": "#1f77b4",
    "orbis": "#d62728",
    "claude": "#2ca02c",
}

# Owner-type colors — 5-category typology of the majority ultimate owner (2026-07-08).
OWNER_TYPE_COLORS = {
    "Multi-media group": "#1f77b4",
    "Single-media group": "#17becf",
    "Non media group": "#ff7f0e",
    "Famille / individu": "#9467bd",
    "Dispersé / étranger": "#2ca02c",
    "Inconnu": "#cfd8dc",
}

APP_FILES = {
    "edges": "app_edges_by_year.csv",
    "outlet_se": "app_outlet_se_by_year.csv",
    "groups": "app_groups_by_year.csv",
    "stats": "app_outlet_stats_by_year.csv",
    "changes": "app_changes.csv",
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


def group_color(label: Optional[str]) -> str:
    """Stable color for a group label (deterministic across reruns)."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return "#95a5a6"
    h = int(hashlib.md5(str(label).encode("utf-8")).hexdigest(), 16)
    return GROUP_PALETTE[h % len(GROUP_PALETTE)]


# --------------------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------------------
def load_app_data(folder: str) -> Dict[str, pd.DataFrame]:
    """Load the 5 app-ready CSVs from a folder into a dict of DataFrames."""
    def _read(key):
        return pd.read_csv(
            os.path.join(folder, APP_FILES[key]),
            dtype={"child_bvd_id": str, "parent_bvd_id": str, "bvd_id_se": str},
        )

    data = {k: _read(k) for k in APP_FILES}
    for k in ("edges", "outlet_se", "groups", "stats"):
        data[k]["year"] = data[k]["year"].astype(int)
    for k in ("outlet_se", "groups", "stats"):
        data[k]["id_news"] = data[k]["id_news"].astype(int)
    data["edges"]["link_status"] = data["edges"]["link_status"].astype(str)
    # owner_type / owner_canonical are optional (older app_groups_by_year.csv may lack them)
    if "owner_type" not in data["groups"].columns:
        data["groups"]["owner_type"] = "Inconnu"
    data["groups"]["owner_type"] = data["groups"]["owner_type"].fillna("Inconnu")
    if "owner_canonical" not in data["groups"].columns:
        data["groups"]["owner_canonical"] = data["groups"]["group_label"]
    data["groups"]["owner_canonical"] = data["groups"]["owner_canonical"].fillna(
        data["groups"]["group_label"]
    )
    data["changes"]["date"] = pd.to_datetime(data["changes"]["date"])
    data["changes"]["id_news"] = data["changes"]["id_news"].astype(int)
    return data


def get_outlets(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Distinct (id_news, name_outlet), sorted by name."""
    return (
        data["outlet_se"][["id_news", "name_outlet"]]
        .drop_duplicates()
        .sort_values("name_outlet")
        .reset_index(drop=True)
    )


def get_available_years(data: Dict[str, pd.DataFrame], id_news: int) -> list:
    """Years with an outlet-SE mapping for this media."""
    sub = data["outlet_se"][data["outlet_se"]["id_news"] == id_news]
    return sorted(int(y) for y in sub["year"].unique())


def get_group_info(data: Dict[str, pd.DataFrame], id_news: int, year: int) -> Optional[dict]:
    """Majority ultimate owner group (canonical name + category), size and siblings
    for a media-year. `canonical` is the homogenised entity name to display;
    `label` is the raw claude_ultimate_owner label; siblings share the same canonical
    group that year."""
    g = data["groups"]
    row = g[(g["id_news"] == id_news) & (g["year"] == year)]
    if row.empty:
        return None
    label = row["group_label"].iloc[0]
    canonical = row["owner_canonical"].iloc[0] if "owner_canonical" in row.columns else label
    siblings = data["groups"][
        (data["groups"]["year"] == year)
        & (data["groups"]["owner_canonical"] == canonical)
        & (data["groups"]["id_news"] != id_news)
    ]["id_news"].tolist()
    name_by_id = dict(
        zip(data["outlet_se"]["id_news"], data["outlet_se"]["name_outlet"])
    )
    sibling_names = sorted(name_by_id.get(i, str(i)) for i in siblings)
    owner_type = row["owner_type"].iloc[0] if "owner_type" in row.columns else "Inconnu"
    return {
        "label": label,
        "canonical": canonical,
        "size": int(row["group_size"].iloc[0]),
        "sibling_names": sibling_names,
        "owner_type": owner_type,
    }


def get_group_timeline(data: Dict[str, pd.DataFrame], id_news: int) -> pd.DataFrame:
    """Ownership spells for a media: consecutive years collapsed into one row per
    (canonical group, owner_type) period. Columns: start, end, owner_canonical,
    owner_type. Drives the 'group evolution' view in the Évolution tab."""
    g = (
        data["groups"][data["groups"]["id_news"] == id_news]
        .sort_values("year")
        [["year", "owner_canonical", "owner_type"]]
        .dropna(subset=["owner_canonical"])
    )
    if g.empty:
        return pd.DataFrame(columns=["start", "end", "owner_canonical", "owner_type"])
    # new spell whenever the canonical group changes vs the previous year
    grp_id = (g["owner_canonical"] != g["owner_canonical"].shift()).cumsum()
    spells = (
        g.groupby(grp_id)
        .agg(
            start=("year", "min"),
            end=("year", "max"),
            owner_canonical=("owner_canonical", "first"),
            owner_type=("owner_type", "first"),
        )
        .reset_index(drop=True)
    )
    return spells


# --------------------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------------------
def _build_full_year_graph(
    year: int, edges: pd.DataFrame, outlet_se: pd.DataFrame
) -> Tuple[nx.DiGraph, set]:
    """Full ownership graph for a year (all media), restricted to components that
    contain a société éditrice (rang0) node."""
    ey = edges[edges["year"] == year]
    oy = outlet_se[outlet_se["year"] == year]
    rang0_nodes = set(ey[ey["rank"] == 0]["child_bvd_id"].unique())

    # name lookup for firm nodes
    names = {}
    names.update(dict(zip(ey["child_bvd_id"], ey["child_name"])))
    names.update(dict(zip(ey["parent_bvd_id"], ey["parent_name"])))

    G = nx.DiGraph()
    for _, row in oy.iterrows():
        idn = int(row["id_news"])
        G.add_node(idn, is_outlet=True, is_se=False, parent_is_person=False,
                   name=row["name_outlet"])
        G.add_node(row["bvd_id_se"], is_outlet=False, is_se=True,
                   parent_is_person=False, name=row["name_se"])
        # SE -> outlet is a structural link, always observed.
        G.add_edge(row["bvd_id_se"], idn, weight=100, link_status="observed")

    for _, row in ey.iterrows():
        c, p = row["child_bvd_id"], row["parent_bvd_id"]
        for n in (c, p):
            if n not in G:
                G.add_node(n, is_outlet=False, is_se=(n in rang0_nodes),
                           parent_is_person=False, name=names.get(n, n))
        if bool(row["parent_is_person"]):
            G.nodes[p]["parent_is_person"] = True
        G.add_edge(p, c, weight=row["ownership_direct"],
                   link_status=str(row["link_status"]))

    keep = set()
    for comp in nx.weakly_connected_components(G):
        if comp & rang0_nodes:
            keep |= comp
    return G.subgraph(keep).copy(), rang0_nodes


def build_outlet_graph(
    year: int, id_news: int, data: Dict[str, pd.DataFrame]
) -> Optional[nx.DiGraph]:
    """Ownership subgraph for one media in one year: SE + all ancestors + outlet."""
    oy = data["outlet_se"][
        (data["outlet_se"]["year"] == year)
        & (data["outlet_se"]["id_news"] == id_news)
    ]
    if oy.empty:
        return None
    se = oy["bvd_id_se"].iloc[0]
    G, _ = _build_full_year_graph(year, data["edges"], data["outlet_se"])
    if se not in G:
        return None
    nodes = {se} | nx.ancestors(G, se)
    if id_news in G:
        nodes = nodes | {id_news}
    return G.subgraph(nodes).copy()


# --------------------------------------------------------------------------------------
# Visualization
# --------------------------------------------------------------------------------------
def _node_type(data: dict) -> str:
    if data.get("is_outlet"):
        return "Outlet"
    if data.get("is_se"):
        return "Société éditrice"
    if data.get("parent_is_person"):
        return "Person"
    return "Company"


def build_pyvis_network(
    G: nx.DiGraph,
    title: str = "Ownership Network",
    node_color_by: str = "type",
    group_label: Optional[str] = None,
    owner_type: Optional[str] = None,
    height: str = "600px",
    show_labels: bool = True,
) -> str:
    """Build a pyvis Network and return its HTML.

    node_color_by: 'type' | 'country' | 'group' | 'owner_type'
      - 'group' colors the outlet node by its media group (`group_label`); other
        nodes keep grey.
      - 'owner_type' colors the outlet node by the owner-type typology (`owner_type`).
    Edges are colored by provenance (link_status): observed solid / propagated & estimated dashed.
    """
    net = Network(height=height, width="100%", directed=True, notebook=False)
    net.set_options("""
    var options = {
      "nodes": {"font": {"size": 14}, "borderWidth": 2},
      "edges": {
        "arrows": {"to": {"enabled": true}},
        "smooth": {"type": "continuous"}
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

    def _to_pyvis_id(value: Any):
        if isinstance(value, (str, int)):
            return value
        if isinstance(value, np.integer):
            return int(value)
        return str(value)

    node_id_map = {}
    grp_color = group_color(group_label)
    otype_color = OWNER_TYPE_COLORS.get(owner_type, "#cfd8dc")

    for node, ndata in G.nodes(data=True):
        node_id = _to_pyvis_id(node)
        node_id_map[node] = node_id
        label = ndata.get("name", str(node))
        country = get_country_from_bvd_id(node) if isinstance(node, str) else "N/A"

        if node_color_by == "country":
            color = COUNTRY_COLORS.get(country, "#95a5a6")
        elif node_color_by == "group":
            color = grp_color if ndata.get("is_outlet") else "#cfd8dc"
        elif node_color_by == "owner_type":
            color = otype_color if ndata.get("is_outlet") else "#cfd8dc"
        else:
            if ndata.get("is_outlet"):
                color = TYPE_COLORS["outlet"]
            elif ndata.get("is_se"):
                color = TYPE_COLORS["societe_editrice"]
            elif ndata.get("parent_is_person"):
                color = TYPE_COLORS["person"]
            else:
                color = TYPE_COLORS["company"]

        tooltip = f"<b>{label}</b><br>Type: {_node_type(ndata)}<br>Country: {country}"
        if isinstance(node, str):
            tooltip += f"<br>BvD ID: {node}"
        if group_label and ndata.get("is_outlet"):
            tooltip += f"<br>Groupe: {group_label}"
        if owner_type and ndata.get("is_outlet"):
            tooltip += f"<br>Type de propriétaire: {owner_type}"

        net.add_node(
            node_id,
            label=str(label) if show_labels else " ",
            color=color,
            title=tooltip,
        )

    seen = set()
    for u, v, edata in G.edges(data=True):
        w = edata.get("weight")
        pct = float(w) if w is not None and not (isinstance(w, float) and np.isnan(w)) else 0
        u_id = node_id_map.get(u, _to_pyvis_id(u))
        v_id = node_id_map.get(v, _to_pyvis_id(v))
        if (u_id, v_id) in seen:
            continue
        seen.add((u_id, v_id))
        status = str(edata.get("link_status", "estimated"))
        # Explicit width (not `value`, which triggers vis.js auto-scaling to very thick
        # strokes that swallow the dash gaps). Modest 1-6px range keeps dashes legible.
        width = max(1.0, min(6.0, pct / 20.0))
        net.add_edge(
            u_id, v_id,
            width=width,
            title=f"{pct}% ({EDGE_STATUS_LABELS.get(status, status)})",
            color=EDGE_STATUS_COLORS.get(status, "#b0b0b0"),
            dashes=EDGE_STATUS_DASHES.get(status, [2, 12]),
        )

    return net.generate_html(notebook=False)
