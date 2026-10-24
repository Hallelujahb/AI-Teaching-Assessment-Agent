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
-- Ids are issued by the system: students get ST001, ST002 ... in student_id; lecturers get LT001 ... in staff_id.
ALTER TABLE users ADD COLUMN IF NOT EXISTS staff_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS one_account_per_staff ON users (staff_id) WHERE staff_id IS NOT NULL;

-- Classes: a lecturer groups students so an exam can be assigned to the whole group at once.
CREATE TABLE IF NOT EXISTS classes (
  id SERIAL PRIMARY KEY,
  owner_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_class_name_per_owner ON classes (owner_id, lower(name));
CREATE TABLE IF NOT EXISTS class_members (
  class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (class_id, user_id)
);

-- An assignment gives one assessment to a fixed set of students. It owns a submission batch, so the
-- answers students type land in the same tables the grading flow already reads.
CREATE TABLE IF NOT EXISTS assignments (
  id SERIAL PRIMARY KEY,
  assessment_id INT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
  batch_id INT NOT NULL UNIQUE REFERENCES submission_batches(id) ON DELETE CASCADE,
  class_id INT REFERENCES classes(id) ON DELETE SET NULL,
  assigned_by INT REFERENCES users(id) ON DELETE SET NULL,
  time_limit_minutes INT CHECK (time_limit_minutes BETWEEN 1 AND 300),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS assignment_students (
  assignment_id INT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ,
  PRIMARY KEY (assignment_id, user_id)
);

-- Forgotten passwords. No email service is used: staff issue a one-time code (stored hashed).
CREATE TABLE IF NOT EXISTS password_resets (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT,
  issued_by INT REFERENCES users(id) ON DELETE SET NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  attempts INT NOT NULL DEFAULT 0,
  used_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_reset_per_user ON password_resets (user_id) WHERE used_at IS NULL;
