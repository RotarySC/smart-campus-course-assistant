-- M4 数据库反注入探针（qa-verifier 独立于 owner 用例）
--
-- 用法（阶段 B 驱动脚本逐条执行，脚本见 verification/scripts/m4-injection.ps1）：
--   1) 执行 -- @setup 段落建立最小合法父行；
--   2) 逐条执行 -- @probe <n> 段落，期望 MySQL 报错（CHECK 3819 / 唯一键 1062 / FK 1452 / 长度 1406）；
--   3) 执行 -- @control 段落，期望成功（证明不是整库拒绝写入）；
--   4) 执行 -- @teardown 清理（仅 cca_test_release，FK 关闭后 TRUNCATE）。
--
-- 只允许在 cca_test_release 执行；不得指向 cca / cca_test_core|knowledge|assistant。

-- @setup
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE chunks;
TRUNCATE TABLE document_versions;
TRUNCATE TABLE documents;
TRUNCATE TABLE document_batches;
TRUNCATE TABLE corpus_control;
TRUNCATE TABLE chat_requests;
TRUNCATE TABLE conversation_states;
TRUNCATE TABLE schedules;
TRUNCATE TABLE auth_sessions;
TRUNCATE TABLE courses;
TRUNCATE TABLE users;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO corpus_control (singleton_id, revision, publish_frozen, updated_at)
VALUES (1, 0, TRUE, UTC_TIMESTAMP(6));

INSERT INTO users (id, account, account_norm, display_name, password_hash, role, enabled, auth_version, version, created_at, updated_at)
VALUES ('qa_p5_user', 'qa_p5_user', X'71615F70355F75736572', 'QA', 'x', 'student', TRUE, 1, 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

INSERT INTO auth_sessions (id, user_id, token_digest, auth_version, expires_at, created_at)
VALUES ('qa_p5_sess', 'qa_p5_user', UNHEX(SHA2('qa_p5_token', 256)), 1, UTC_TIMESTAMP(6) + INTERVAL 1 HOUR, UTC_TIMESTAMP(6));

INSERT INTO conversation_states (id, user_id, session_id, created_at, updated_at)
VALUES ('qa_p5_conv', 'qa_p5_user', 'qa_p5_sess', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

INSERT INTO courses (id, code, code_norm, name, enabled, version, created_at, updated_at)
VALUES ('qa_p5_course', 'QA101', X'5141313031', 'QA 课程', TRUE, 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

INSERT INTO document_batches (id, uploaded_by, state, expected_files, total_bytes, created_at, updated_at)
VALUES ('qa_p5_batch', 'qa_p5_user', 'accepted', 1, 10, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

INSERT INTO documents (id, batch_id, original_name, file_type, byte_size, visibility, processing_state, created_at, updated_at)
VALUES ('qa_p5_doc', 'qa_p5_batch', 'qa.txt', 'txt', 10, 'unpublished', 'pending', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

INSERT INTO document_versions (id, document_id, version_no, state, parser_config_digest, vector_space, created_at)
VALUES ('qa_p5_ver', 'qa_p5_doc', 1, 'ready', UNHEX(SHA2('cfg', 256)), 'qa_space', UTC_TIMESTAMP(6));

-- @probe 1  ck_users_role：role 必须是 student/admin → 期望 3819
INSERT INTO users (id, account, account_norm, display_name, password_hash, role, enabled, auth_version, version, created_at, updated_at)
VALUES ('qa_p5_bad1', 'qa_teacher', X'71615F74656163686572', 'QA', 'x', 'teacher', TRUE, 1, 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 2  ck_users_names：account 长度 3..64 → 期望 3819
INSERT INTO users (id, account, account_norm, display_name, password_hash, role, enabled, auth_version, version, created_at, updated_at)
VALUES ('qa_p5_bad2', 'ab', X'6162', 'QA', 'x', 'student', TRUE, 1, 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 3  uq_users_account：account_norm 唯一 → 期望 1062
INSERT INTO users (id, account, account_norm, display_name, password_hash, role, enabled, auth_version, version, created_at, updated_at)
VALUES ('qa_p5_bad3', 'qa_p5_user2', X'71615F70355F75736572', 'QA', 'x', 'student', TRUE, 1, 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 4  ck_sessions_expiry：expires_at > created_at → 期望 3819
INSERT INTO auth_sessions (id, user_id, token_digest, auth_version, expires_at, created_at)
VALUES ('qa_p5_bad4', 'qa_p5_user', UNHEX(SHA2('qa_p5_t4', 256)), 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 5  ck_schedule_times：start_time < end_time → 期望 3819
INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, version, created_at, updated_at)
VALUES ('qa_p5_bad5', 'qa_p5_user', 'qa_p5_course', '2026-10-23', '10:00:00', '10:00:00', 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 6  ck_chat_state：state 枚举 → 期望 3819
INSERT INTO chat_requests (id, client_request_id, user_id, session_id, conversation_id, request_digest, state, accepted_at, deadline_at, school_timezone, fence)
VALUES ('qa_p5_bad6', 'qa_p5_c6', 'qa_p5_user', 'qa_p5_sess', 'qa_p5_conv', UNHEX(SHA2('d', 256)), 'done', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6) + INTERVAL 60 SECOND, 'Asia/Shanghai', 1);

-- @probe 7  ck_chat_terminal：终态必须有 finished_at → 期望 3819
INSERT INTO chat_requests (id, client_request_id, user_id, session_id, conversation_id, request_digest, state, accepted_at, deadline_at, finished_at, school_timezone, fence)
VALUES ('qa_p5_bad7', 'qa_p5_c7', 'qa_p5_user', 'qa_p5_sess', 'qa_p5_conv', UNHEX(SHA2('d', 256)), 'succeeded', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6) + INTERVAL 60 SECOND, NULL, 'Asia/Shanghai', 1);

-- @probe 8  uq_document_one_active：同一文档只能有一个 active 版本 → 期望 1062
INSERT INTO document_versions (id, document_id, version_no, state, parser_config_digest, vector_space, created_at)
VALUES ('qa_p5_ver_act1', 'qa_p5_doc', 2, 'active', UNHEX(SHA2('cfg', 256)), 'qa_space', UTC_TIMESTAMP(6));
INSERT INTO document_versions (id, document_id, version_no, state, parser_config_digest, vector_space, created_at)
VALUES ('qa_p5_ver_act2', 'qa_p5_doc', 3, 'active', UNHEX(SHA2('cfg', 256)), 'qa_space', UTC_TIMESTAMP(6));

-- @probe 9  ck_chunk_text：text_content 非空 → 期望 3819
INSERT INTO chunks (id, document_id, version_id, chunk_index, text_content, location_label, content_digest)
VALUES ('qa_p5_bad9', 'qa_p5_doc', 'qa_p5_ver', 1, '', 'p1', UNHEX(SHA2('t', 256)));

-- @probe 10 ck_corpus_singleton：singleton_id 只能为 1 → 期望 3819
INSERT INTO corpus_control (singleton_id, revision, publish_frozen, updated_at)
VALUES (2, 0, TRUE, UTC_TIMESTAMP(6));

-- @probe 11 ck_document_removed：removed 必须有 deleted_at → 期望 3819
INSERT INTO documents (id, batch_id, original_name, file_type, byte_size, visibility, processing_state, created_at, updated_at)
VALUES ('qa_p5_bad11', 'qa_p5_batch', 'qa2.txt', 'txt', 10, 'removed', 'deleted', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @probe 12 fk_chunk_document：document_id 必须存在 → 期望 1452
INSERT INTO chunks (id, document_id, version_id, chunk_index, text_content, location_label, content_digest)
VALUES ('qa_p5_bad12', 'qa_p5_missing_doc', 'qa_p5_ver', 2, 'x', 'p1', UNHEX(SHA2('t', 256)));

-- @control：合法行必须成功（证明探针不是"整库拒写"）
INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, version, created_at, updated_at)
VALUES ('qa_p5_ok', 'qa_p5_user', 'qa_p5_course', '2026-10-23', '08:00:00', '09:00:00', 1, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6));

-- @teardown
DELETE FROM schedules WHERE user_id = 'qa_p5_user';
DELETE FROM chunks WHERE document_id = 'qa_p5_doc';
DELETE FROM document_versions WHERE document_id = 'qa_p5_doc';
DELETE FROM documents WHERE batch_id = 'qa_p5_batch';
DELETE FROM document_batches WHERE id = 'qa_p5_batch';
DELETE FROM chat_requests WHERE user_id = 'qa_p5_user';
DELETE FROM conversation_states WHERE id = 'qa_p5_conv';
DELETE FROM auth_sessions WHERE user_id = 'qa_p5_user';
DELETE FROM courses WHERE id = 'qa_p5_course';
DELETE FROM users WHERE id = 'qa_p5_user';
