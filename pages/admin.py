"""Admin CRUD Page - Auth Protected."""

import streamlit as st
from utils.auth import (
    init_auth_state,
    is_authenticated,
    render_login_form,
    logout
)
from utils.supabase_client import (
    get_all_domains,
    get_all_formulas,
    get_domain_by_name,
    create_domain,
    update_domain,
    delete_domain,
    delete_domain_cascade,
    is_domain_used_by_formulas,
    get_formulas_using_domain,
    create_formula,
    update_formula,
    delete_formula,
    get_formula_by_id
)
from utils.graph import build_domain_lookup, resolve_formula_domains

st.set_page_config(
    page_title="Admin | Golden Formulas",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide the sidebar navigation
st.markdown(
    """
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize auth state
init_auth_state()


def clear_form_state():
    """Clear form-related session state."""
    keys_to_clear = [
        "edit_domain_id", "edit_formula_id",
        "show_add_domain", "show_add_formula",
        "new_domain_in_formula"
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def refresh_data():
    """Clear cached data and refresh."""
    if "domains_cache" in st.session_state:
        del st.session_state["domains_cache"]
    if "formulas_cache" in st.session_state:
        del st.session_state["formulas_cache"]


def get_cached_domains():
    """Get domains with session-level caching."""
    if "domains_cache" not in st.session_state:
        st.session_state["domains_cache"] = get_all_domains()
    return st.session_state["domains_cache"]


def get_cached_formulas():
    """Get formulas with session-level caching."""
    if "formulas_cache" not in st.session_state:
        st.session_state["formulas_cache"] = get_all_formulas()
    return st.session_state["formulas_cache"]


# Main content
col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title("Admin Panel")

# Check authentication
if not is_authenticated():
    st.markdown("Please log in to access the admin panel.")
    st.markdown("---")
    render_login_form()
    st.stop()

# User is authenticated - show logout button in header
with col_logout:
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"Logged in as: {st.session_state.user_email}")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

st.markdown("---")

# Tabs for Domains and Formulas management
tab_domains, tab_formulas = st.tabs(["Domains", "Formulas"])

# ============ DOMAINS TAB ============
with tab_domains:
    st.subheader("Manage Domains")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("+ Add Domain", use_container_width=True, key="add_domain_btn"):
            st.session_state["show_add_domain"] = True
            st.session_state.pop("edit_domain_id", None)

    # Add Domain Form
    if st.session_state.get("show_add_domain"):
        st.markdown("#### Add New Domain")
        with st.form("add_domain_form"):
            new_domain_name = st.text_input("Domain Name", placeholder="Enter domain name")
            col_save, col_cancel = st.columns(2)

            with col_save:
                save_clicked = st.form_submit_button("Save", use_container_width=True)
            with col_cancel:
                cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

            if save_clicked:
                if not new_domain_name.strip():
                    st.error("Domain name cannot be empty.")
                else:
                    # Check for duplicate
                    existing = get_domain_by_name(new_domain_name.strip())
                    if existing:
                        st.error(f"Domain '{new_domain_name}' already exists.")
                    else:
                        try:
                            with st.spinner("Creating domain..."):
                                create_domain(new_domain_name.strip())
                            st.success(f"Domain '{new_domain_name}' created successfully!")
                            refresh_data()
                            st.session_state["show_add_domain"] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create domain: {str(e)}")

            if cancel_clicked:
                st.session_state["show_add_domain"] = False
                st.rerun()

        st.markdown("---")

    # Edit Domain Form
    if st.session_state.get("edit_domain_id"):
        domain_id = st.session_state["edit_domain_id"]
        domains = get_cached_domains()
        domain = next((d for d in domains if d["id"] == domain_id), None)

        if domain:
            st.markdown("#### Edit Domain")
            with st.form("edit_domain_form"):
                edited_name = st.text_input("Domain Name", value=domain["name"])
                col_save, col_cancel = st.columns(2)

                with col_save:
                    save_clicked = st.form_submit_button("Save Changes", use_container_width=True)
                with col_cancel:
                    cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

                if save_clicked:
                    if not edited_name.strip():
                        st.error("Domain name cannot be empty.")
                    elif edited_name.strip() != domain["name"]:
                        # Check for duplicate
                        existing = get_domain_by_name(edited_name.strip())
                        if existing and existing["id"] != domain_id:
                            st.error(f"Domain '{edited_name}' already exists.")
                        else:
                            try:
                                with st.spinner("Updating domain..."):
                                    update_domain(domain_id, edited_name.strip())
                                st.success(f"Domain updated successfully!")
                                refresh_data()
                                del st.session_state["edit_domain_id"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update domain: {str(e)}")
                    else:
                        del st.session_state["edit_domain_id"]
                        st.rerun()

                if cancel_clicked:
                    del st.session_state["edit_domain_id"]
                    st.rerun()

            st.markdown("---")

    # Confirm Delete Domain Dialog
    if st.session_state.get("confirm_delete_domain_id"):
        domain_id = st.session_state["confirm_delete_domain_id"]
        domain_name = st.session_state.get("confirm_delete_domain_name", "this domain")
        formulas_using = get_formulas_using_domain(domain_id)

        st.warning(f"**'{domain_name}'** is used by {len(formulas_using)} formula(s).")

        with st.expander("Show affected formulas", expanded=True):
            for f in formulas_using:
                principle_preview = f["principle"][:60] + "..." if len(f["principle"]) > 60 else f["principle"]
                st.markdown(f"- {principle_preview}")

        st.markdown("**Choose an action:**")
        col_cascade, col_cancel = st.columns(2)

        with col_cascade:
            if st.button(
                f"Remove from formulas & delete",
                key="confirm_cascade_delete",
                use_container_width=True,
                type="primary"
            ):
                try:
                    with st.spinner("Removing domain from formulas and deleting..."):
                        success, updated_count = delete_domain_cascade(domain_id)
                    st.success(
                        f"Domain '{domain_name}' deleted. "
                        f"Removed from {updated_count} formula(s)."
                    )
                    st.session_state.pop("confirm_delete_domain_id", None)
                    st.session_state.pop("confirm_delete_domain_name", None)
                    refresh_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete domain: {str(e)}")

        with col_cancel:
            if st.button("Cancel", key="cancel_cascade_delete", use_container_width=True):
                st.session_state.pop("confirm_delete_domain_id", None)
                st.session_state.pop("confirm_delete_domain_name", None)
                st.rerun()

        st.markdown("---")

    # List all domains
    st.markdown("#### All Domains")

    try:
        domains = get_cached_domains()

        if not domains:
            st.info("No domains found. Create your first domain above.")
        else:
            for domain in domains:
                col_name, col_edit, col_delete = st.columns([4, 1, 1])

                with col_name:
                    st.markdown(f"**{domain['name']}**")

                with col_edit:
                    if st.button("Edit", key=f"edit_domain_{domain['id']}", use_container_width=True):
                        st.session_state["edit_domain_id"] = domain["id"]
                        st.session_state.pop("show_add_domain", None)
                        st.rerun()

                with col_delete:
                    if st.button("Delete", key=f"delete_domain_{domain['id']}", use_container_width=True):
                        # Check if domain is used by formulas
                        if is_domain_used_by_formulas(domain["id"]):
                            st.session_state["confirm_delete_domain_id"] = domain["id"]
                            st.session_state["confirm_delete_domain_name"] = domain["name"]
                            st.rerun()
                        else:
                            try:
                                with st.spinner("Deleting domain..."):
                                    delete_domain(domain["id"])
                                st.success(f"Domain '{domain['name']}' deleted.")
                                refresh_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to delete domain: {str(e)}")

    except Exception as e:
        st.error(f"Failed to load domains: {str(e)}")

# ============ FORMULAS TAB ============
with tab_formulas:
    st.subheader("Manage Formulas")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("+ Add Formula", use_container_width=True, key="add_formula_btn"):
            st.session_state["show_add_formula"] = True
            st.session_state.pop("edit_formula_id", None)

    # Get domains for selects
    try:
        domains = get_cached_domains()
        domain_options = {d["name"]: d["id"] for d in domains}
        domain_names = list(domain_options.keys())
    except Exception as e:
        st.error(f"Failed to load domains: {str(e)}")
        domains = []
        domain_options = {}
        domain_names = []

    # Add Formula Form
    if st.session_state.get("show_add_formula"):
        st.markdown("#### Add New Formula")

        with st.form("add_formula_form"):
            principle = st.text_area(
                "Principle",
                placeholder="Enter the formula/principle text",
                height=100
            )

            # Domain selection with option to add new
            selected_domains = st.multiselect(
                "Domains",
                options=domain_names,
                help="Select one or more domains for this formula"
            )

            # Add new domain inline
            new_domain_name = st.text_input(
                "Or add a new domain",
                placeholder="Enter new domain name (optional)"
            )

            reference = st.text_input(
                "Reference",
                placeholder="Source/reference for this formula"
            )

            col_save, col_cancel = st.columns(2)

            with col_save:
                save_clicked = st.form_submit_button("Save Formula", use_container_width=True)
            with col_cancel:
                cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

            if save_clicked:
                if not principle.strip():
                    st.error("Principle cannot be empty.")
                else:
                    try:
                        # Collect domain IDs
                        selected_domain_ids = [domain_options[name] for name in selected_domains]

                        # Create new domain if specified
                        if new_domain_name.strip():
                            existing = get_domain_by_name(new_domain_name.strip())
                            if existing:
                                selected_domain_ids.append(existing["id"])
                            else:
                                new_domain = create_domain(new_domain_name.strip())
                                if new_domain:
                                    selected_domain_ids.append(new_domain["id"])

                        with st.spinner("Creating formula..."):
                            create_formula(
                                principle=principle.strip(),
                                domain_ids=selected_domain_ids,
                                reference=reference.strip()
                            )

                        st.success("Formula created successfully!")
                        refresh_data()
                        st.session_state["show_add_formula"] = False
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to create formula: {str(e)}")

            if cancel_clicked:
                st.session_state["show_add_formula"] = False
                st.rerun()

        st.markdown("---")

    # Edit Formula Form
    if st.session_state.get("edit_formula_id"):
        formula_id = st.session_state["edit_formula_id"]
        formula = get_formula_by_id(formula_id)

        if formula:
            st.markdown("#### Edit Formula")

            # Get current domain names
            domain_lookup = build_domain_lookup(domains)
            current_domains = resolve_formula_domains(formula, domain_lookup)
            current_domain_names = [d["name"] for d in current_domains]

            with st.form("edit_formula_form"):
                edited_principle = st.text_area(
                    "Principle",
                    value=formula.get("principle", ""),
                    height=100
                )

                edited_domains = st.multiselect(
                    "Domains",
                    options=domain_names,
                    default=[name for name in current_domain_names if name in domain_names]
                )

                # Add new domain inline
                new_domain_name = st.text_input(
                    "Or add a new domain",
                    placeholder="Enter new domain name (optional)"
                )

                edited_reference = st.text_input(
                    "Reference",
                    value=formula.get("reference", "")
                )

                col_save, col_cancel = st.columns(2)

                with col_save:
                    save_clicked = st.form_submit_button("Save Changes", use_container_width=True)
                with col_cancel:
                    cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

                if save_clicked:
                    if not edited_principle.strip():
                        st.error("Principle cannot be empty.")
                    else:
                        try:
                            # Collect domain IDs
                            edited_domain_ids = [domain_options[name] for name in edited_domains]

                            # Create new domain if specified
                            if new_domain_name.strip():
                                existing = get_domain_by_name(new_domain_name.strip())
                                if existing:
                                    edited_domain_ids.append(existing["id"])
                                else:
                                    new_domain = create_domain(new_domain_name.strip())
                                    if new_domain:
                                        edited_domain_ids.append(new_domain["id"])

                            with st.spinner("Updating formula..."):
                                update_formula(
                                    formula_id=formula_id,
                                    principle=edited_principle.strip(),
                                    domain_ids=edited_domain_ids,
                                    reference=edited_reference.strip()
                                )

                            st.success("Formula updated successfully!")
                            refresh_data()
                            del st.session_state["edit_formula_id"]
                            st.rerun()

                        except Exception as e:
                            st.error(f"Failed to update formula: {str(e)}")

                if cancel_clicked:
                    del st.session_state["edit_formula_id"]
                    st.rerun()

            st.markdown("---")

    # List all formulas
    st.markdown("#### All Formulas")

    try:
        formulas = get_cached_formulas()
        domain_lookup = build_domain_lookup(domains)

        if not formulas:
            st.info("No formulas found. Create your first formula above.")
        else:
            for formula in formulas:
                formula_domains = resolve_formula_domains(formula, domain_lookup)
                domain_tags = ", ".join([d["name"] for d in formula_domains]) if formula_domains else "No domains"

                principle_preview = formula["principle"][:80] + "..." if len(formula["principle"]) > 80 else formula["principle"]

                with st.expander(f"{principle_preview}"):
                    st.markdown(f"**Principle:** {formula['principle']}")
                    st.markdown(f"**Reference:** {formula.get('reference', 'N/A')}")
                    st.markdown(f"**Domains:** {domain_tags}")

                    col_edit, col_delete, col_spacer = st.columns([1, 1, 4])

                    with col_edit:
                        if st.button("Edit", key=f"edit_formula_{formula['id']}", use_container_width=True):
                            st.session_state["edit_formula_id"] = formula["id"]
                            st.session_state.pop("show_add_formula", None)
                            st.rerun()

                    with col_delete:
                        if st.button("Delete", key=f"delete_formula_{formula['id']}", use_container_width=True):
                            try:
                                with st.spinner("Deleting formula..."):
                                    delete_formula(formula["id"])
                                st.success("Formula deleted.")
                                refresh_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to delete formula: {str(e)}")

    except Exception as e:
        st.error(f"Failed to load formulas: {str(e)}")
