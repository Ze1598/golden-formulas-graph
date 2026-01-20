"""Golden Formulas Graph - Main App."""

import streamlit as st
from utils.supabase_client import get_all_domains, get_all_formulas, get_all_edges
from utils.graph import create_network_graph, build_domain_lookup, resolve_formula_domains

st.set_page_config(
    page_title="Golden Formulas Graph",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide the sidebar navigation and collapse button
st.markdown(
    """
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Golden Formulas Graph")
st.markdown("Visualize principles across domains of knowledge in graph format.")


@st.cache_data(ttl=300)
def load_data():
    """Load all domains, formulas, and edges from the database."""
    domains = get_all_domains()
    formulas = get_all_formulas()
    edges = get_all_edges()
    return domains, formulas, edges


# Load data
try:
    with st.spinner("Loading data..."):
        domains, formulas, edges = load_data()
except Exception as e:
    st.error(f"Failed to load data: {str(e)}")
    st.stop()

if not domains and not formulas:
    st.info("No data available yet.")
    st.stop()

# Filter controls in main content area
st.markdown("---")

col_domain_filter, col_search = st.columns([1, 1])

with col_domain_filter:
    domain_options = {d["id"]: d["name"] for d in domains}
    selected_domain_names = st.multiselect(
        "Filter by Domain",
        options=list(domain_options.values()),
        default=[],
        help="Select domains to filter formulas. Leave empty to show all."
    )

with col_search:
    search_query = st.text_input(
        "Search Principles",
        placeholder="Type to search...",
        help="Search formulas by principle text (case-insensitive)"
    )

# Convert selected names back to IDs
selected_domain_ids = [
    did for did, name in domain_options.items()
    if name in selected_domain_names
] if selected_domain_names else None

# Normalize search query
search_query_lower = search_query.strip().lower() if search_query else None

# Apply filters to formulas
def filter_formulas(formulas_list, domain_ids, search_text):
    """Filter formulas by domain and search text."""
    result = formulas_list

    if domain_ids:
        result = [
            f for f in result
            if any(did in domain_ids for did in (f.get("domain_ids") or []))
        ]

    if search_text:
        result = [
            f for f in result
            if search_text in f.get("principle", "").lower()
        ]

    return result


filtered_formulas = filter_formulas(formulas, selected_domain_ids, search_query_lower)

# Create and display graph
st.markdown("---")

if filtered_formulas:
    fig = create_network_graph(filtered_formulas, domains, edges, selected_domain_ids)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No formulas match the current filters.")

# Formula list view
st.markdown("---")
st.subheader("Formula List")

# Build domain lookup for display
domain_lookup = build_domain_lookup(domains)

# Use already filtered formulas
display_formulas = filtered_formulas

if display_formulas:
    for formula in display_formulas:
        formula_domains = resolve_formula_domains(formula, domain_lookup)

        with st.expander(f"{formula['principle'][:80]}..." if len(formula['principle']) > 80 else formula['principle']):
            st.markdown(f"**Principle:** {formula['principle']}")
            st.markdown(f"**Reference:** {formula.get('reference', 'N/A')}")

            if formula_domains:
                domain_chips = " | ".join([f"**{d['name']}**" for d in formula_domains])
                st.markdown(f"**Domains:** {domain_chips}")
            else:
                st.markdown("**Domains:** None assigned")
else:
    st.info("No formulas match the current filter.")
