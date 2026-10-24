-- Qeleme schema. Applied by: python -m app.setup_db
-- Owner: P2. Tables and rules are described in section 5 of the plan.
-- gen_random_uuid() needs Postgres 13 or newer.
-- assessments.id is a whole number (SERIAL) so ids match docs/api-examples.md and seed.py.

CREATE TABLE IF NOT EXISTS assessments (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  question TEXT NOT NULL,
  reference_answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rubric_criteria (
  id SERIAL PRIMARY KEY,
  assessment_id INT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  position INT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  max_score INT NOT NULL CHECK (max_score > 0),
  UNIQUE (assessment_id, position)
);

CREATE TABLE IF NOT EXISTS submission_batches (
  id SERIAL PRIMARY KEY,
  assessment_id INT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (assessment_id, label)
);

CREATE TABLE IF NOT EXISTS submissions (
  id SERIAL PRIMARY KEY,
  batch_id INT NOT NULL REFERENCES submission_batches(id) ON DELETE CASCADE,
  student_id TEXT NOT NULL CHECK (length(student_id) > 0),
  answer TEXT NOT NULL CHECK (length(answer) <= 2000),
  UNIQUE (batch_id, student_id)
);

CREATE TABLE IF NOT EXISTS grading_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id INT NOT NULL REFERENCES submission_batches(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  model TEXT,
  rubric_snapshot JSONB NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  error TEXT
);

-- One running run per batch, enforced by the database itself (two requests cannot both start).
CREATE UNIQUE INDEX IF NOT EXISTS one_running_run_per_batch
  ON grading_runs (batch_id) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS grading_runs_batch_idx ON grading_runs (batch_id, started_at);

CREATE TABLE IF NOT EXISTS tool_logs (
  id SERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES grading_runs(id) ON DELETE CASCADE,
  tool_name TEXT NOT NULL,
  arguments JSONB,
  outcome TEXT NOT NULL,
  duration_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tool_logs_run_idx ON tool_logs (run_id, id);

CREATE TABLE IF NOT EXISTS ai_proposals (
  id SERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES grading_runs(id) ON DELETE CASCADE,
  submission_id INT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  answer_status TEXT NOT NULL CHECK (answer_status IN
    ('complete', 'incomplete', 'unassessable', 'blank', 'needs_manual_grading')),
  scores JSONB,
  evidence JSONB,
  explanations JSONB,
  flags JSONB,
  feedback TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, submission_id)
);

CREATE TABLE IF NOT EXISTS reviewed_results (
  id SERIAL PRIMARY KEY,
  submission_id INT NOT NULL UNIQUE REFERENCES submissions(id) ON DELETE CASCADE,
  proposal_id INT NOT NULL REFERENCES ai_proposals(id),
  run_id UUID NOT NULL REFERENCES grading_runs(id),
  scores JSONB NOT NULL,
  total INT NOT NULL,
  percentage NUMERIC(5, 1) NOT NULL,
  feedback TEXT NOT NULL DEFAULT '',
  approved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Accounts and roles (superadmin, lecturer, student). A student account is linked to
-- submissions by student_id (for example ST001).
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('superadmin', 'lecturer', 'student')),
  student_id TEXT,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Sign-up requests wait as 'pending' until approved. Existing accounts stay 'active'.
ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active'));
-- One account per student id, so nobody can claim an id that is already taken.
CREATE UNIQUE INDEX IF NOT EXISTS one_account_per_student ON users (student_id) WHERE role = 'student' AND student_id IS NOT NULL;