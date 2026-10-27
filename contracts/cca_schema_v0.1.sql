-- CCA backend design v0.1; target: MySQL 8.4 / InnoDB.
-- REVIEW DRAFT: not executed against a database. Apply only through reviewed migrations.
-- No DROP, default passwords, database creation or privilege changes.
-- All DATETIME values are UTC. Connection sql_mode must be strict.
SET time_zone = '+00:00';

CREATE TABLE users (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  account VARCHAR(64) NOT NULL,
  account_norm VARBINARY(768) NOT NULL,
  display_name VARCHAR(50) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(16) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  auth_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_users_account (account_norm),
  CONSTRAINT ck_users_role CHECK (role IN ('student','admin')),
  CONSTRAINT ck_users_names CHECK (CHAR_LENGTH(account) BETWEEN 3 AND 64 AND CHAR_LENGTH(display_name) BETWEEN 1 AND 50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE auth_sessions (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  token_digest BINARY(32) NOT NULL,
  auth_version BIGINT UNSIGNED NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_sessions_token (token_digest),
  KEY ix_sessions_user_expiry (user_id, expires_at),
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT ck_sessions_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE courses (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  code VARCHAR(32) NOT NULL,
  code_norm VARBINARY(384) NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_courses_code (code_norm),
  CONSTRAINT ck_courses_fields CHECK (CHAR_LENGTH(code) BETWEEN 1 AND 32 AND CHAR_LENGTH(name) BETWEEN 1 AND 100 AND (description IS NULL OR CHAR_LENGTH(description) <= 2000))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE schedules (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  course_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  class_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  location VARCHAR(200) NULL,
  overlap_reason VARCHAR(500) NULL,
  version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_schedule_exact (user_id, course_id, class_date, start_time, end_time),
  KEY ix_schedule_person_date (user_id, class_date, start_time, id),
  CONSTRAINT fk_schedule_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_schedule_course FOREIGN KEY (course_id) REFERENCES courses(id),
  CONSTRAINT ck_schedule_times CHECK (start_time >= '00:00:00' AND end_time < '24:00:00' AND start_time < end_time AND SECOND(start_time)=0 AND SECOND(end_time)=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE conversation_states (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  session_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  active_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  KEY ix_conversations_owner (user_id, session_id),
  CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_conversations_session FOREIGN KEY (session_id) REFERENCES auth_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE chat_requests (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  client_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  session_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  conversation_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  request_digest BINARY(32) NOT NULL,
  state VARCHAR(16) NOT NULL,
  cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_at DATETIME(6) NOT NULL,
  deadline_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  school_timezone VARCHAR(64) NOT NULL,
  model_calls INT UNSIGNED NOT NULL DEFAULT 0,
  tool_calls INT UNSIGNED NOT NULL DEFAULT 0,
  owner_instance VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  fence BIGINT UNSIGNED NOT NULL DEFAULT 1,
  lease_until DATETIME(6) NULL,
  terminal_reason VARCHAR(64) NULL,
  instruction_class VARCHAR(16) NULL,
  plan_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  operation_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  UNIQUE KEY uq_chat_client (user_id, client_request_id),
  KEY ix_chat_recovery (state, lease_until),
  KEY ix_chat_owner (user_id, conversation_id, accepted_at),
  CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_chat_session FOREIGN KEY (session_id) REFERENCES auth_sessions(id),
  CONSTRAINT fk_chat_conversation FOREIGN KEY (conversation_id) REFERENCES conversation_states(id),
  CONSTRAINT ck_chat_state CHECK (state IN ('accepted','running','succeeded','failed','cancelled')),
  CONSTRAINT ck_chat_instruction CHECK (instruction_class IS NULL OR instruction_class IN ('none','explicit','ambiguous','denied')),
  CONSTRAINT ck_chat_deadline CHECK (deadline_at > accepted_at),
  CONSTRAINT ck_chat_terminal CHECK ((state IN ('accepted','running') AND finished_at IS NULL) OR (state IN ('succeeded','failed','cancelled') AND finished_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE ai_capacity_slots (
slot_no INT UNSIGNED PRIMARY KEY,
  request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  owner_instance VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  fence BIGINT UNSIGNED NOT NULL DEFAULT 0,
  lease_until DATETIME(6) NULL,
  UNIQUE KEY uq_capacity_request (request_id),
  KEY ix_capacity_lease (lease_until),
  CONSTRAINT fk_capacity_request FOREIGN KEY (request_id) REFERENCES chat_requests(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE plan_drafts (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  session_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  conversation_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  origin_chat_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  current_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  expires_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  KEY ix_drafts_expiry (expires_at),
  CONSTRAINT fk_drafts_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_drafts_session FOREIGN KEY (session_id) REFERENCES auth_sessions(id),
  CONSTRAINT fk_drafts_conversation FOREIGN KEY (conversation_id) REFERENCES conversation_states(id),
  CONSTRAINT fk_drafts_origin FOREIGN KEY (origin_chat_request_id) REFERENCES chat_requests(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE plan_draft_versions (
draft_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  draft_version BIGINT UNSIGNED NOT NULL,
  operation_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  schema_version INT UNSIGNED NOT NULL DEFAULT 1,
  payload JSON NULL,
  content_digest BINARY(32) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  payload_cleared_at DATETIME(6) NULL,
  PRIMARY KEY (draft_id, draft_version),
  UNIQUE KEY uq_draft_operation (operation_id),
  CONSTRAINT fk_draft_version_header FOREIGN KEY (draft_id) REFERENCES plan_drafts(id),
  CONSTRAINT ck_draft_payload CHECK ((payload IS NOT NULL AND payload_cleared_at IS NULL) OR (payload IS NULL AND payload_cleared_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE write_operations (
user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  operation_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source VARCHAR(16) NOT NULL,
  origin_chat_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  authorization_chat_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  draft_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  draft_version BIGINT UNSIGNED NULL,
  content_digest BINARY(32) NOT NULL,
  state VARCHAR(16) NOT NULL,
  resolution VARCHAR(16) NOT NULL DEFAULT 'confirmed',
  plan_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  error_code VARCHAR(64) NULL,
  retryable BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (user_id, operation_id),
  KEY ix_operations_recovery (state, updated_at),
  CONSTRAINT fk_operations_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_operations_origin FOREIGN KEY (origin_chat_request_id) REFERENCES chat_requests(id),
  CONSTRAINT fk_operations_auth_chat FOREIGN KEY (authorization_chat_request_id) REFERENCES chat_requests(id),
  CONSTRAINT fk_operations_draft FOREIGN KEY (draft_id, draft_version) REFERENCES plan_draft_versions(draft_id, draft_version),
  CONSTRAINT ck_operations_state CHECK (state IN ('pending','succeeded','failed','deleted')),
  CONSTRAINT ck_operations_resolution CHECK (resolution IN ('confirmed','recovering')),
  CONSTRAINT ck_operations_source CHECK (source IN ('manual','assistant')),
  CONSTRAINT ck_operations_draft_pair CHECK ((draft_id IS NULL AND draft_version IS NULL) OR (draft_id IS NOT NULL AND draft_version IS NOT NULL)),
  CONSTRAINT ck_operations_result CHECK ((state IN ('succeeded','deleted') AND plan_id IS NOT NULL) OR (state IN ('pending','failed') AND plan_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE save_grants (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  session_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  trace_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  authorization_kind VARCHAR(32) NOT NULL,
  authorization_chat_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  draft_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  draft_version BIGINT UNSIGNED NULL,
  operation_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  content_digest BINARY(32) NOT NULL,
  state VARCHAR(16) NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  consumed_at DATETIME(6) NULL,
  KEY ix_grants_operation (user_id, operation_id),
  KEY ix_grants_expiry (state, expires_at),
  CONSTRAINT fk_grants_operation FOREIGN KEY (user_id, operation_id) REFERENCES write_operations(user_id, operation_id),
  CONSTRAINT fk_grants_session FOREIGN KEY (session_id) REFERENCES auth_sessions(id),
  CONSTRAINT fk_grants_auth_chat FOREIGN KEY (authorization_chat_request_id) REFERENCES chat_requests(id),
  CONSTRAINT fk_grants_draft FOREIGN KEY (draft_id, draft_version) REFERENCES plan_draft_versions(draft_id, draft_version),
  CONSTRAINT ck_grants_state CHECK (state IN ('issued','consumed','expired','revoked')),
  CONSTRAINT ck_grants_kind CHECK (authorization_kind IN ('manual_form','draft_button','direct_instruction')),
  CONSTRAINT ck_grants_draft_pair CHECK ((draft_id IS NULL AND draft_version IS NULL) OR (draft_id IS NOT NULL AND draft_version IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE study_plans (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  operation_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  title VARCHAR(100) NULL,
  goal VARCHAR(500) NULL,
  start_date DATE NULL,
  end_date DATE NULL,
  content MEDIUMTEXT NULL,
  source VARCHAR(16) NOT NULL,
  basis_snapshot JSON NULL,
  version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  deleted_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_plan_operation (user_id, operation_id),
  KEY ix_plan_list (user_id, deleted_at, updated_at, id),
  CONSTRAINT fk_plan_operation FOREIGN KEY (user_id, operation_id) REFERENCES write_operations(user_id, operation_id),
  CONSTRAINT ck_plan_source CHECK (source IN ('manual','assistant')),
  CONSTRAINT ck_plan_dates CHECK ((start_date IS NULL AND end_date IS NULL) OR (start_date IS NOT NULL AND end_date IS NOT NULL AND start_date <= end_date)),
  CONSTRAINT ck_plan_body CHECK ((deleted_at IS NULL AND title IS NOT NULL AND content IS NOT NULL AND CHAR_LENGTH(title) BETWEEN 1 AND 100 AND CHAR_LENGTH(content) BETWEEN 1 AND 10000) OR (deleted_at IS NOT NULL AND title IS NULL AND content IS NULL AND goal IS NULL AND start_date IS NULL AND end_date IS NULL AND basis_snapshot IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE assistant_save_slots (
user_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  operation_id VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  plan_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (user_id, request_id),
  CONSTRAINT fk_save_slot_request FOREIGN KEY (request_id) REFERENCES chat_requests(id),
  CONSTRAINT fk_save_slot_operation FOREIGN KEY (user_id, operation_id) REFERENCES write_operations(user_id, operation_id),
  CONSTRAINT fk_save_slot_plan FOREIGN KEY (plan_id) REFERENCES study_plans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE corpus_control (
singleton_id TINYINT UNSIGNED PRIMARY KEY,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
  active_vector_space VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NULL,
  publish_frozen BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT ck_corpus_singleton CHECK (singleton_id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE document_batches (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  uploaded_by VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  state VARCHAR(16) NOT NULL,
  expected_files INT UNSIGNED NOT NULL,
  total_bytes BIGINT UNSIGNED NOT NULL,
  error_code VARCHAR(64) NULL,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  KEY ix_batch_state (state, updated_at),
  CONSTRAINT fk_batch_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id),
  CONSTRAINT ck_batch_state CHECK (state IN ('accepted','processing','published','compensating','failed')),
  CONSTRAINT ck_batch_size CHECK (expected_files BETWEEN 1 AND 10 AND total_bytes <= 52428800),
  CONSTRAINT ck_batch_publication CHECK ((state='published' AND published_at IS NOT NULL) OR (state<>'published' AND published_at IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE documents (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  batch_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  file_type VARCHAR(8) NOT NULL,
  byte_size BIGINT UNSIGNED NOT NULL,
  original_storage_key VARCHAR(512) NULL,
  visibility VARCHAR(16) NOT NULL DEFAULT 'unpublished',
  processing_state VARCHAR(32) NOT NULL,
  active_version_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  mutation_task_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  error_code VARCHAR(64) NULL,
  deleted_at DATETIME(6) NULL,
  cleanup_state VARCHAR(16) NOT NULL DEFAULT 'not_required',
  version BIGINT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  KEY ix_document_list (visibility, processing_state, created_at, id),
  KEY ix_document_batch (batch_id),
  CONSTRAINT fk_document_batch FOREIGN KEY (batch_id) REFERENCES document_batches(id),
  CONSTRAINT ck_document_type CHECK (file_type IN ('txt','md','pdf','docx')),
  CONSTRAINT ck_document_size CHECK (byte_size <= 20971520),
  CONSTRAINT ck_document_visibility CHECK (visibility IN ('unpublished','shared','removed')),
  CONSTRAINT ck_document_removed CHECK ((visibility='removed' AND deleted_at IS NOT NULL) OR (visibility<>'removed' AND deleted_at IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE document_versions (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  document_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  version_no BIGINT UNSIGNED NOT NULL,
  state VARCHAR(16) NOT NULL,
  content_digest BINARY(32) NULL,
  parser_config_digest BINARY(32) NOT NULL,
  vector_space VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  selected_attempt_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  extracted_text_key VARCHAR(512) NULL,
  error_code VARCHAR(64) NULL,
  active_document_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin GENERATED ALWAYS AS (CASE WHEN state='active' THEN document_id ELSE NULL END) STORED,
  created_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_document_version (document_id, version_no),
  UNIQUE KEY uq_document_one_active (active_document_id),
  CONSTRAINT fk_version_document FOREIGN KEY (document_id) REFERENCES documents(id),
  CONSTRAINT ck_document_version_state CHECK (state IN ('staging','ready','active','retired','failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE chunks (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  document_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  version_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  chunk_index INT UNSIGNED NOT NULL,
  text_content MEDIUMTEXT NOT NULL,
  page_number INT UNSIGNED NULL,
  location_label VARCHAR(100) NOT NULL,
  content_digest BINARY(32) NOT NULL,
  UNIQUE KEY uq_chunk_order (version_id, chunk_index),
  CONSTRAINT fk_chunk_document FOREIGN KEY (document_id) REFERENCES documents(id),
  CONSTRAINT fk_chunk_version FOREIGN KEY (version_id) REFERENCES document_versions(id),
  CONSTRAINT ck_chunk_text CHECK (CHAR_LENGTH(text_content) > 0),
  CONSTRAINT ck_chunk_page CHECK (page_number IS NULL OR page_number >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE citation_references (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  document_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  version_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  chunk_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  revoked_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_citation_chunk (chunk_id),
  KEY ix_citation_document (document_id, version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE background_tasks (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  kind VARCHAR(32) NOT NULL,
  object_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dedupe_key VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  state VARCHAR(16) NOT NULL,
  priority INT NOT NULL DEFAULT 0,
  attempt INT UNSIGNED NOT NULL DEFAULT 0,
  max_attempts INT UNSIGNED NOT NULL DEFAULT 5,
  fence BIGINT UNSIGNED NOT NULL DEFAULT 0,
  owner_instance VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  lease_until DATETIME(6) NULL,
  next_run_at DATETIME(6) NOT NULL,
  error_code VARCHAR(64) NULL,
  error_summary VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_task_action (kind, object_id, dedupe_key),
  KEY ix_task_claim (state, next_run_at, priority, id),
  KEY ix_task_lease (state, lease_until),
  CONSTRAINT ck_task_state CHECK (state IN ('pending','running','retry_wait','succeeded','failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE storage_attempts (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  task_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  task_fence BIGINT UNSIGNED NOT NULL,
  version_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  file_prefix VARCHAR(512) NOT NULL,
  vector_namespace VARCHAR(512) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  io_state VARCHAR(16) NOT NULL,
  inflight_writes INT UNSIGNED NOT NULL DEFAULT 0,
  barrier_confirmed_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_storage_attempt (task_id, task_fence),
  KEY ix_storage_version (version_id, io_state),
  CONSTRAINT fk_attempt_task FOREIGN KEY (task_id) REFERENCES background_tasks(id),
  CONSTRAINT fk_attempt_version FOREIGN KEY (version_id) REFERENCES document_versions(id),
  CONSTRAINT ck_attempt_state CHECK (io_state IN ('active','quiescing','unknown','settled','cleaned'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE audit_events (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  actor_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  action VARCHAR(64) NOT NULL,
  object_type VARCHAR(32) NOT NULL,
  object_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  result VARCHAR(32) NOT NULL,
  request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  duration_ms BIGINT UNSIGNED NULL,
  metadata JSON NULL,
  created_at DATETIME(6) NOT NULL,
  KEY ix_audit_object (object_type, object_id, created_at),
  KEY ix_audit_request (request_id),
  KEY ix_audit_retention (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE outbox_events (
id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  event_type VARCHAR(64) NOT NULL,
  aggregate_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  metadata JSON NOT NULL,
  state VARCHAR(16) NOT NULL DEFAULT 'pending',
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  next_run_at DATETIME(6) NOT NULL,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL,
  KEY ix_outbox_dispatch (state, next_run_at, id),
  CONSTRAINT ck_outbox_state CHECK (state IN ('pending','published','failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

-- Circular references are added after all tables exist. Cross-owner consistency
-- and active-version ownership must also be checked by the application transaction.
ALTER TABLE conversation_states ADD CONSTRAINT fk_conversation_active FOREIGN KEY (active_request_id) REFERENCES chat_requests(id);
ALTER TABLE chat_requests ADD CONSTRAINT fk_chat_plan FOREIGN KEY (plan_id) REFERENCES study_plans(id);
ALTER TABLE write_operations ADD CONSTRAINT fk_operation_plan FOREIGN KEY (plan_id) REFERENCES study_plans(id);
ALTER TABLE documents ADD CONSTRAINT fk_document_active FOREIGN KEY (active_version_id) REFERENCES document_versions(id);
ALTER TABLE documents ADD CONSTRAINT fk_document_mutation FOREIGN KEY (mutation_task_id) REFERENCES background_tasks(id);
ALTER TABLE document_versions ADD CONSTRAINT fk_version_attempt FOREIGN KEY (selected_attempt_id) REFERENCES storage_attempts(id);

-- Citation tombstones intentionally have no chunk FK so physical text cleanup
-- cannot remove the record needed to return CITATION_UNAVAILABLE.
-- Seed control records only; this does not create an administrator.
INSERT INTO corpus_control (singleton_id, revision, publish_frozen, updated_at)
VALUES (1, 0, TRUE, UTC_TIMESTAMP(6));
INSERT INTO ai_capacity_slots (slot_no) VALUES (1),(2),(3),(4),(5);

