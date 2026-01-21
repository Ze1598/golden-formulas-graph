"""Seed script to insert formula data from a JSON file into the database."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Load environment variables from .env.local
print(Path(__file__).parent.parent / ".streamlit/secrets.toml")
load_dotenv(Path(__file__).parent.parent / ".streamlit/secrets.toml")

# --- Configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use SERVICE ROLE key for seeding

# Path to the JSON file containing formula records
DATA_FILE = Path(__file__).parent / "formulas_data.json"


def create_supabase_client():
    """Create Supabase client with service role key."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_formulas_from_json(file_path: Path) -> list[dict]:
    """
    Load formula records from JSON file.

    Expected JSON format:
    [
        {
            "domains": ["Mathematics", "Physics"],
            "principle": "The whole is greater than the sum of its parts",
            "reference": "Aristotle, Metaphysics"
        },
        ...
    ]
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_unique_domains(formulas: list[dict]) -> list[str]:
    """Extract unique domain names from all formula records."""
    domains = set()
    for formula in formulas:
        for domain in formula.get("domains", []):
            domains.add(domain)
    return sorted(domains)


def seed_domains(client, domain_names: list[str]) -> dict[str, str]:
    """
    Insert domains and return a mapping of domain name to domain ID.
    """
    domains_to_insert = [{"name": name} for name in domain_names]

    print(f"Inserting {len(domains_to_insert)} domains...")
    response = client.schema("golden_formula_graph").table("domains").insert(domains_to_insert).execute()

    # Create name -> id mapping
    domain_map = {d["name"]: d["id"] for d in response.data}

    print(f"Created {len(response.data)} domains")
    return domain_map


def prepare_formulas_for_insert(formulas: list[dict], domain_map: dict[str, str]) -> list[dict]:
    """
    Convert formula records from JSON format to database format.

    Replaces domain names with domain IDs.
    """
    formulas_to_insert = []

    for formula in formulas:
        domain_names = formula.get("domains", [])
        domain_ids = [domain_map[name] for name in domain_names if name in domain_map]

        if not domain_ids:
            print(f"Warning: Formula '{formula.get('principle', '')[:50]}...' has no valid domains, skipping")
            continue

        formulas_to_insert.append({
            "principle": formula["principle"],
            "domain_ids": domain_ids,
            "reference": formula.get("reference", ""),
        })

    return formulas_to_insert


def seed_formulas(client, formulas_to_insert: list[dict]) -> list[dict]:
    """Insert formulas into the database."""
    print(f"Inserting {len(formulas_to_insert)} formulas...")
    response = client.schema("golden_formula_graph").table("formulas").insert(formulas_to_insert).execute()

    print(f"Created {len(response.data)} formulas")
    return response.data


def clear_existing_data(client):
    """Clear existing data from tables."""
    print("Clearing existing formulas...")
    client.schema("golden_formula_graph").table("formulas").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    print("Clearing existing domains...")
    client.schema("golden_formula_graph").table("domains").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    print("Existing data cleared")


def main():
    """Main function to seed the database from JSON file."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing environment variables")
        print("Please create a .env.local file in the scripts directory with:")
        print("  SUPABASE_URL=your_supabase_url")
        print("  SUPABASE_KEY=your_service_role_key")
        return

    # Check if data file exists
    if not DATA_FILE.exists():
        print(f"ERROR: Data file not found: {DATA_FILE}")
        print("\nPlease create a JSON file with the following format:")
        print("""
[
    {
        "domains": ["Mathematics", "Physics"],
        "principle": "The whole is greater than the sum of its parts",
        "reference": "Aristotle, Metaphysics"
    },
    ...
]
        """)
        return

    # Load and process data
    print(f"Loading data from: {DATA_FILE}")
    formulas_raw = load_formulas_from_json(DATA_FILE)
    print(f"Loaded {len(formulas_raw)} formula records")

    # Extract unique domains
    domain_names = extract_unique_domains(formulas_raw)
    print(f"Found {len(domain_names)} unique domains: {domain_names}")

    client = create_supabase_client()

    # Ask for confirmation before clearing
    print(f"\nThis will:")
    print(f"  1. Clear all existing domains and formulas")
    print(f"  2. Create {len(domain_names)} domains")
    print(f"  3. Create {len(formulas_raw)} formulas")
    print()

    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted")
        return

    # Clear existing data
    clear_existing_data(client)

    # Seed domains and get the name -> id mapping
    domain_map = seed_domains(client, domain_names)

    # Prepare formulas with domain IDs
    formulas_to_insert = prepare_formulas_for_insert(formulas_raw, domain_map)

    # Seed formulas
    formulas = seed_formulas(client, formulas_to_insert)

    print("\nSeeding complete!")
    print(f"  Domains: {len(domain_map)}")
    print(f"  Formulas: {len(formulas)}")


if __name__ == "__main__":
    main()
