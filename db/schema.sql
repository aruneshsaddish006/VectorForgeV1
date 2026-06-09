BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  plan TEXT NOT NULL DEFAULT 'free',
  stripe_customer_id TEXT UNIQUE,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  avatar_url TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'approver', 'builder', 'viewer')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS user_password_credentials (
  user_id UUID PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  password_iterations INTEGER NOT NULL DEFAULT 260000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_identities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('password', 'google')),
  provider_user_id TEXT NOT NULL,
  email TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

CREATE TABLE IF NOT EXISTS auth_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,
  provider TEXT NOT NULL CHECK (provider IN ('password', 'google')),
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'archived')),
  created_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS use_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  task_type TEXT NOT NULL,
  business_problem TEXT NOT NULL,
  kpis JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'training', 'deployed', 'archived')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS problem_intakes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  problem_statement TEXT NOT NULL,
  domain_context TEXT,
  timeline TEXT,
  inferred_intent TEXT,
  clarifying_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
  raw_response JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  projected_roi TEXT,
  feasibility TEXT,
  recommended_next_step TEXT,
  source TEXT NOT NULL DEFAULT 'strategy_agent',
  status TEXT NOT NULL DEFAULT 'complete' CHECK (status IN ('draft', 'complete', 'approved', 'rejected')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategy_use_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES ai_strategies(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  task_type TEXT NOT NULL,
  confidence TEXT,
  projected_roi TEXT,
  rationale TEXT,
  rank INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  use_case_id UUID REFERENCES use_cases(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  created_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
  sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'agent', 'system')),
  agent_name TEXT,
  content TEXT NOT NULL,
  rich_card_type TEXT,
  rich_card_ref_id UUID,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  uploaded_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  file_name TEXT NOT NULL,
  file_type TEXT NOT NULL,
  storage_uri TEXT NOT NULL,
  size_bytes BIGINT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_source_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  path TEXT NOT NULL CHECK (path IN ('upload', 'exa', 'hybrid')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'waiting_approval', 'running', 'complete', 'failed')),
  input_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  cost_estimate NUMERIC(12, 4),
  cost_actual NUMERIC(12, 4),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exa_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  data_source_run_id UUID NOT NULL REFERENCES data_source_runs(id) ON DELETE CASCADE,
  external_run_id TEXT UNIQUE,
  previous_external_run_id TEXT,
  query TEXT NOT NULL,
  effort TEXT NOT NULL CHECK (effort IN ('low', 'medium', 'high', 'xhigh')),
  output_schema JSONB NOT NULL,
  input_data JSONB NOT NULL DEFAULT '[]'::jsonb,
  exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'enriching', 'validating', 'complete', 'failed')),
  structured_output JSONB,
  grounding JSONB NOT NULL DEFAULT '{}'::jsonb,
  cost_dollars NUMERIC(12, 4),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS exa_run_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exa_run_id UUID NOT NULL REFERENCES exa_runs(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  label TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  data_source_run_id UUID REFERENCES data_source_runs(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN ('uploaded', 'exa', 'hybrid')),
  storage_uri TEXT,
  row_count INTEGER NOT NULL DEFAULT 0,
  column_count INTEGER NOT NULL DEFAULT 0,
  quality_score INTEGER CHECK (quality_score BETWEEN 0 AND 100),
  target_column TEXT,
  task_type TEXT,
  status TEXT NOT NULL DEFAULT 'preview' CHECK (status IN ('preview', 'confirmed', 'training', 'archived')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_columns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  inferred_type TEXT NOT NULL CHECK (inferred_type IN ('string', 'number', 'integer', 'boolean', 'datetime', 'text')),
  null_pct NUMERIC(5, 2) NOT NULL DEFAULT 0,
  sample_value TEXT,
  source TEXT NOT NULL CHECK (source IN ('uploaded', 'exa', 'enriched')),
  is_target BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (dataset_id, name)
);

CREATE TABLE IF NOT EXISTS dataset_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  row_index INTEGER NOT NULL,
  record JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, row_index)
);

CREATE TABLE IF NOT EXISTS provenance_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  title TEXT,
  publisher TEXT,
  retrieved_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS dataset_field_provenance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_record_id UUID NOT NULL REFERENCES dataset_records(id) ON DELETE CASCADE,
  column_id UUID REFERENCES dataset_columns(id) ON DELETE CASCADE,
  source_id UUID NOT NULL REFERENCES provenance_sources(id) ON DELETE CASCADE,
  evidence TEXT,
  confidence NUMERIC(5, 2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schema_confirmations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  confirmed_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  target_column TEXT NOT NULL,
  quality_fixes JSONB NOT NULL DEFAULT '[]'::jsonb,
  confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS training_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  engine TEXT NOT NULL DEFAULT 'autogluon',
  predictor_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'complete', 'failed')),
  best_metric_name TEXT,
  best_metric_value NUMERIC(12, 6),
  compute_cost NUMERIC(12, 4),
  train_time_seconds INTEGER,
  sagemaker_job_arn TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS model_leaderboard_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  training_run_id UUID NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  rank INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  metric_value NUMERIC(12, 6) NOT NULL,
  inference_latency_ms INTEGER,
  is_best BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (training_run_id, rank)
);

CREATE TABLE IF NOT EXISTS feature_importances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  training_run_id UUID NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  feature_name TEXT NOT NULL,
  importance NUMERIC(12, 6) NOT NULL,
  rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
  corpus_source TEXT NOT NULL CHECK (corpus_source IN ('uploaded_documents', 'exa_web', 'hybrid')),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'complete', 'failed')),
  trials_run INTEGER NOT NULL DEFAULT 0,
  faithfulness NUMERIC(6, 4),
  context_recall NUMERIC(6, 4),
  p95_latency_ms INTEGER,
  compute_cost NUMERIC(12, 4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag_pipeline_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rag_run_id UUID NOT NULL REFERENCES rag_runs(id) ON DELETE CASCADE,
  stage TEXT NOT NULL,
  detail TEXT,
  value TEXT,
  rank INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rag_configurations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rag_run_id UUID NOT NULL REFERENCES rag_runs(id) ON DELETE CASCADE,
  retriever TEXT,
  embedding_model TEXT,
  reranker TEXT,
  top_k INTEGER,
  chunk_size INTEGER,
  chunk_overlap INTEGER,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_winner BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS deployments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  use_case_id UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
  training_run_id UUID REFERENCES training_runs(id) ON DELETE SET NULL,
  rag_run_id UUID REFERENCES rag_runs(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'deploying', 'deployed', 'failed', 'disabled')),
  environment TEXT NOT NULL DEFAULT 'production',
  model_api_url TEXT,
  rag_api_url TEXT,
  version TEXT NOT NULL DEFAULT 'v1',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deployed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  use_case_id UUID REFERENCES use_cases(id) ON DELETE CASCADE,
  requested_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  approved_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  approval_type TEXT NOT NULL CHECK (approval_type IN ('exa_run', 'schema_confirmation', 'training', 'deployment', 'billing')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
  summary TEXT NOT NULL,
  cost_estimate NUMERIC(12, 4),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS billing_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  plan TEXT NOT NULL DEFAULT 'free',
  exa_credit_allowance NUMERIC(12, 4) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  use_case_id UUID REFERENCES use_cases(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('exa_acu', 'exa_search', 'autogluon_compute', 'autorag_compute', 'deployment_runtime')),
  provider TEXT NOT NULL,
  units NUMERIC(12, 4) NOT NULL,
  unit_cost NUMERIC(12, 6) NOT NULL,
  total_cost NUMERIC(12, 4) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_request_id UUID REFERENCES approval_requests(id) ON DELETE SET NULL,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  amount NUMERIC(12, 4) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'charged')),
  stripe_payment_intent_id TEXT,
  approved_by UUID REFERENCES app_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS activity_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  use_case_id UUID REFERENCES use_cases(id) ON DELETE CASCADE,
  actor_user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
  agent_name TEXT,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  tool_name TEXT,
  cost NUMERIC(12, 4),
  detail TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id UUID REFERENCES app_users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  before_state JSONB,
  after_state JSONB,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'organizations',
    'app_users',
    'user_password_credentials',
    'auth_identities',
    'projects',
    'use_cases',
    'ai_strategies',
    'exa_runs',
    'datasets',
    'billing_accounts',
    'chat_threads'
  ]
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_updated_at ON %I', tbl, tbl);
    EXECUTE format('CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()', tbl, tbl);
  END LOOP;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_workspace_members_org ON workspace_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_auth_identities_user ON auth_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token);
CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(organization_id);
CREATE INDEX IF NOT EXISTS idx_use_cases_project ON use_cases(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created ON chat_messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_data_source_runs_use_case ON data_source_runs(use_case_id);
CREATE INDEX IF NOT EXISTS idx_exa_runs_data_source ON exa_runs(data_source_run_id);
CREATE INDEX IF NOT EXISTS idx_datasets_use_case ON datasets(use_case_id);
CREATE INDEX IF NOT EXISTS idx_dataset_records_dataset ON dataset_records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_training_runs_dataset ON training_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_rag_runs_use_case ON rag_runs(use_case_id);
CREATE INDEX IF NOT EXISTS idx_deployments_use_case ON deployments(use_case_id);
CREATE INDEX IF NOT EXISTS idx_activity_events_org_created ON activity_events(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created ON audit_logs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_org_created ON usage_events(organization_id, created_at DESC);

INSERT INTO schema_migrations(version)
VALUES ('001_complete_app_schema')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations(version)
VALUES ('002_auth_tables')
ON CONFLICT (version) DO NOTHING;

COMMIT;
