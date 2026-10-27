/**
 * ⚠ 生成物（勿手改）—— 不要直接编辑本文件。
 *
 * 生成命令：node scripts/gen-types.mjs
 * 漂移门禁：node scripts/gen-types.mjs --check（不一致即 exit 1）
 * 生成器：openapi-typescript（devDependency，版本见 web/pnpm-lock.yaml）
 * 真源：优先后端运行时 `GET /api/v1/openapi.json`（--source=auto 默认），
 *       不可达时回落 `contracts/openapi_v0.1.json`（同一份契约）。
 *
 * 内网端点：OpenAPI 里的 4 个 `/internal/v1/*` 在生成前被**剔除**（§15.2 前端不得调用），
 * 因此前端类型面天然不含这些端点，不变量 8「不引用 /internal/v1」保持零豁免。
 *
 * 注释归一：生成前剥离 description/summary/title/example 等**非结构性注解**，
 * 只保留字段/类型/必填/枚举/格式。这样「设计包」与「运行态」只要**结构契约一致**
 * 就产出逐字节相同的文件，--check 在后端在线/离线两种情况下都稳定可复现。
 *
 * 业务代码请从 `@/api/types`（手写薄门面）取类型：
 * 门面里的每个类型都直接指向本文件的 `components['schemas'][...]`，
 * 因此契约字段漂移会在 `vue-tsc` 阶段变成编译错误。
 */

export interface paths {
    "/api/v1/admin/courses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listCourses"];
        put?: never;
        post: operations["createCourse"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/courses/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch: operations["patchCourse"];
        trace?: never;
    };
    "/api/v1/admin/document-batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["uploadBatch"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/document-batches/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getBatch"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listDocuments"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/documents/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete: operations["deleteDocument"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/documents/{id}/cleanup-retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["retryCleanup"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/documents/{id}/rebuild": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["rebuildDocument"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/documents/{id}/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["previewDocument"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/schedules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["adminSchedules"];
        put?: never;
        post: operations["createSchedule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/schedules/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete: operations["deleteSchedule"];
        options?: never;
        head?: never;
        patch: operations["patchSchedule"];
        trace?: never;
    };
    "/api/v1/admin/stats/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getStatsOverview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/students": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listStudents"];
        put?: never;
        post: operations["createStudent"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/students/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch: operations["patchStudent"];
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["register"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/requests/{request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getChatState"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/requests/{request_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["cancelChat"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["streamChat"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/citations/{reference_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getCitation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getMe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/drafts/{draft_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getDraft"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch: operations["reviseDraft"];
        trace?: never;
    };
    "/api/v1/me/drafts/{draft_id}/save": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["saveDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listPlans"];
        put?: never;
        post: operations["createPlan"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/plans/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getPlan"];
        put?: never;
        post?: never;
        delete: operations["deletePlan"];
        options?: never;
        head?: never;
        patch: operations["patchPlan"];
        trace?: never;
    };
    "/api/v1/me/schedules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["mySchedules"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/write-operations/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getWriteOperation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Batch: {
            batch_id: string;
            documents: components["schemas"]["Document"][];
            error_code?: string;
            published: boolean;
            /** @enum {string} */
            state: "accepted" | "processing" | "published" | "compensating" | "failed";
            tasks: components["schemas"]["Task"][];
        };
        Cancel: {
            accepted: boolean;
            request: components["schemas"]["ChatState"];
        };
        ChatInput: {
            client_request_id: string;
            conversation_id?: string;
            history?: components["schemas"]["HistoryMessage"][];
            message: string;
        };
        ChatState: {
            /** Format: date-time */
            accepted_at: string;
            cancel_requested: boolean;
            conversation_id: string;
            finished_at: string | null;
            model_calls: number;
            operation_id?: string;
            plan_id?: string;
            request_id: string;
            /** @enum {string} */
            state: "accepted" | "running" | "succeeded" | "failed" | "cancelled";
            terminal_reason?: string;
            tool_calls: number;
        };
        Citation: {
            reference: components["schemas"]["Reference"];
            text: string;
        };
        Course: {
            code: string;
            description: string | null;
            enabled: boolean;
            id: string;
            name: string;
            version: number;
        };
        CourseCreate: {
            code: string;
            description?: string | null;
            enabled?: boolean;
            name: string;
        };
        CoursePage: {
            items: components["schemas"]["Course"][];
            page: number;
            page_size: number;
            total: number;
        };
        CoursePatch: {
            description?: string | null;
            enabled?: boolean;
            expected_version: number;
            name?: string;
        } | unknown | unknown | unknown;
        DelegationExchangeInput: {
            delegation: string;
        };
        DelegationExchangeOutput: {
            /** @constant */
            audience: "cca-internal";
            delegation: string;
            /** Format: date-time */
            expires_at: string;
        };
        Document: {
            batch_id: string;
            byte_size: number;
            /** @enum {string} */
            cleanup_state: "not_required" | "pending" | "running" | "succeeded" | "failed";
            error_code?: string;
            /** @enum {string} */
            file_type: "txt" | "md" | "pdf" | "docx";
            id: string;
            original_name: string;
            /** @enum {string} */
            processing_state: "processing" | "available" | "failed" | "rebuilding" | "deleting" | "delete_failed" | "deleted";
            /** Format: date-time */
            uploaded_at: string;
            version: number;
            /** @enum {string} */
            visibility: "unpublished" | "shared" | "removed";
        };
        DocumentMutation: {
            document_id: string;
            task: components["schemas"]["Task"];
            version: number;
            /** @enum {string} */
            visibility: "unpublished" | "shared" | "removed";
        };
        DocumentPage: {
            items: components["schemas"]["Document"][];
            page: number;
            page_size: number;
            total: number;
        };
        DocumentText: {
            document_id: string;
            next_offset: number | null;
            offset: number;
            /** @enum {string} */
            state: "available" | "processing" | "parse_failed";
            text: string;
            version_id: string;
        };
        Draft: {
            basis_types: ("schedule" | "documents" | "general")[];
            content: string;
            draft_id: string;
            draft_version: number;
            end_date?: string | null;
            /** Format: date-time */
            expires_at: string;
            goal?: string | null;
            operation_id: string;
            references: components["schemas"]["Reference"][];
            start_date?: string | null;
            title: string;
        };
        DraftPatch: {
            content?: string;
            end_date?: string | null;
            expected_draft_version: number;
            goal?: string | null;
            start_date?: string | null;
            title?: string;
        } | unknown | unknown | unknown | unknown | unknown;
        DraftSave: {
            draft_version: number;
        };
        EmptyInput: Record<string, never>;
        Error: {
            error: {
                /** @enum {string} */
                code: "AUTH_REQUIRED" | "SESSION_EXPIRED" | "FORBIDDEN" | "RESOURCE_NOT_FOUND" | "DUPLICATE_ACCOUNT" | "DUPLICATE_COURSE" | "DUPLICATE_SCHEDULE" | "VERSION_CONFLICT" | "SCHEDULE_OVERLAP" | "CHAT_IN_PROGRESS" | "REQUEST_ALREADY_EXISTS" | "IDEMPOTENCY_CONFLICT" | "SAVE_LIMIT_REACHED" | "DOCUMENT_BUSY" | "DUPLICATE_FILENAME" | "DRAFT_EXPIRED" | "CITATION_UNAVAILABLE" | "UPLOAD_TOO_LARGE" | "UNSUPPORTED_FILE_TYPE" | "VALIDATION_FAILED" | "SAVE_NOT_AUTHORIZED" | "CAPACITY_LIMITED" | "MODEL_UNAVAILABLE" | "RETRIEVAL_UNAVAILABLE" | "MCP_UNAVAILABLE" | "STORAGE_UNAVAILABLE" | "EXECUTION_TIMEOUT" | "CALL_LIMIT_REACHED" | "INTERNAL_ERROR";
                details?: components["schemas"]["ErrorDetails"];
                field_errors?: components["schemas"]["FieldError"][];
                message: string;
            };
            request_id: string;
        };
        ErrorDetails: {
            existing_request_id?: string;
            operation_id?: string;
            overlaps?: components["schemas"]["Schedule"][];
            plan_id?: string;
            retryable?: boolean;
            /** @enum {string} */
            state?: "pending" | "succeeded" | "failed" | "deleted";
        };
        EvidenceChunk: {
            chunk_id: string;
            document_id: string;
            location_label: string;
            page_number?: number;
            reference_id: string;
            text: string;
            version_id: string;
        };
        FieldError: {
            field: string;
            reason: string;
        };
        HistoryMessage: {
            content: string;
            /** @enum {string} */
            role: "user" | "assistant";
        };
        Login: {
            access_token: string;
            /** Format: date-time */
            expires_at: string;
            /** @constant */
            token_type: "Bearer";
            user: components["schemas"]["User"];
        };
        LoginInput: {
            account: string;
            password: string;
        };
        Logout: {
            /** @constant */
            revoked: true;
        };
        Me: {
            capabilities: string[];
            school_timezone: string;
            /** Format: date-time */
            session_expires_at: string;
            user: components["schemas"]["User"];
        };
        Plan: {
            basis_types: ("schedule" | "documents" | "general")[];
            content: string;
            /** Format: date-time */
            created_at: string;
            end_date?: string | null;
            goal?: string | null;
            id: string;
            references: components["schemas"]["Reference"][];
            /** @enum {string} */
            source: "manual" | "assistant";
            start_date?: string | null;
            title: string;
            /** Format: date-time */
            updated_at: string;
            version: number;
        };
        PlanCreate: {
            content: string;
            end_date?: string | null;
            goal?: string | null;
            start_date?: string | null;
            title: string;
        };
        PlanDelete: {
            /** @constant */
            deleted: true;
            plan_id: string;
            version: number;
        };
        PlanPage: {
            items: components["schemas"]["Plan"][];
            page: number;
            page_size: number;
            total: number;
        };
        PlanPatch: {
            content?: string;
            end_date?: string | null;
            expected_version: number;
            goal?: string | null;
            start_date?: string | null;
            title?: string;
        } | unknown | unknown | unknown | unknown | unknown;
        Rebuild: {
            expected_version: number;
        };
        Reference: {
            document_id: string;
            file_name: string;
            location_label: string;
            page_number?: number;
            reference_id: string;
            version_id: string;
        };
        RegisterInput: {
            account: string;
            display_name: string;
            password: string;
        };
        SaveCreatedResult: {
            operation_id: string;
            plan_id: string;
            /** @enum {string} */
            status: "created";
        };
        SaveResult: {
            operation_id: string;
            plan_id: string;
            /** @enum {string} */
            status: "created" | "existing" | "deleted";
        };
        SaveReusedResult: {
            operation_id: string;
            plan_id: string;
            /** @enum {string} */
            status: "existing" | "deleted";
        };
        SaveToolInput: {
            draft_id: string;
            draft_version: number;
        };
        SaveToolOutput: {
            operation_id: string;
            plan_id: string;
            /** @enum {string} */
            status: "created" | "existing" | "deleted";
        };
        Schedule: {
            /** Format: date */
            class_date: string;
            course_id: string;
            course_name: string;
            end_time: string;
            id: string;
            location: string | null;
            start_time: string;
            student_id: string;
            version: number;
        };
        ScheduleCreate: {
            /** Format: date */
            class_date: string;
            course_id: string;
            end_time: string;
            location?: string | null;
            overlap_acknowledged?: boolean;
            reason?: string;
            start_time: string;
            student_id: string;
        };
        ScheduleDelete: {
            audit_id: string;
            /** @constant */
            deleted: true;
            schedule_id: string;
        };
        SchedulePage: {
            /** Format: date */
            from_date: string;
            items: components["schemas"]["Schedule"][];
            page: number;
            page_size: number;
            school_timezone: string;
            /** Format: date */
            to_date: string;
            total: number;
        };
        SchedulePatch: {
            /** Format: date */
            class_date?: string;
            course_id?: string;
            end_time?: string;
            expected_version: number;
            location?: string | null;
            overlap_acknowledged?: boolean;
            reason?: string;
            start_time?: string;
        } | unknown | unknown | unknown | unknown | unknown;
        ScheduleToolInput: {
            /** Format: date */
            from_date?: string;
            /** Format: date */
            to_date?: string;
        };
        ScheduleToolOutput: {
            /** Format: date */
            from_date: string;
            items: components["schemas"]["Schedule"][];
            school_timezone: string;
            /** @enum {string} */
            status: "ok" | "empty";
            /** Format: date */
            to_date: string;
        } & unknown;
        SearchToolInput: {
            query: string;
        };
        SearchToolOutput: {
            chunks: components["schemas"]["EvidenceChunk"][];
            corpus_empty: boolean;
            references: components["schemas"]["Reference"][];
            revision: number;
            /** @enum {string} */
            status: "ok" | "empty";
        } & unknown;
        StatsCleanup: {
            failed: number;
            slow: number;
            succeeded: number;
        };
        StatsOperations: {
            batches_failed: number;
            batches_published: number;
            citations_expanded: number;
            drafts_formed: number;
            idempotent_hits: number;
            plans_created: number;
            plans_deleted: number;
            plans_retryable_failed: number;
            tool_calls: number;
            tool_failures: number;
            writes_recovered: number;
        };
        StatsOverview: {
            cleanup: components["schemas"]["StatsCleanup"];
            operations: components["schemas"]["StatsOperations"];
            requests: components["schemas"]["StatsRequests"];
            tasks: components["schemas"]["StatsTasks"];
            window: components["schemas"]["StatsWindow"];
        };
        StatsRequests: {
            auth_expired: number;
            cancelled: number;
            empty: number;
            failed: number;
            limit_reached: number;
            pending: number;
            succeeded: number;
            succeeded_with_evidence: number;
            timeout: number;
            total: number;
        };
        StatsTasks: {
            failed: number;
            pending: number;
            retry_wait: number;
            running: number;
        };
        StatsWindow: {
            /** Format: date */
            from_date: string;
            school_timezone: string;
            /** Format: date */
            to_date: string;
        };
        StudentCreate: {
            account: string;
            display_name: string;
            initial_password: string;
        };
        StudentPage: {
            items: components["schemas"]["User"][];
            page: number;
            page_size: number;
            total: number;
        };
        StudentPatch: {
            display_name?: string;
            enabled?: boolean;
            expected_version: number;
        } | unknown | unknown;
        Task: {
            error_code?: string;
            retryable: boolean;
            /** @enum {string} */
            state: "pending" | "running" | "retry_wait" | "succeeded" | "failed";
            task_id: string;
        };
        Upload: {
            allow_duplicate_names?: boolean;
            files: string[];
        };
        User: {
            account: string;
            display_name: string;
            enabled: boolean;
            id: string;
            /** @enum {string} */
            role: "student" | "admin";
            version: number;
        };
        WriteOperation: {
            error_code?: string;
            operation_id: string;
            plan_id?: string;
            /** @enum {string} */
            resolution: "confirmed" | "recovering";
            retryable: boolean;
            /** @enum {string} */
            state: "pending" | "succeeded" | "failed" | "deleted";
        } & (unknown & unknown);
    };
    responses: {
        ErrorResponse: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        ExpectedVersion: number;
        FromDate: string;
        IdempotencyKey: string;
        Page: number;
        PageSize: number;
        ToDate: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listCourses: {
        parameters: {
            query?: {
                enabled?: boolean;
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                query?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["CoursePage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    createCourse: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CourseCreate"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Course"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    patchCourse: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CoursePatch"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Course"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    uploadBatch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Upload"];
            };
        };
        responses: {
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Batch"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getBatch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Batch"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    listDocuments: {
        parameters: {
            query?: {
                name?: string;
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                state?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["DocumentPage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    deleteDocument: {
        parameters: {
            query: {
                expected_version: components["parameters"]["ExpectedVersion"];
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["DocumentMutation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    retryCleanup: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["DocumentMutation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    rebuildDocument: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
            };
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Rebuild"];
            };
        };
        responses: {
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["DocumentMutation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    previewDocument: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["DocumentText"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    adminSchedules: {
        parameters: {
            query: {
                from_date?: components["parameters"]["FromDate"];
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                student_id: string;
                to_date?: components["parameters"]["ToDate"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SchedulePage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    createSchedule: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleCreate"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Schedule"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    deleteSchedule: {
        parameters: {
            query: {
                expected_version: components["parameters"]["ExpectedVersion"];
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["ScheduleDelete"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    patchSchedule: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SchedulePatch"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Schedule"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getStatsOverview: {
        parameters: {
            query?: {
                from_date?: string | null;
                to_date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["StatsOverview"];
                        request_id: string;
                    };
                };
            };
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            504: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    listStudents: {
        parameters: {
            query?: {
                enabled?: boolean;
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                query?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["StudentPage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    createStudent: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StudentCreate"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["User"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    patchStudent: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StudentPatch"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["User"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    login: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginInput"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Login"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    logout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Logout"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    register: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterInput"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Login"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getChatState: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["ChatState"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    cancelChat: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                request_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Cancel"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    streamChat: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatInput"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getCitation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                reference_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Citation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getMe: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Me"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Draft"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    reviseDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftPatch"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Draft"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    saveDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
            };
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftSave"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SaveReusedResult"];
                        request_id: string;
                    };
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SaveCreatedResult"];
                        request_id: string;
                    };
                };
            };
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["WriteOperation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    listPlans: {
        parameters: {
            query?: {
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                title?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["PlanPage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    createPlan: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanCreate"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SaveReusedResult"];
                        request_id: string;
                    };
                };
            };
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SaveCreatedResult"];
                        request_id: string;
                    };
                };
            };
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["WriteOperation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getPlan: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Plan"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    deletePlan: {
        parameters: {
            query: {
                expected_version: components["parameters"]["ExpectedVersion"];
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["PlanDelete"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    patchPlan: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanPatch"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Plan"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    mySchedules: {
        parameters: {
            query?: {
                from_date?: components["parameters"]["FromDate"];
                page?: components["parameters"]["Page"];
                page_size?: components["parameters"]["PageSize"];
                to_date?: components["parameters"]["ToDate"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["SchedulePage"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
    getWriteOperation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["WriteOperation"];
                        request_id: string;
                    };
                };
            };
            400: components["responses"]["ErrorResponse"];
            401: components["responses"]["ErrorResponse"];
            403: components["responses"]["ErrorResponse"];
            404: components["responses"]["ErrorResponse"];
            409: components["responses"]["ErrorResponse"];
            410: components["responses"]["ErrorResponse"];
            413: components["responses"]["ErrorResponse"];
            415: components["responses"]["ErrorResponse"];
            422: components["responses"]["ErrorResponse"];
            429: components["responses"]["ErrorResponse"];
            500: components["responses"]["ErrorResponse"];
            503: components["responses"]["ErrorResponse"];
            504: components["responses"]["ErrorResponse"];
        };
    };
}
