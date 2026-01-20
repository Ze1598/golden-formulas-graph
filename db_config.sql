-------- SCHEMA
CREATE SCHEMA golden_formula_graph;

-------- TABLES
CREATE TABLE golden_formula_graph.domains (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) DEFAULT auth.uid()
);

CREATE TABLE golden_formula_graph.formulas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  principle TEXT NOT NULL,
  domain_ids UUID[] NOT NULL,
  reference TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  created_by UUID REFERENCES auth.users(id) DEFAULT auth.uid()
);

CREATE TABLE golden_formula_graph.formula_edges (
  formula_a_id UUID NOT NULL,
  formula_b_id UUID NOT NULL,
  shared_domain_ids UUID[] NOT NULL,
  edge_weight INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (formula_a_id, formula_b_id),
  FOREIGN KEY (formula_a_id) REFERENCES golden_formula_graph.formulas(id) ON DELETE CASCADE,
  FOREIGN KEY (formula_b_id) REFERENCES golden_formula_graph.formulas(id) ON DELETE CASCADE,
  CHECK (formula_a_id < formula_b_id)
);

-- Indexes
CREATE INDEX idx_golden_formula_graph_formulas_domain_ids ON golden_formula_graph.formulas USING GIN (domain_ids);
CREATE INDEX idx_golden_formula_graph_edges_formula_a ON golden_formula_graph.formula_edges(formula_a_id);
CREATE INDEX idx_golden_formula_graph_edges_formula_b ON golden_formula_graph.formula_edges(formula_b_id);
CREATE INDEX idx_golden_formula_graph_edges_weight ON golden_formula_graph.formula_edges(edge_weight);

-------- TRIGGER FUNCTIONS
-- Function to recalculate edges for a single formula
CREATE OR REPLACE FUNCTION golden_formula_graph.recalculate_formula_edges()
RETURNS TRIGGER AS $$
BEGIN
  -- Delete existing edges involving this formula
  DELETE FROM golden_formula_graph.formula_edges
  WHERE formula_a_id = NEW.id OR formula_b_id = NEW.id;
  
  -- Compute new edges with this formula
  INSERT INTO golden_formula_graph.formula_edges (formula_a_id, formula_b_id, shared_domain_ids, edge_weight)
  SELECT 
    LEAST(NEW.id, f.id) as formula_a_id,
    GREATEST(NEW.id, f.id) as formula_b_id,
    ARRAY(
      SELECT unnest(NEW.domain_ids)
      INTERSECT
      SELECT unnest(f.domain_ids)
    ) as shared_domain_ids,
    (
      SELECT COUNT(*)
      FROM unnest(NEW.domain_ids) d1
      WHERE d1 = ANY(f.domain_ids)
    )::INTEGER as edge_weight
  FROM golden_formula_graph.formulas f
  WHERE f.id != NEW.id
    AND EXISTS (
      SELECT 1
      FROM unnest(NEW.domain_ids) d1
      WHERE d1 = ANY(f.domain_ids)
    );
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Manual function to recalculate all edges (for admin utility)
CREATE OR REPLACE FUNCTION golden_formula_graph.recalculate_all_edges()
RETURNS void AS $$
BEGIN
  DELETE FROM golden_formula_graph.formula_edges;
  
  INSERT INTO golden_formula_graph.formula_edges (formula_a_id, formula_b_id, shared_domain_ids, edge_weight)
  SELECT 
    LEAST(f1.id, f2.id) as formula_a_id,
    GREATEST(f1.id, f2.id) as formula_b_id,
    ARRAY(
      SELECT unnest(f1.domain_ids)
      INTERSECT
      SELECT unnest(f2.domain_ids)
    ) as shared_domain_ids,
    (
      SELECT COUNT(*)
      FROM unnest(f1.domain_ids) d1
      WHERE d1 = ANY(f2.domain_ids)
    )::INTEGER as edge_weight
  FROM golden_formula_graph.formulas f1
  CROSS JOIN golden_formula_graph.formulas f2
  WHERE f1.id < f2.id
    AND EXISTS (
      SELECT 1
      FROM unnest(f1.domain_ids) d1
      WHERE d1 = ANY(f2.domain_ids)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-------- TRIGGERS
-- Trigger to recalculate edges after INSERT
CREATE TRIGGER trigger_recalculate_edges_on_insert
  AFTER INSERT ON golden_formula_graph.formulas
  FOR EACH ROW
  EXECUTE FUNCTION golden_formula_graph.recalculate_formula_edges();

-- Trigger to recalculate edges after UPDATE (only if domain_ids changed)
CREATE TRIGGER trigger_recalculate_edges_on_update
  AFTER UPDATE ON golden_formula_graph.formulas
  FOR EACH ROW
  WHEN (OLD.domain_ids IS DISTINCT FROM NEW.domain_ids)
  EXECUTE FUNCTION golden_formula_graph.recalculate_formula_edges();

-------- GRANTS
GRANT USAGE ON SCHEMA golden_formula_graph TO anon;
GRANT USAGE ON SCHEMA golden_formula_graph TO authenticated;

-- Grant SELECT to anon (public read)
GRANT SELECT ON golden_formula_graph.domains TO anon;
GRANT SELECT ON golden_formula_graph.formulas TO anon;
GRANT SELECT ON golden_formula_graph.formula_edges TO anon;

-- Grant full CRUD to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.domains TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.formulas TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.formula_edges TO authenticated;

-- Grant EXECUTE on manual recalculate function to authenticated users
GRANT EXECUTE ON FUNCTION golden_formula_graph.recalculate_all_edges() TO authenticated;

-------- GRANTS
GRANT USAGE ON SCHEMA golden_formula_graph TO anon;
GRANT USAGE ON SCHEMA golden_formula_graph TO authenticated;

-- Grant SELECT to anon (public read)
GRANT SELECT ON golden_formula_graph.domains TO anon;
GRANT SELECT ON golden_formula_graph.formulas TO anon;
GRANT SELECT ON golden_formula_graph.formula_edges TO anon;

-- Grant full CRUD to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.domains TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.formulas TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON golden_formula_graph.formula_edges TO authenticated;

-- Grant EXECUTE on functions to authenticated users
GRANT EXECUTE ON FUNCTION golden_formula_graph.recalculate_all_edges() TO authenticated;
GRANT EXECUTE ON FUNCTION golden_formula_graph.recalculate_formula_edges(UUID) TO authenticated;

-------- RLS
-- Enable Row Level Security
ALTER TABLE golden_formula_graph.domains ENABLE ROW LEVEL SECURITY;
ALTER TABLE golden_formula_graph.formulas ENABLE ROW LEVEL SECURITY;
ALTER TABLE golden_formula_graph.formula_edges ENABLE ROW LEVEL SECURITY;

-- Public read policies
CREATE POLICY "Public read golden_formula_graph.domains" 
  ON golden_formula_graph.domains FOR SELECT 
  USING (true);

CREATE POLICY "Public read golden_formula_graph.formulas" 
  ON golden_formula_graph.formulas FOR SELECT 
  USING (true);

CREATE POLICY "Public read golden_formula_graph.formula_edges" 
  ON golden_formula_graph.formula_edges FOR SELECT 
  USING (true);

-- Authenticated write policies for domains
CREATE POLICY "Authenticated insert golden_formula_graph.domains" 
  ON golden_formula_graph.domains FOR INSERT 
  TO authenticated 
  WITH CHECK (true);

CREATE POLICY "Authenticated modify golden_formula_graph.domains" 
  ON golden_formula_graph.domains FOR UPDATE 
  TO authenticated 
  USING (true);

CREATE POLICY "Authenticated delete golden_formula_graph.domains" 
  ON golden_formula_graph.domains FOR DELETE 
  TO authenticated 
  USING (true);

-- Authenticated write policies for formulas
CREATE POLICY "Authenticated insert golden_formula_graph.formulas" 
  ON golden_formula_graph.formulas FOR INSERT 
  TO authenticated 
  WITH CHECK (true);

CREATE POLICY "Authenticated update golden_formula_graph.formulas" 
  ON golden_formula_graph.formulas FOR UPDATE 
  TO authenticated 
  USING (true);

CREATE POLICY "Authenticated delete golden_formula_graph.formulas" 
  ON golden_formula_graph.formulas FOR DELETE 
  TO authenticated 
  USING (created_by = auth.uid());

-- Authenticated write policies for formula_edges
CREATE POLICY "Authenticated insert golden_formula_graph.formula_edges" 
  ON golden_formula_graph.formula_edges FOR INSERT 
  TO authenticated 
  WITH CHECK (true);

CREATE POLICY "Authenticated update golden_formula_graph.formula_edges" 
  ON golden_formula_graph.formula_edges FOR UPDATE 
  TO authenticated 
  USING (true);

CREATE POLICY "Authenticated delete golden_formula_graph.formula_edges" 
  ON golden_formula_graph.formula_edges FOR DELETE 
  TO authenticated 
  USING (true);


--DEBUG ONLY FOR SEEDING TABLES
-- GRANT USAGE ON SCHEMA golden_formula_graph TO service_role;
-- GRANT ALL ON ALL TABLES IN SCHEMA golden_formula_graph TO service_role;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA golden_formula_graph TO service_role;
