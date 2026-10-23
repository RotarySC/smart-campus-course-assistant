# 前端字段参考（自动生成，只读）

> 由 `docs/frontend-detail/gen-api-reference.py` 从 `docs/backend/openapi_v0.1.json` 生成，**请勿手改**。
> 用途：并行写作时**字段名的唯一来源**。文档里出现的每个端点与字段都必须能在这里查到。

## 0. 通用约定

- **所有响应都带信封**：`{ request_id, data }`。`request_id` 在前端用于 `NFR-OBS-001` 的贯通关联。
- **`request_id` 也可能出现在响应头**，前端取 body 的为准；SSE 事件的 `request_id` 见 SSE schema。
- `/api/v1/*` 共 26 个，前端可用；`/internal/v1/*` 共 4 个，**前端不得调用**。

### 同步错误码（前端允许集合，29 个）

来源：`openapi_v0.1.json` 的 `Error` 枚举（28 个）∪ `SRS §8`（1 个）

```
AUTH_REQUIRED、CALL_LIMIT_REACHED、CAPACITY_LIMITED、CHAT_IN_PROGRESS、CITATION_UNAVAILABLE、DOCUMENT_BUSY、DRAFT_EXPIRED、DUPLICATE_ACCOUNT、DUPLICATE_COURSE、DUPLICATE_FILENAME、DUPLICATE_SCHEDULE、EXECUTION_TIMEOUT、FORBIDDEN、IDEMPOTENCY_CONFLICT、INTERNAL_ERROR、MCP_UNAVAILABLE、MODEL_UNAVAILABLE、REQUEST_ALREADY_EXISTS、RESOURCE_NOT_FOUND、RETRIEVAL_UNAVAILABLE、SAVE_LIMIT_REACHED、SAVE_NOT_AUTHORIZED、SCHEDULE_OVERLAP、SESSION_EXPIRED、STORAGE_UNAVAILABLE、UNSUPPORTED_FILE_TYPE、UPLOAD_TOO_LARGE、VALIDATION_FAILED、VERSION_CONFLICT
```

> **上游不一致（已登记，未抹平）**：`SRS §8` 列出了 `FORBIDDEN`，但 `openapi_v0.1.json` 的 `Error` 枚举里**没有**。
> 前端以 `SRS §8` 为准（它承载了「客户端行为」这一列，是前端要实现的语义），因此允许集合是两者并集。这一点需要后端确认是 OpenAPI 漏写还是 SRS 多写；**在确认前，前端按并集实现并保留该码的处理分支**。

### 异步任务码（SRS §8，6 个，出现在文档批次/文件状态里，不是 HTTP 错误）

```
NO_TEXT_EXTRACTED、DOCUMENT_ENCRYPTED、PARSE_FAILED、EMBEDDING_FAILED、CLEANUP_FAILED、SERVICE_RESTARTED
```

## 1. 端点逐条

### `GET /api/v1/admin/courses`

listCourses

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `query` | string | 否 |
| query | `enabled` | boolean | 否 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/courses`

createCourse

**请求体**（`application/json`）

```
code string
name string
description ?
enabled boolean
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 201 | `id`: string<br>`code`: string<br>`name`: string<br>`description`: ?<br>`enabled`: boolean<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `PATCH /api/v1/admin/courses/{id}`

patchCourse

**请求体**（`application/json`）

```
name string
description ?
enabled boolean
expected_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `id`: string<br>`code`: string<br>`name`: string<br>`description`: ?<br>`enabled`: boolean<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/document-batches`

uploadBatch

**请求体**（`multipart/form-data`）（multipart 上传）

```
files array<string>
allow_duplicate_names boolean
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 202 | `batch_id`: string<br>`state`: enum(accepted|processing|published|compensating|failed)<br>`published`: boolean<br>`documents`: array<object><br>`tasks`: array<object><br>`error_code`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/admin/document-batches/{id}`

getBatch

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `batch_id`: string<br>`state`: enum(accepted|processing|published|compensating|failed)<br>`published`: boolean<br>`documents`: array<object><br>`tasks`: array<object><br>`error_code`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/admin/documents`

listDocuments

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `name` | string | 否 |
| query | `state` | string | 否 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `DELETE /api/v1/admin/documents/{id}`

deleteDocument

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `expected_version` | integer | 是 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 202 | `document_id`: string<br>`visibility`: enum(unpublished|shared|removed)<br>`task`: object<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/documents/{id}/cleanup-retry`

retryCleanup

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| header | `Idempotency-Key` | string | 是 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 202 | `document_id`: string<br>`visibility`: enum(unpublished|shared|removed)<br>`task`: object<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/documents/{id}/rebuild`

rebuildDocument

**请求体**（`application/json`）

```
expected_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| header | `Idempotency-Key` | string | 是 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 202 | `document_id`: string<br>`visibility`: enum(unpublished|shared|removed)<br>`task`: object<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/admin/documents/{id}/text`

previewDocument

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `offset` | integer | 否 |
| query | `limit` | integer | 否 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `document_id`: string<br>`version_id`: string<br>`offset`: integer<br>`next_offset`: ?<br>`text`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/admin/schedules`

adminSchedules

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `from_date` | string | 否 |
| query | `to_date` | string | 否 |
| query | `student_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer<br>`from_date`: string<br>`to_date`: string<br>`school_timezone`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/schedules`

createSchedule

**请求体**（`application/json`）

```
student_id string
course_id string
class_date string
start_time string
end_time string
location ?
overlap_acknowledged boolean
reason string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 201 | `id`: string<br>`student_id`: string<br>`course_id`: string<br>`course_name`: string<br>`class_date`: string<br>`start_time`: string<br>`end_time`: string<br>`location`: ?<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `PATCH /api/v1/admin/schedules/{id}`

patchSchedule

**请求体**（`application/json`）

```
course_id string
class_date string
start_time string
end_time string
location ?
overlap_acknowledged boolean
reason string
expected_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `id`: string<br>`student_id`: string<br>`course_id`: string<br>`course_name`: string<br>`class_date`: string<br>`start_time`: string<br>`end_time`: string<br>`location`: ?<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `DELETE /api/v1/admin/schedules/{id}`

deleteSchedule

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `expected_version` | integer | 是 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `deleted`: ?<br>`schedule_id`: string<br>`audit_id`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/admin/students`

listStudents

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `query` | string | 否 |
| query | `enabled` | boolean | 否 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/admin/students`

createStudent

**请求体**（`application/json`）

```
account string
display_name string
initial_password string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 201 | `id`: string<br>`account`: string<br>`display_name`: string<br>`role`: enum(student|admin)<br>`enabled`: boolean<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `PATCH /api/v1/admin/students/{id}`

patchStudent

**请求体**（`application/json`）

```
display_name string
enabled boolean
expected_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `id`: string<br>`account`: string<br>`display_name`: string<br>`role`: enum(student|admin)<br>`enabled`: boolean<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/auth/login`

login

**请求体**（`application/json`）

```
account string
password string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `access_token`: string<br>`token_type`: ?<br>`expires_at`: string<br>`user`: object |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/auth/logout`

logout


**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `revoked`: ? |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/chat/requests/{request_id}`

getChatState

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `request_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `request_id`: string<br>`conversation_id`: string<br>`state`: enum(accepted|running|succeeded|failed|cancelled)<br>`cancel_requested`: boolean<br>`accepted_at`: string<br>`finished_at`: ?<br>`terminal_reason`: string<br>`model_calls`: integer<br>`tool_calls`: integer<br>`plan_id`: string<br>`operation_id`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/chat/requests/{request_id}/cancel`

cancelChat

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `request_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `accepted`: boolean<br>`request`: object |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/chat/stream`

streamChat

**请求体**（`application/json`）

```
client_request_id string
conversation_id string
message string
history array<object>
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | SSE；六类事件data见sse_events_v0.1.schema.json；终态及引用在写出边界核实。 |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |

> 响应为 `text/event-stream`：解析口径见 `docs/backend/sse_events_v0.1.schema.json`。
### `GET /api/v1/citations/{reference_id}`

getCitation

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `reference_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `reference`: object<br>`text`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me`

getMe


**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `user`: object<br>`session_expires_at`: string<br>`school_timezone`: string<br>`capabilities`: array<string> |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me/drafts/{draft_id}`

getDraft

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `draft_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `draft_id`: string<br>`draft_version`: integer<br>`operation_id`: string<br>`title`: string<br>`goal`: ?<br>`start_date`: ?<br>`end_date`: ?<br>`content`: string<br>`basis_types`: array<enum(schedule|documents|general)><br>`references`: array<object><br>`expires_at`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `PATCH /api/v1/me/drafts/{draft_id}`

reviseDraft

**请求体**（`application/json`）

```
title string
goal ?
start_date ?
end_date ?
content string
expected_draft_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `draft_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `draft_id`: string<br>`draft_version`: integer<br>`operation_id`: string<br>`title`: string<br>`goal`: ?<br>`start_date`: ?<br>`end_date`: ?<br>`content`: string<br>`basis_types`: array<enum(schedule|documents|general)><br>`references`: array<object><br>`expires_at`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/me/drafts/{draft_id}/save`

saveDraft

**请求体**（`application/json`）

```
draft_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| header | `Idempotency-Key` | string | 是 |
| path | `draft_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `status`: enum(existing|deleted)<br>`operation_id`: string<br>`plan_id`: string |
| 201 | `status`: enum(created)<br>`operation_id`: string<br>`plan_id`: string |
| 202 | `operation_id`: string<br>`state`: enum(pending|succeeded|failed|deleted)<br>`resolution`: enum(confirmed|recovering)<br>`plan_id`: string<br>`error_code`: string<br>`retryable`: boolean |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me/plans`

listPlans

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `title` | string | 否 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /api/v1/me/plans`

createPlan

**请求体**（`application/json`）

```
title string
goal ?
start_date ?
end_date ?
content string
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| header | `Idempotency-Key` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `status`: enum(existing|deleted)<br>`operation_id`: string<br>`plan_id`: string |
| 201 | `status`: enum(created)<br>`operation_id`: string<br>`plan_id`: string |
| 202 | `operation_id`: string<br>`state`: enum(pending|succeeded|failed|deleted)<br>`resolution`: enum(confirmed|recovering)<br>`plan_id`: string<br>`error_code`: string<br>`retryable`: boolean |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me/plans/{id}`

getPlan

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `id`: string<br>`title`: string<br>`goal`: ?<br>`start_date`: ?<br>`end_date`: ?<br>`content`: string<br>`source`: enum(manual|assistant)<br>`basis_types`: array<enum(schedule|documents|general)><br>`references`: array<object><br>`version`: integer<br>`created_at`: string<br>`updated_at`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `PATCH /api/v1/me/plans/{id}`

patchPlan

**请求体**（`application/json`）

```
title string
goal ?
start_date ?
end_date ?
content string
expected_version integer
```
**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `id`: string<br>`title`: string<br>`goal`: ?<br>`start_date`: ?<br>`end_date`: ?<br>`content`: string<br>`source`: enum(manual|assistant)<br>`basis_types`: array<enum(schedule|documents|general)><br>`references`: array<object><br>`version`: integer<br>`created_at`: string<br>`updated_at`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `DELETE /api/v1/me/plans/{id}`

deletePlan

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `expected_version` | integer | 是 |
| path | `id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `deleted`: ?<br>`plan_id`: string<br>`version`: integer |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me/schedules`

mySchedules

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| query | `page` | integer | 否 |
| query | `page_size` | integer | 否 |
| query | `from_date` | string | 否 |
| query | `to_date` | string | 否 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `items`: array<object><br>`page`: integer<br>`page_size`: integer<br>`total`: integer<br>`from_date`: string<br>`to_date`: string<br>`school_timezone`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `GET /api/v1/me/write-operations/{operation_id}`

getWriteOperation

**参数/头**

| 位置 | 名 | 类型 | 必填 |
| --- | --- | --- | --- |
| path | `operation_id` | string | 是 |

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `operation_id`: string<br>`state`: enum(pending|succeeded|failed|deleted)<br>`resolution`: enum(confirmed|recovering)<br>`plan_id`: string<br>`error_code`: string<br>`retryable`: boolean |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /internal/v1/delegations/exchange`

exchangeDelegation

> **内部接口：前端不得调用。**

**请求体**（`application/json`）

```
delegation string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `delegation`: string<br>`audience`: ?<br>`expires_at`: string |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /internal/v1/tools/get-my-schedule`

internalSchedule

> **内部接口：前端不得调用。**

**请求体**（`application/json`）

```
from_date string
to_date string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `status`: enum(ok|empty)<br>`from_date`: string<br>`to_date`: string<br>`school_timezone`: string<br>`items`: array<object> |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /internal/v1/tools/save-study-plan`

internalSave

> **内部接口：前端不得调用。**

**请求体**（`application/json`）

```
draft_id string
draft_version integer
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `status`: enum(created|existing)<br>`operation_id`: string<br>`plan_id`: string |
| 202 | `operation_id`: string<br>`state`: enum(pending|succeeded|failed|deleted)<br>`resolution`: enum(confirmed|recovering)<br>`plan_id`: string<br>`error_code`: string<br>`retryable`: boolean |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |
### `POST /internal/v1/tools/search-course-docs`

internalSearch

> **内部接口：前端不得调用。**

**请求体**（`application/json`）

```
query string
```

**响应**

| 码 | `data` 字段 |
| --- | --- |
| 200 | `status`: enum(ok|empty)<br>`corpus_empty`: boolean<br>`revision`: integer<br>`chunks`: array<object><br>`references`: array<object> |
| 400 | — |
| 401 | — |
| 403 | — |
| 404 | — |
| 409 | — |
| 410 | — |
| 413 | — |
| 415 | — |
| 422 | — |
| 429 | — |
| 500 | — |
| 503 | — |
| 504 | — |

## 2. 组件 schema 附录（嵌套对象的字段在这里查）

端点的响应 `data` 只展开顶层；`object` 字样表示嵌套，其字段在本节查。
枚举取值全部列出，必填字段标 `*`。

### `Batch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `batch_id` | string | 是 |
| `state` | enum(accepted|processing|published|compensating|failed) | 是 |
| `published` | boolean | 是 |
| `documents` | array<object> | 是 |
| `tasks` | array<object> | 是 |
| `error_code` | string |  |

### `Cancel`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `accepted` | boolean | 是 |
| `request` | object | 是 |

### `ChatInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `client_request_id` | string | 是 |
| `conversation_id` | string |  |
| `message` | string | 是 |
| `history` | array<object> |  |

### `ChatState`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `request_id` | string | 是 |
| `conversation_id` | string | 是 |
| `state` | enum(accepted|running|succeeded|failed|cancelled) | 是 |
| `cancel_requested` | boolean | 是 |
| `accepted_at` | string | 是 |
| `finished_at` | ? | 是 |
| `terminal_reason` | string |  |
| `model_calls` | integer | 是 |
| `tool_calls` | integer | 是 |
| `plan_id` | string |  |
| `operation_id` | string |  |

### `Citation`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `reference` | object | 是 |
| `text` | string | 是 |

### `Course`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `id` | string | 是 |
| `code` | string | 是 |
| `name` | string | 是 |
| `description` | ? | 是 |
| `enabled` | boolean | 是 |
| `version` | integer | 是 |

### `CourseCreate`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `code` | string | 是 |
| `name` | string | 是 |
| `description` | ? |  |
| `enabled` | boolean |  |

### `CoursePage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `items` | array<object> | 是 |
| `page` | integer | 是 |
| `page_size` | integer | 是 |
| `total` | integer | 是 |

### `CoursePatch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `name` | string |  |
| `description` | ? |  |
| `enabled` | boolean |  |
| `expected_version` | integer | 是 |

### `DelegationExchangeInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `delegation` | string | 是 |

### `DelegationExchangeOutput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `delegation` | string | 是 |
| `audience` | ? | 是 |
| `expires_at` | string | 是 |

### `Document`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `id` | string | 是 |
| `batch_id` | string | 是 |
| `original_name` | string | 是 |
| `file_type` | enum(txt|md|pdf|docx) | 是 |
| `byte_size` | integer | 是 |
| `visibility` | enum(unpublished|shared|removed) | 是 |
| `processing_state` | enum(processing|available|failed|rebuilding|deleting|delete_failed|deleted) | 是 |
| `version` | integer | 是 |
| `uploaded_at` | string | 是 |
| `error_code` | string |  |
| `cleanup_state` | enum(not_required|pending|running|succeeded|failed) | 是 |

### `DocumentMutation`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `document_id` | string | 是 |
| `visibility` | enum(unpublished|shared|removed) | 是 |
| `task` | object | 是 |
| `version` | integer | 是 |

### `DocumentPage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `items` | array<object> | 是 |
| `page` | integer | 是 |
| `page_size` | integer | 是 |
| `total` | integer | 是 |

### `DocumentText`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `document_id` | string | 是 |
| `version_id` | string | 是 |
| `offset` | integer | 是 |
| `next_offset` | ? | 是 |
| `text` | string | 是 |

### `Draft`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `draft_id` | string | 是 |
| `draft_version` | integer | 是 |
| `operation_id` | string | 是 |
| `title` | string | 是 |
| `goal` | ? |  |
| `start_date` | ? |  |
| `end_date` | ? |  |
| `content` | string | 是 |
| `basis_types` | array<enum(schedule|documents|general)> | 是 |
| `references` | array<object> | 是 |
| `expires_at` | string | 是 |

### `DraftPatch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `title` | string |  |
| `goal` | ? |  |
| `start_date` | ? |  |
| `end_date` | ? |  |
| `content` | string |  |
| `expected_draft_version` | integer | 是 |

### `DraftSave`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `draft_version` | integer | 是 |

### `EmptyInput`

（无字段，或为 `oneOf`/`allOf` 组合，见 OpenAPI 原文）

### `Error`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `request_id` | string | 是 |
| `error` | object | 是 |

### `ErrorDetails`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `existing_request_id` | string |  |
| `operation_id` | string |  |
| `plan_id` | string |  |
| `state` | enum(pending|succeeded|failed|deleted) |  |
| `overlaps` | array<object> |  |
| `retryable` | boolean |  |

### `EvidenceChunk`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `chunk_id` | string | 是 |
| `reference_id` | string | 是 |
| `document_id` | string | 是 |
| `version_id` | string | 是 |
| `text` | string | 是 |
| `location_label` | string | 是 |
| `page_number` | integer |  |

### `FieldError`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `field` | string | 是 |
| `reason` | string | 是 |

### `HistoryMessage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `role` | enum(user|assistant) | 是 |
| `content` | string | 是 |

### `Login`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `access_token` | string | 是 |
| `token_type` | ? | 是 |
| `expires_at` | string | 是 |
| `user` | object | 是 |

### `LoginInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `account` | string | 是 |
| `password` | string | 是 |

### `Logout`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `revoked` | ? | 是 |

### `Me`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `user` | object | 是 |
| `session_expires_at` | string | 是 |
| `school_timezone` | string | 是 |
| `capabilities` | array<string> | 是 |

### `Plan`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `id` | string | 是 |
| `title` | string | 是 |
| `goal` | ? |  |
| `start_date` | ? |  |
| `end_date` | ? |  |
| `content` | string | 是 |
| `source` | enum(manual|assistant) | 是 |
| `basis_types` | array<enum(schedule|documents|general)> | 是 |
| `references` | array<object> | 是 |
| `version` | integer | 是 |
| `created_at` | string | 是 |
| `updated_at` | string | 是 |

### `PlanCreate`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `title` | string | 是 |
| `goal` | ? |  |
| `start_date` | ? |  |
| `end_date` | ? |  |
| `content` | string | 是 |

### `PlanDelete`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `deleted` | ? | 是 |
| `plan_id` | string | 是 |
| `version` | integer | 是 |

### `PlanPage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `items` | array<object> | 是 |
| `page` | integer | 是 |
| `page_size` | integer | 是 |
| `total` | integer | 是 |

### `PlanPatch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `title` | string |  |
| `goal` | ? |  |
| `start_date` | ? |  |
| `end_date` | ? |  |
| `content` | string |  |
| `expected_version` | integer | 是 |

### `Rebuild`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `expected_version` | integer | 是 |

### `Reference`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `reference_id` | string | 是 |
| `document_id` | string | 是 |
| `version_id` | string | 是 |
| `file_name` | string | 是 |
| `location_label` | string | 是 |
| `page_number` | integer |  |

### `SaveCreatedResult`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(created) | 是 |
| `operation_id` | string | 是 |
| `plan_id` | string | 是 |

### `SaveResult`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(created|existing|deleted) | 是 |
| `operation_id` | string | 是 |
| `plan_id` | string | 是 |

### `SaveReusedResult`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(existing|deleted) | 是 |
| `operation_id` | string | 是 |
| `plan_id` | string | 是 |

### `SaveToolInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `draft_id` | string | 是 |
| `draft_version` | integer | 是 |

### `SaveToolOutput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(created|existing) | 是 |
| `operation_id` | string | 是 |
| `plan_id` | string | 是 |

### `Schedule`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `id` | string | 是 |
| `student_id` | string | 是 |
| `course_id` | string | 是 |
| `course_name` | string | 是 |
| `class_date` | string | 是 |
| `start_time` | string | 是 |
| `end_time` | string | 是 |
| `location` | ? | 是 |
| `version` | integer | 是 |

### `ScheduleCreate`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `student_id` | string | 是 |
| `course_id` | string | 是 |
| `class_date` | string | 是 |
| `start_time` | string | 是 |
| `end_time` | string | 是 |
| `location` | ? |  |
| `overlap_acknowledged` | boolean |  |
| `reason` | string |  |

### `ScheduleDelete`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `deleted` | ? | 是 |
| `schedule_id` | string | 是 |
| `audit_id` | string | 是 |

### `SchedulePage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `items` | array<object> | 是 |
| `page` | integer | 是 |
| `page_size` | integer | 是 |
| `total` | integer | 是 |
| `from_date` | string | 是 |
| `to_date` | string | 是 |
| `school_timezone` | string | 是 |

### `SchedulePatch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `course_id` | string |  |
| `class_date` | string |  |
| `start_time` | string |  |
| `end_time` | string |  |
| `location` | ? |  |
| `overlap_acknowledged` | boolean |  |
| `reason` | string |  |
| `expected_version` | integer | 是 |

### `ScheduleToolInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `from_date` | string |  |
| `to_date` | string |  |

### `ScheduleToolOutput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(ok|empty) | 是 |
| `from_date` | string | 是 |
| `to_date` | string | 是 |
| `school_timezone` | string | 是 |
| `items` | array<object> | 是 |

### `SearchToolInput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `query` | string | 是 |

### `SearchToolOutput`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `status` | enum(ok|empty) | 是 |
| `corpus_empty` | boolean | 是 |
| `revision` | integer | 是 |
| `chunks` | array<object> | 是 |
| `references` | array<object> | 是 |

### `StudentCreate`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `account` | string | 是 |
| `display_name` | string | 是 |
| `initial_password` | string | 是 |

### `StudentPage`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `items` | array<object> | 是 |
| `page` | integer | 是 |
| `page_size` | integer | 是 |
| `total` | integer | 是 |

### `StudentPatch`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `display_name` | string |  |
| `enabled` | boolean |  |
| `expected_version` | integer | 是 |

### `Task`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `task_id` | string | 是 |
| `state` | enum(pending|running|retry_wait|succeeded|failed) | 是 |
| `error_code` | string |  |
| `retryable` | boolean | 是 |

### `Upload`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `files` | array<string> | 是 |
| `allow_duplicate_names` | boolean |  |

### `User`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `id` | string | 是 |
| `account` | string | 是 |
| `display_name` | string | 是 |
| `role` | enum(student|admin) | 是 |
| `enabled` | boolean | 是 |
| `version` | integer | 是 |

### `WriteOperation`

| 字段 | 类型 | 必填 |
| --- | --- | --- |
| `operation_id` | string | 是 |
| `state` | enum(pending|succeeded|failed|deleted) | 是 |
| `resolution` | enum(confirmed|recovering) | 是 |
| `plan_id` | string |  |
| `error_code` | string |  |
| `retryable` | boolean | 是 |

