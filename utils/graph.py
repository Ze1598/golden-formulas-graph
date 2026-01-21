"""Plotly graph generation utilities for knowledge graph visualization."""

import plotly.graph_objects as go
import math
import textwrap


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


def wrap_text(text: str, width: int = 60) -> str:
    """Wrap text to specified width using HTML line breaks."""
    if not text:
        return ""
    lines = textwrap.wrap(text, width=width)
    return "<br>".join(lines)


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
    selected_domain_ids: list[str] | None = None,
    cross_domain_only: bool = False,
    min_connections: int = 0
) -> go.Figure:
    """Create an interactive network graph visualization.

    Args:
        formulas: List of formula dictionaries
        domains: List of domain dictionaries
        edges: List of pre-computed edge dictionaries from formula_edges table
        selected_domain_ids: Optional list of domain IDs to filter by
        cross_domain_only: If True, only show edges between nodes with different primary domains
        min_connections: Minimum number of connections required to display a node

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

    # Build lookup for primary domain per formula and count domains
    formula_primary_domain = {}
    formula_domain_count = {}
    for f in formulas:
        domain_ids = f.get("domain_ids") or []
        formula_primary_domain[f["id"]] = domain_ids[0] if domain_ids else None
        formula_domain_count[f["id"]] = len(domain_ids)

    # Filter formulas by minimum domain count (connections = domains the node belongs to)
    if min_connections > 0:
        formulas = [f for f in formulas if formula_domain_count.get(f["id"], 0) >= min_connections]

    if not formulas:
        fig = go.Figure()
        fig.add_annotation(
            text="No formulas meet the minimum connections threshold",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="white"
        )
        return fig

    # Rebuild formula ID set after filtering
    formula_id_to_index = {f["id"]: i for i, f in enumerate(formulas)}
    formula_ids_set = set(formula_id_to_index.keys())

    # Filter edges: must connect two formulas in the current view
    def should_include_edge(edge):
        formula_a_id = edge.get("formula_a_id")
        formula_b_id = edge.get("formula_b_id")
        if formula_a_id not in formula_ids_set or formula_b_id not in formula_ids_set:
            return False
        if cross_domain_only:
            primary_a = formula_primary_domain.get(formula_a_id)
            primary_b = formula_primary_domain.get(formula_b_id)
            if primary_a == primary_b:
                return False
        return True

    filtered_edges = [e for e in (edges or []) if should_include_edge(e)]

    # Calculate positions using a force-directed-like layout
    # Group formulas by their primary domain for clustering
    node_positions = calculate_node_positions(formulas, domain_lookup)

    # Prepare edge traces
    edge_traces = []
    for edge in filtered_edges:
        formula_a_id = edge.get("formula_a_id")
        formula_b_id = edge.get("formula_b_id")

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

    # Calculate min/max domain count for size scaling
    domain_counts = [formula_domain_count.get(f["id"], 0) for f in formulas]
    max_domains = max(domain_counts) if domain_counts else 1
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

        # Calculate node size based on domain count
        num_domains = formula_domain_count.get(formula["id"], 0)
        if max_domains > 0:
            size = min_size + (num_domains / max_domains) * (max_size - min_size)
        else:
            size = min_size
        node_sizes.append(size)

        # Build hover text with wrapped principle
        principle = formula.get("principle", "")
        wrapped_principle = wrap_text(principle, width=60)
        domain_names = [d["name"] for d in formula_domains]
        reference = formula.get('reference', 'N/A')
        wrapped_reference = wrap_text(reference, width=60) if reference else 'N/A'
        hover_text = (
            f"<b>Principle:</b><br>{wrapped_principle}<br><br>"
            f"<b>Domains:</b> {', '.join(domain_names) if domain_names else 'None'}<br><br>"
            f"<b>Reference:</b> {wrapped_reference}<br><br>"
            f"<b>Domain count:</b> {num_domains}"
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


def create_replicated_network_graph(
    replicated_nodes: list[dict],
    domains: list[dict],
    selected_domain_ids: list[str] | None = None,
    min_domains: int = 0
) -> go.Figure:
    """Create network graph from replicated nodes view.

    Each row in replicated_nodes is an edge between domain replicas of the same principle.
    Schema: id (principle), principle, from_domain, to_domain, reference

    Args:
        replicated_nodes: List of edge rows from replicated_nodes view
        domains: List of domain dictionaries
        selected_domain_ids: Optional list of domain IDs to filter by
        min_domains: Minimum number of domains a principle must have

    Returns:
        Plotly Figure object
    """
    domain_lookup = build_domain_lookup(domains)

    # Filter by selected domains if specified
    if selected_domain_ids:
        replicated_nodes = [
            row for row in replicated_nodes
            if row.get("from_domain") in selected_domain_ids
            or row.get("to_domain") in selected_domain_ids
        ]

    if not replicated_nodes:
        fig = go.Figure()
        fig.add_annotation(
            text="No data to display",
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

    # Build unique nodes: each (principle_id, domain_id) pair is a node
    # Also count domains per principle for filtering
    principle_domains: dict[str, set[str]] = {}
    principle_info: dict[str, dict] = {}

    for row in replicated_nodes:
        principle_id = row.get("id")
        from_domain = row.get("from_domain")
        to_domain = row.get("to_domain")

        if principle_id not in principle_domains:
            principle_domains[principle_id] = set()
            principle_info[principle_id] = {
                "principle": row.get("principle", ""),
                "reference": row.get("reference", "")
            }

        principle_domains[principle_id].add(from_domain)
        principle_domains[principle_id].add(to_domain)

    # Filter principles by minimum domain count
    if min_domains > 0:
        principle_domains = {
            pid: doms for pid, doms in principle_domains.items()
            if len(doms) >= min_domains
        }

    if not principle_domains:
        fig = go.Figure()
        fig.add_annotation(
            text="No principles meet the minimum domains threshold",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="white"
        )
        return fig

    # Build node list: (principle_id, domain_id) pairs
    nodes = []
    node_index = {}  # (principle_id, domain_id) -> index

    for principle_id, domain_ids in principle_domains.items():
        for domain_id in domain_ids:
            if domain_id in domain_lookup:  # Only include known domains
                key = (principle_id, domain_id)
                node_index[key] = len(nodes)
                nodes.append({
                    "principle_id": principle_id,
                    "domain_id": domain_id,
                    "principle": principle_info[principle_id]["principle"],
                    "reference": principle_info[principle_id]["reference"],
                    "domain_count": len(domain_ids)
                })

    # Calculate positions grouped by domain
    node_positions = calculate_replicated_node_positions(nodes, domain_lookup)

    # Build edges from the view data
    edge_traces = []
    for row in replicated_nodes:
        principle_id = row.get("id")
        from_domain = row.get("from_domain")
        to_domain = row.get("to_domain")

        # Skip if principle was filtered out
        if principle_id not in principle_domains:
            continue

        from_key = (principle_id, from_domain)
        to_key = (principle_id, to_domain)

        if from_key in node_index and to_key in node_index:
            idx_from = node_index[from_key]
            idx_to = node_index[to_key]

            pos_from = node_positions[idx_from]
            pos_to = node_positions[idx_to]

            edge_trace = go.Scatter(
                x=[pos_from[0], pos_to[0], None],
                y=[pos_from[1], pos_to[1], None],
                mode="lines",
                line=dict(width=1.5, color="#AAAAAA"),
                hoverinfo="none",
                showlegend=False,
                opacity=0.3
            )
            edge_traces.append(edge_trace)

    # Prepare node data
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    hover_texts = []

    max_domains = max(n["domain_count"] for n in nodes) if nodes else 1
    min_size = 12
    max_size = 40

    for i, node in enumerate(nodes):
        pos = node_positions[i]
        node_x.append(pos[0])
        node_y.append(pos[1])

        domain_id = node["domain_id"]
        if domain_id in domain_lookup:
            node_colors.append(domain_lookup[domain_id]["color"])
        else:
            node_colors.append("#CCCCCC")

        # Size based on domain count
        domain_count = node["domain_count"]
        if max_domains > 0:
            size = min_size + (domain_count / max_domains) * (max_size - min_size)
        else:
            size = min_size
        node_sizes.append(size)

        # Hover text
        principle = node["principle"]
        wrapped_principle = wrap_text(principle, width=60)
        reference = node["reference"] or "N/A"
        wrapped_reference = wrap_text(reference, width=60)
        domain_name = domain_lookup.get(domain_id, {}).get("name", "Unknown")

        hover_text = (
            f"<b>Principle:</b><br>{wrapped_principle}<br><br>"
            f"<b>Domain:</b> {domain_name}<br><br>"
            f"<b>Reference:</b> {wrapped_reference}<br><br>"
            f"<b>Total domains:</b> {domain_count}"
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

    # Create figure
    fig = go.Figure(data=edge_traces + [node_trace])

    # Add legend for domains
    domains_in_graph = set(n["domain_id"] for n in nodes)
    for domain in domains:
        if domain["id"] in domains_in_graph and domain["id"] in domain_lookup:
            info = domain_lookup[domain["id"]]
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


def calculate_replicated_node_positions(
    nodes: list[dict],
    domain_lookup: dict[str, dict]
) -> list[tuple[float, float]]:
    """Calculate positions for replicated nodes, grouped by domain."""
    if not nodes:
        return []

    # Group nodes by domain
    domain_groups: dict[str, list[int]] = {}

    for i, node in enumerate(nodes):
        domain_id = node["domain_id"]
        if domain_id not in domain_groups:
            domain_groups[domain_id] = []
        domain_groups[domain_id].append(i)

    # Calculate positions
    positions = [None] * len(nodes)
    num_groups = len(domain_groups)

    if num_groups == 0:
        return [(0, 0) for _ in nodes]

    # Arrange groups in a circle
    group_radius = 3.0 if num_groups > 1 else 0
    group_angle_step = 2 * math.pi / max(num_groups, 1)

    for group_index, (domain_id, node_indices) in enumerate(domain_groups.items()):
        group_angle = group_index * group_angle_step
        group_cx = group_radius * math.cos(group_angle)
        group_cy = group_radius * math.sin(group_angle)

        arrange_group(positions, node_indices, group_cx, group_cy)

    return positions


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
