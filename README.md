# Golden Formulas Graph

A knowledge graph visualization application for exploring principles across multiple domains of knowledge.

## Architecture

### Technology Stack

- **Frontend/Application**: Streamlit (Python)
- **Database**: PostgreSQL via Supabase
- **Visualization**: Plotly for interactive network graphs
- **Authentication**: Supabase Auth with magic link email authentication

### Application Structure

```
app.py                    # Main visualization page (public)
pages/
  admin.py                # Admin CRUD interface (auth protected)
utils/
  supabase_client.py      # Database operations and client management
  auth.py                 # Authentication utilities
  graph.py                # Plotly graph generation
```

### Data Model

The application uses a custom PostgreSQL schema (`golden_formula_graph`) with three core tables:

**domains**
- Represents categories or fields of knowledge (e.g., Physics, Economics, Psychology)
- Fields: `id` (UUID), `name` (unique), `created_by`, `created_at`

**formulas**
- Represents principles or concepts that can belong to multiple domains
- Fields: `id` (UUID), `principle` (text description), `domain_ids` (UUID array), `reference` (source attribution), `created_by`, `created_at`, `updated_at`
- The `domain_ids` array enables many-to-many relationships without a junction table

**formula_edges**
- Pre-computed edges between formulas that share domains
- Fields: `id` (UUID), `formula_a_id`, `formula_b_id`, `shared_domain_ids` (UUID array), `edge_weight` (count of shared domains)
- Automatically maintained by database triggers on formula insert/update

### Graph Computation

Edges between formulas are computed at the database level using PostgreSQL triggers. When a formula is created or updated, the `recalculate_formula_edges()` function automatically:

1. Removes existing edges involving that principle
2. Finds all other principles that share at least one domain
3. Creates new edge records with the shared domain IDs and edge weight

This approach offloads graph computation from the application layer and ensures edges stay synchronized with formula data.

### Visualization

The network graph uses a domain-clustered layout:

- Principles are grouped by their primary domain (first in the array)
- Groups are arranged in a circular pattern
- Within each group, principles are placed in concentric rings
- Edge lines connect principles that share domains, with line thickness proportional to edge weight
- Node size reflects the number of connections (degree centrality)
- Colors are assigned per domain for visual distinction

### Authentication Flow

The admin interface uses Supabase magic link authentication:

1. User enters email address
2. Supabase sends a magic link to the email
3. User clicks the link, which redirects with access/refresh tokens in the URL fragment
4. Application extracts tokens and establishes an authenticated session
5. Authenticated client is used for write operations (create, update, delete)

### Database Permissions

The application uses Supabase's role-based access:

- `anon` role: Read access to all tables (public visualization)
- `authenticated` role: Full CRUD access (admin operations)
- `service_role`: Used by seed scripts to bulk upload the original dataset