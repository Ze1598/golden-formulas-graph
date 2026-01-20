"""Supabase client singleton using Streamlit secrets."""

import streamlit as st
from supabase import create_client, Client


def _create_client() -> Client:
    """Create a new Supabase client instance."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


@st.cache_resource
def get_anon_client() -> Client:
    """Get the anonymous Supabase client (for public read operations).

    This client is cached and shared - use only for unauthenticated operations.
    """
    return _create_client()


def get_authenticated_client() -> Client:
    """Get a Supabase client with the current user's session.

    Creates a new client and sets the session from session state.
    Use this for any write operations that need auth.uid() to work.
    """
    client = _create_client()

    # If user has tokens stored, set the session
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token:
        try:
            client.auth.set_session(access_token, refresh_token or "")
        except Exception:
            pass

    return client


def get_supabase_client() -> Client:
    """Get appropriate Supabase client based on auth state.

    Returns authenticated client if user is logged in, otherwise anon client.
    """
    if st.session_state.get("authenticated") and st.session_state.get("access_token"):
        return get_authenticated_client()
    return get_anon_client()


def get_all_domains() -> list[dict]:
    """Fetch all domains from the database."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("domains").select("*").order("name").execute()
    return response.data


def get_all_formulas() -> list[dict]:
    """Fetch all formulas from the database."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").select("*").order("created_at", desc=True).execute()
    return response.data


def get_all_edges() -> list[dict]:
    """Fetch all formula edges from the database."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formula_edges").select("*").execute()
    return response.data


def get_domain_by_id(domain_id: str) -> dict | None:
    """Fetch a single domain by ID."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("domains").select("*").eq("id", domain_id).execute()
    return response.data[0] if response.data else None


def get_domain_by_name(name: str) -> dict | None:
    """Fetch a single domain by name (for duplicate checking)."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("domains").select("*").eq("name", name).execute()
    return response.data[0] if response.data else None


def create_domain(name: str) -> dict:
    """Create a new domain."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("domains").insert({"name": name}).execute()
    return response.data[0] if response.data else {}


def update_domain(domain_id: str, name: str) -> dict:
    """Update a domain's name."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("domains").update({"name": name}).eq("id", domain_id).execute()
    return response.data[0] if response.data else {}


def delete_domain(domain_id: str) -> bool:
    """Delete a domain by ID."""
    client = get_supabase_client()
    client.schema("golden_formula_graph").table("domains").delete().eq("id", domain_id).execute()
    return True


def is_domain_used_by_formulas(domain_id: str) -> bool:
    """Check if a domain is referenced by any formulas."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").select("id").contains("domain_ids", [domain_id]).execute()
    return len(response.data) > 0


def get_formulas_using_domain(domain_id: str) -> list[dict]:
    """Get all formulas that use a specific domain."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").select("*").contains("domain_ids", [domain_id]).execute()
    return response.data


def create_formula(principle: str, domain_ids: list[str], reference: str) -> dict:
    """Create a new formula."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").insert({
        "principle": principle,
        "domain_ids": domain_ids,
        "reference": reference
    }).execute()
    return response.data[0] if response.data else {}


def update_formula(formula_id: str, principle: str, domain_ids: list[str], reference: str) -> dict:
    """Update an existing formula."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").update({
        "principle": principle,
        "domain_ids": domain_ids,
        "reference": reference
    }).eq("id", formula_id).execute()
    return response.data[0] if response.data else {}


def delete_formula(formula_id: str) -> bool:
    """Delete a formula by ID."""
    client = get_supabase_client()
    client.schema("golden_formula_graph").table("formulas").delete().eq("id", formula_id).execute()
    return True


def get_formula_by_id(formula_id: str) -> dict | None:
    """Fetch a single formula by ID."""
    client = get_supabase_client()
    response = client.schema("golden_formula_graph").table("formulas").select("*").eq("id", formula_id).execute()
    return response.data[0] if response.data else None


def remove_domain_from_formulas(domain_id: str) -> int:
    """Remove a domain ID from all formulas that reference it.

    Returns the number of formulas updated.
    """
    formulas = get_formulas_using_domain(domain_id)
    updated_count = 0

    for formula in formulas:
        current_domain_ids = formula.get("domain_ids", [])
        new_domain_ids = [did for did in current_domain_ids if did != domain_id]

        update_formula(
            formula_id=formula["id"],
            principle=formula["principle"],
            domain_ids=new_domain_ids,
            reference=formula.get("reference", "")
        )
        updated_count += 1

    return updated_count


def delete_domain_cascade(domain_id: str) -> tuple[bool, int]:
    """Delete a domain and remove it from all formulas that reference it.

    Returns (success, number of formulas updated).
    """
    # First remove the domain from all formulas
    updated_count = remove_domain_from_formulas(domain_id)

    # Then delete the domain
    delete_domain(domain_id)

    return True, updated_count
