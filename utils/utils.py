"""Plotly graph generation utilities for knowledge graph visualization."""

def build_domain_lookup(domains: list[dict]) -> dict[str, dict]:
    """Build a lookup dictionary from domain ID to domain info with color."""
    lookup = {}
    for i, domain in enumerate(domains):
        lookup[domain["id"]] = {
            "name": domain["name"],
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