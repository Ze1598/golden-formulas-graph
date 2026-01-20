"""Plotly graph generation utilities for knowledge graph visualization."""

import plotly.graph_objects as go
import math


# Color palette for domains (will cycle if more domains than colors)
DOMAIN_COLORS = [
    "#FF6B6B",  # Red
    "#4ECDC4",  # Teal
    "#45B7D1",  # Sky Blue
    "#96CEB4",  # Sage Green
    "#FFEAA7",  # Yellow
    "#DDA0DD",  # Plum
    "#98D8C8",  # Mint
    "#F7DC6F",  # Gold
    "#BB8FCE",  # Purple
    "#85C1E9",  # Light Blue
    "#F8B500",  # Amber
    "#00CED1",  # Dark Cyan
    "#FF69B4",  # Hot Pink
    "#32CD32",  # Lime Green
    "#FF8C00",  # Dark Orange
]


def get_domain_color(domain_index: int) -> str:
    """Get a color for a domain based on its index."""
    return DOMAIN_COLORS[domain_index % len(DOMAIN_COLORS)]


def build_domain_lookup(domains: list[dict]) -> dict[str, dict]:
    """Build a lookup dictionary from domain ID to domain info with color."""
    lookup = {}
    for i, domain in enumerate(domains):
        lookup[domain["id"]] = {
            "name": domain["name"],
            "color": get_domain_color(i),
            "index": i
        }
    return lookup


def resolve_formula_domains(formula: dict, domain_lookup: dict[str, dict]) -> list[dict]:
    """Resolve domain IDs to domain info for a formula."""
    domain_ids = formula.get("domain_ids") or []
    resolved = []
    for domain_id in domain_ids:
        if domain_id in domain_lookup:
            resolved.append({
                "id": domain_id,
                **domain_lookup[domain_id]
            })
    return resolved


def create_network_graph(
    formulas: list[dict],
    domains: list[dict],
    edges: list[dict] | None = None,
    selected_domain_ids: list[str] | None = None
) -> go.Figure:
    """Create an interactive network graph visualization.

    Args:
        formulas: List of formula dictionaries
        domains: List of domain dictionaries
        edges: List of pre-computed edge dictionaries from formula_edges table
        selected_domain_ids: Optional list of domain IDs to filter by

    Returns:
        Plotly Figure object
    """
    domain_lookup = build_domain_lookup(domains)

    # Filter formulas if domain filter is applied
    if selected_domain_ids:
        filtered_formulas = []
        for formula in formulas:
            formula_domain_ids = formula.get("domain_ids") or []
            if any(did in selected_domain_ids for did in formula_domain_ids):
                filtered_formulas.append(formula)
        formulas = filtered_formulas

    if not formulas:
        fig = go.Figure()
        fig.add_annotation(
            text="No formulas to display",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="white"
        )
        return fig

    # Build formula ID to index mapping for edge drawing
    formula_id_to_index = {f["id"]: i for i, f in enumerate(formulas)}
    formula_ids_set = set(formula_id_to_index.keys())

    # Count edges per formula (degree) for node sizing
    edge_count = {f["id"]: 0 for f in formulas}
    if edges:
        for edge in edges:
            formula_a_id = edge.get("formula_a_id")
            formula_b_id = edge.get("formula_b_id")
            if formula_a_id in edge_count:
                edge_count[formula_a_id] += 1
            if formula_b_id in edge_count:
                edge_count[formula_b_id] += 1

    # Calculate positions using a force-directed-like layout
    # Group formulas by their primary domain for clustering
    node_positions = calculate_node_positions(formulas, domain_lookup)

    # Prepare edge traces
    edge_traces = []
    if edges:
        for edge in edges:
            formula_a_id = edge.get("formula_a_id")
            formula_b_id = edge.get("formula_b_id")

            # Only draw edge if both formulas are in the current view
            if formula_a_id in formula_ids_set and formula_b_id in formula_ids_set:
                idx_a = formula_id_to_index[formula_a_id]
                idx_b = formula_id_to_index[formula_b_id]

                pos_a = node_positions[idx_a]
                pos_b = node_positions[idx_b]

                edge_weight = edge.get("edge_weight", 1)
                shared_domain_ids = edge.get("shared_domain_ids") or []

                # Use first shared domain color for edge, or gray
                if shared_domain_ids and shared_domain_ids[0] in domain_lookup:
                    edge_color = domain_lookup[shared_domain_ids[0]]["color"]
                else:
                    edge_color = "#CCCCCC"

                # Scale line width based on edge weight (number of shared domains)
                line_width = max(1, min(edge_weight * 1.5, 6))

                edge_trace = go.Scatter(
                    x=[pos_a[0], pos_b[0], None],
                    y=[pos_a[1], pos_b[1], None],
                    mode="lines",
                    line=dict(width=line_width, color=edge_color),
                    hoverinfo="none",
                    showlegend=False,
                    opacity=0.4
                )
                edge_traces.append(edge_trace)

    # Prepare node data
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    hover_texts = []

    # Calculate min/max for size scaling
    max_edges = max(edge_count.values()) if edge_count else 1
    min_size = 12
    max_size = 40

    for i, formula in enumerate(formulas):
        pos = node_positions[i]
        node_x.append(pos[0])
        node_y.append(pos[1])

        # Get formula's domains
        formula_domains = resolve_formula_domains(formula, domain_lookup)

        # Use primary domain color (first domain) or gray if no domains
        if formula_domains:
            node_colors.append(formula_domains[0]["color"])
        else:
            node_colors.append("#CCCCCC")

        # Calculate node size based on edge count
        num_edges = edge_count.get(formula["id"], 0)
        if max_edges > 0:
            size = min_size + (num_edges / max_edges) * (max_size - min_size)
        else:
            size = min_size
        node_sizes.append(size)

        # Build hover text
        principle = formula.get("principle", "")
        domain_names = [d["name"] for d in formula_domains]
        hover_text = (
            f"<b>Principle:</b><br>{principle}<br><br>"
            f"<b>Domains:</b> {', '.join(domain_names) if domain_names else 'None'}<br><br>"
            f"<b>Reference:</b> {formula.get('reference', 'N/A')}<br><br>"
            f"<b>Connections:</b> {num_edges}"
        )
        hover_texts.append(hover_text)

    # Create node trace
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        hovertext=hover_texts,
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color="white"),
            opacity=0.9
        ),
        showlegend=False
    )

    # Create figure with edges first (so nodes appear on top)
    fig = go.Figure(data=edge_traces + [node_trace])

    # Add legend for domains
    for domain in domains:
        if domain["id"] in domain_lookup:
            info = domain_lookup[domain["id"]]
            # Check if this domain has any formulas (for visibility)
            has_formulas = any(
                domain["id"] in (f.get("domain_ids") or [])
                for f in formulas
            )
            if has_formulas or not selected_domain_ids:
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(size=10, color=info["color"]),
                    name=domain["name"],
                    showlegend=True
                ))

    fig.update_layout(
        title=dict(
            text="Golden Formulas Graph",
            font=dict(size=20)
        ),
        showlegend=True,
        legend=dict(
            title="Domains",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02
        ),
        hovermode="closest",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title=""
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title=""
        ),
        plot_bgcolor="white",
        margin=dict(l=20, r=150, t=50, b=20),
        height=600
    )

    return fig


def calculate_node_positions(
    formulas: list[dict],
    domain_lookup: dict[str, dict]
) -> list[tuple[float, float]]:
    """Calculate node positions using a domain-clustered layout.

    Formulas are grouped by their primary domain and arranged in clusters.
    """
    if not formulas:
        return []

    # Group formulas by primary domain
    domain_groups: dict[str, list[int]] = {}
    no_domain_formulas: list[int] = []

    for i, formula in enumerate(formulas):
        domain_ids = formula.get("domain_ids") or []
        if domain_ids:
            primary_domain = domain_ids[0]
            if primary_domain not in domain_groups:
                domain_groups[primary_domain] = []
            domain_groups[primary_domain].append(i)
        else:
            no_domain_formulas.append(i)

    # Calculate positions
    positions = [None] * len(formulas)
    num_groups = len(domain_groups) + (1 if no_domain_formulas else 0)

    if num_groups == 0:
        return [(0, 0) for _ in formulas]

    # Arrange groups in a circle
    group_radius = 3.0 if num_groups > 1 else 0
    group_angle_step = 2 * math.pi / max(num_groups, 1)

    group_index = 0
    for domain_id, formula_indices in domain_groups.items():
        # Calculate group center
        group_angle = group_index * group_angle_step
        group_cx = group_radius * math.cos(group_angle)
        group_cy = group_radius * math.sin(group_angle)

        # Arrange formulas within group
        arrange_group(positions, formula_indices, group_cx, group_cy)
        group_index += 1

    # Handle formulas without domains
    if no_domain_formulas:
        group_angle = group_index * group_angle_step
        group_cx = group_radius * math.cos(group_angle)
        group_cy = group_radius * math.sin(group_angle)
        arrange_group(positions, no_domain_formulas, group_cx, group_cy)

    return positions


def arrange_group(
    positions: list,
    indices: list[int],
    center_x: float,
    center_y: float
):
    """Arrange a group of nodes around a center point."""
    n = len(indices)
    if n == 1:
        positions[indices[0]] = (center_x, center_y)
        return

    # Arrange in concentric circles if many nodes
    inner_radius = 0.8
    nodes_per_ring = 8

    for i, idx in enumerate(indices):
        ring = i // nodes_per_ring
        pos_in_ring = i % nodes_per_ring
        nodes_in_this_ring = min(nodes_per_ring, n - ring * nodes_per_ring)

        radius = inner_radius * (ring + 1)
        angle = 2 * math.pi * pos_in_ring / nodes_in_this_ring

        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        positions[idx] = (x, y)
