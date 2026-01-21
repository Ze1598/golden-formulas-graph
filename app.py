"""Golden Formulas Graph - Main App."""

import streamlit as st
from utils.supabase_client import get_all_domains, get_all_formulas, get_replicated_nodes
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd

st.set_page_config(
    page_title="Golden Formulas Graph",
    page_icon="🧩",
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
    """Load all domains, formulas, and replicated nodes from the database."""
    domains = get_all_domains()
    formulas = get_all_formulas()
    replicated_nodes = get_replicated_nodes()
    return domains, formulas, replicated_nodes


# Load data
try:
    with st.spinner("Loading data..."):
        domains, formulas, replicated_nodes = load_data()
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
        help="Select domains to filter. Leave empty to show all."
    )

with col_search:
    # Minimum domain count filter
    min_domains = st.number_input(
        "Minimum Domains per Formula",
        min_value=0,
        max_value=20,
        value=2,
        step=1,
        help="Only show principles that belong to at least this many domains"
    )

# Create and display graph
st.markdown("---")


# Create a principles DF to facilitate filters
domains_df = pd.DataFrame(domains)
# First keep all records because they represent the edges
replicated_nodes_df = pd.DataFrame(replicated_nodes)
# Bring domains to have their names
replicated_nodes_df = replicated_nodes_df.merge(domains_df, how="inner", left_on="from_domain", right_on="id")
# Now keep just 1 of each principle to generate nodes
principles_df = replicated_nodes_df.drop_duplicates(subset=["principle"])

# Apply user filters
principles_df = principles_df.query(f"domain_count >= {min_domains}")
# Filter dataset by domain if user selected any
if selected_domain_names != list():
    principles_df = principles_df.query(f"name in {selected_domain_names}")
    domains = [domain for domain in domains if domain["name"] in selected_domain_names]

# Proceed to draw the visual if there is data after filters
if not principles_df.empty:
    # Generate nodes for principles
    nodes = [
        Node(
            id=node["principle"], 
            label="", 
            size=25, 
            shape="circle",
        ) for index,node in principles_df.iterrows()
    ]
    # And domains
    nodes.extend([
        Node(
            id=node["name"], 
            label=node["name"], 
            # id=domain['id'], 
            # label=domain["name"], 
            shape="box",
            color="orange"
        ) for index,node in principles_df.drop_duplicates(subset="name").iterrows()
    ])

    # And create principle->domain edges
    edges = [
        Edge(
            source=edge["principle"], 
            label=None, 
            target=edge['name']
        ) for index,edge in replicated_nodes_df.iterrows()
    ]

    config = Config(
        width=2000,
        height=1000,
        directed=True, 
        physics=True, 
        hierarchical=False,
        navigationButtons=True
    )
    
    selected_principle = agraph(nodes=nodes, edges=edges, config=config)

else:
    st.info("No data matches the current filters.")

# Formula list view
st.markdown("---")
st.subheader("Formula List")


if not principles_df.empty:
    # Only filter when user as selected a node
    if selected_principle != None:
        principles_df = principles_df[principles_df["principle"] == selected_principle]
    
    # Add domain string agg
    # Calculated from the edges DF
    domains_list_df = replicated_nodes_df[["principle", "name"]]
    domains_list_df["domains_list"] = domains_list_df.groupby(["principle"])["name"].transform(lambda x: " | ".join(x))
    domains_list_df.drop_duplicates(subset="principle", inplace=True)
    # Then joined back to the nodes DF
    principles_df = principles_df.merge(domains_list_df, how="inner", left_on="principle", right_on="principle", suffixes=(None, "_listy"))

    # Now loop through formulas to write each
    for index, formula in principles_df.iterrows():

        with st.expander(f"{formula['principle'][:80]}..." if len(formula['principle']) > 80 else formula['principle']):
            st.markdown(f"**Formula:** {formula['principle']}")
            st.markdown(f"**Reference:** {formula.get('reference', 'N/A')}")
            st.markdown(f"**Domains:** {formula['domains_list']}")

else:
    st.info("No formulas match the current filter.")
