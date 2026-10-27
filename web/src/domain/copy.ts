/**
 * 用户可见文案的唯一落点。
 *
 * 真源：`design/directions/shared/content-spec.md`（S01–S13 / S15）。
 * 规则（前端详细设计 §8.5.1 硬规则③ / CONTRACT §3.7 第 3 条）：
 *   - 每一行都必须能在 content-spec 里逐字查到（按**小节号**引用，如 `// content-spec S07`）；
 *   - **禁止自造**；禁止「正在思考」「AI 推理中」「推理过程」「思考中」；
 *   - 禁止「暂无数据」「暂无内容」；
 *   - 「当天无安排」与「课表无法读取」必须是两条不同文案（S08 ①②）。
 *
 * 为什么按小节号而不是行号：content-spec 是活文档，行号会随每次追加漂移
 * （2026-10-26 实测 S11 那批已偏 11 行）。小节号（S01、S15.5…）稳定且能直接定位到屏。
 *
 * 组件 chrome 文案（跳转链接、landmark 命名）不在此文件，归组件规格管辖
 * （design/system/README.md 裁决 13）。
 */

/* ===================== S01 登录（content-spec S01） ===================== */
export const S01 = {
  productName: '校园课程智能助手', // content-spec S01
  subtitle: '查课表 · 问资料 · 存计划，一个入口', // content-spec S01
  labelAccount: '账号', // content-spec S01
  labelPassword: '密码', // content-spec S01
  required: '必填', // content-spec S01；§1「必填有文字标记『必填』」
  submit: '登录', // content-spec S01
  invalidCredentials: '账号或密码不正确，请重试。', // content-spec S01
  accountDisabled: '当前账号不可用，请联系管理员。', // content-spec S01
  sessionFootnote: '登录会话有效期 2 小时，到期后需要重新登录。', // content-spec S01
  /* ---- 阶段 B · P2d 两栏登录页与自助注册（content-spec S15.5） ---- */
  tabLogin: '登录', // content-spec S15.5
  tabRegister: '注册', // content-spec S15.5
  registerTitle: '查课表 · 问资料 · 存计划，一个入口', // content-spec S15.5（逐字同 subtitle，不新增词）
  lead: '基于本校课程资料回答问题，课表与学习计划都在同一个页面里。', // content-spec S15.5
  points: [
    { title: '查我的课表', desc: '按日期查今天的课、下一节课与当天结束时间。' }, // content-spec S15.5
    { title: '问课程资料', desc: '依据课程资料回答，并在回答里标出资料来源。' }, // content-spec S15.5
    { title: '存学习计划', desc: '把拟定好的计划直接存进学习计划，随时回看。' }, // content-spec S15.5
  ],
  toRegister: '还没有账号？去注册', // content-spec S15.5
  toLogin: '已有账号？去登录', // content-spec S15.5
  labelName: '显示名', // content-spec S15.5
  labelConfirm: '确认密码', // content-spec S15.5
  submitRegister: '创建账号', // content-spec S15.5
  accountTooShort: '账号至少 3 个字符。', // content-spec S15.5
  passwordTooShort: '密码至少 8 位。', // content-spec S15.5
  passwordMismatch: '两次输入的密码不一致。', // content-spec S15.5
  duplicateAccount: '该账号已被注册，请换一个或直接登录。', // content-spec S15.5
} as const

/* ===================== S02 助手 · 空闲态（content-spec S01） ===================== */
export const S02 = {
  title: '你好，我是校园课程助手', // content-spec S01
  capability: '我可以查你的课表、根据课程资料回答问题、帮你拟定学习计划。', // content-spec S01
  boundaryNotice: '对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。', // content-spec S01
  clearConversation: '清空对话', // content-spec S01
  examples: ['查今天的课', '根据资料回答问题', '制定学习计划'], // content-spec S01
  composerLabel: '你的问题', // content-spec S01
  composerHint: '最多 2000 字', // content-spec S01
  send: '发送', // content-spec S01
} as const

/* ===================== S03 助手 · 执行中（content-spec S02） ===================== */
export const S03 = {
  sampleQuestion: '明天有什么课？顺便看看实验课要准备什么。', // content-spec S02
  processTitle: '本轮执行', // content-spec S02；禁止「正在思考」「AI 推理中」
  processing: '正在处理 · 最长 60 秒', // content-spec S02
  stop: '停止', // content-spec S02
  pendingCiteMark: '〔资料 1〕', // content-spec S02（未验证引用标记，样式须与已验证可区分）
} as const

/* ===================== S04 助手 · 有据回答（content-spec S03） ===================== */
export const S04 = {
  answer:
    '根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：1）预习实验二排序算法；2）提交预习报告，不少于 500 字。', // content-spec S03
  expandSnippet: '展开片段', // content-spec S03
  sourcedTag: '课程规定', // content-spec S03
  adviceTag: '一般学习建议', // content-spec S03
  citeInvalid: '这条引用已失效（资料已被删除），依据可能已变化。', // content-spec S03
} as const

/* ===================== S05 助手 · 依据不足 / 检索失败 / 全库为空（content-spec S04） ===================== */
export const S05 = {
  insufficient: '已检索共享资料，但没有找到足以回答这项要求的内容。', // content-spec S04
  rephrase: '换个问法', // content-spec S04
  contactAdmin: '联系管理员补充材料', // content-spec S04
  retrievalFailed: '课程资料暂时无法查询，请稍后重试。', // content-spec S04
  retry: '重试', // content-spec S04
  libraryEmpty: '管理员还没有上传可检索的课程资料。', // content-spec S04
} as const

/* ===================== S06 助手 · 草稿（content-spec S04） ===================== */
export const S06 = {
  draftTitle: '复习计划草稿', // content-spec S04
  unsaved: '未保存', // content-spec S04
  basisSchedule: '本人课表', // content-spec S05
  basisDocuments: '课程资料', // content-spec S05
  saveAsPlan: '保存为我的计划', // content-spec S05
  continueEditing: '继续修改', // content-spec S05
  savedPrefix: '已保存 · 计划编号', // content-spec S05
  openPlan: '打开计划', // content-spec S05
  confirming: '正在确认是否保存…', // content-spec S06
  unconfirmedNotice: '写入结果尚未确认，请勿重复创建；可稍后查询状态。', // content-spec S06
  queryWriteStatus: '查询写入状态', // content-spec S06
  idempotencyNote: '重复提交同一操作只会得到同一份计划。', // content-spec S06
} as const

/* ===================== S07 我的课表（content-spec S06） ===================== */
export const S07 = {
  title: '我的课表', // content-spec S06
  today: '今天', // content-spec S06
  rangeLimit: '单次最多查询 31 天', // content-spec S06
  colTime: '开始–结束时间', // content-spec S06
  colCourse: '课程名', // content-spec S06
  colLocation: '地点', // content-spec S06
  /** 页脚逐字样例（content-spec S06）。 */
  footer: '时间为学校时区 Asia/Shanghai', // content-spec S06
  /** 页脚模板：只有 `Asia/Shanghai` 是**数据**（`SchedulePage.school_timezone`），其余逐字。 */
  footerTemplate: '时间为学校时区 {timezone}', // content-spec S06
  /**
   * 纯图标按钮的可访问名（组件 chrome，归组件规格管辖，不进 content-spec）：
   * 02-actions-status.md §Btn 明确「冻结原型 records.html:22/26 的『查看前一天 / 查看后一天』是范例」。
   */
  prevDay: '查看前一天',
  nextDay: '查看后一天',
} as const

/* ===================== S08 我的课表 · 两种空状态（content-spec S06） ===================== */
export const S08 = {
  /** ① 查询成功但无记录 —— 中性，不得使用错误色。占位符 {date}/{weekday} 由 domain/format.ts 填充。 */
  noCoursesTemplate: '{date}（{weekday}）没有课程安排。', // content-spec S06
  changeDate: '换个日期', // content-spec S06
  /** ② 服务异常 —— 错误/警告语义，与 ① 明显不同。两者绝不合并为「暂无数据」。 */
  fetchFailed: '课表数据暂时无法读取，这不代表当天没有课。', // content-spec S07
  retry: '重试', // content-spec S07
} as const

/* ===================== S09 学习计划（content-spec S07） ===================== */
export const S09 = {
  listTitle: '学习计划', // content-spec S07
  searchLabel: '按标题筛选', // content-spec S07（可见 label）
  colTitle: '标题', // content-spec S07
  colRange: '覆盖日期', // content-spec S07
  colSource: '来源', // content-spec S07
  colUpdatedAt: '更新时间', // content-spec S07
  colActions: '操作', // content-spec S07
  sourceAssistant: '助手生成', // content-spec S07
  sourceManual: '手动创建', // content-spec S08
  noDates: '未设置日期', // content-spec S08
  open: '打开', // content-spec S07
  remove: '删除', // content-spec S07
  emptyList: '还没有学习计划。', // content-spec S08
  createManual: '手动新建', // content-spec S08
  create: '新建计划', // content-spec S08
  labelTitle: '标题', // content-spec S08
  labelGoal: '目标', // content-spec S08
  labelStartDate: '开始日期', // content-spec S08
  labelEndDate: '结束日期', // content-spec S08
  labelContent: '正文', // content-spec S08
  labelSource: '来源', // content-spec S08（只读）
  dateRangeError: '开始与结束日期需要同时填写，且开始日期不能晚于结束日期。', // content-spec S08
  versionConflict:
    '这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。', // content-spec S08
  /** 删除确认，占位符 {title} 由调用方填充；逐字形态见 content-spec S08。 */
  deleteConfirmTemplate: '删除「{title}」？删除后无法恢复。助手对话不受影响。', // content-spec S08
} as const

/* ===================== S10 管理中心 · 课程管理（content-spec S09） ===================== */
export const S10 = {
  title: '管理中心 · 课程管理', // content-spec S09
  filterLabel: '按课程代码或名称筛选', // content-spec S09（必须有筛选/搜索区）
  colCode: '课程代码', // content-spec S09
  colName: '名称', // content-spec S09
  colDescription: '简介', // content-spec S09
  colEnabled: '状态', // content-spec S09
  colActions: '操作', // content-spec S09
  enabled: '启用', // content-spec S09
  disabled: '已停用', // content-spec S09
  edit: '编辑', // content-spec S09
  create: '新建课程', // content-spec S09
  labelCode: '课程代码', // content-spec S09
  labelName: '名称', // content-spec S09
  labelDescription: '简介', // content-spec S09
  labelEnabled: '启用状态', // content-spec S09
  codeReadonlyNote: '课程代码创建后不可修改', // content-spec S09（逐字，引号内）
  duplicateCode: '该课程代码已存在，请更换。', // content-spec S09
  disableConfirm: '停用后不能再为该课程新增课表记录；已有课表和计划仍可查看。', // content-spec S09
} as const

/* ===================== S11 管理中心 · 文档与批次（content-spec S10） ===================== */
export const S11 = {
  title: '管理中心 · 文档与批次', // content-spec S11
  uploadHint: 'TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB', // content-spec S11
  chooseFile: '选择文件', // content-spec S11
  dropTitle: '把文件拖到这里，或选择文件', // content-spec S11（S11 上传区：拖拽区标题）
  publishRule: '整批可见或整批不可见', // content-spec S11
  colFile: '文件', // content-spec S10（原名）
  colType: '类型', // content-spec S10
  colSize: '大小', // content-spec S10
  colUploadedAt: '上传时间', // content-spec S10
  colStatus: '状态', // content-spec S10
  colActions: '操作', // content-spec S10
  statusSearchable: '可检索', // content-spec S10
  statusProcessing: '处理中', // content-spec S10
  statusFailed: '失败', // content-spec S10
  statusDeleting: '删除中', // content-spec S10
  statusDeleteFailed: '删除失败', // content-spec S10
  retryCleanup: '重试清理', // content-spec S10
  noTextExtracted: '未提取到文字，可能是扫描件；本期不支持 OCR。', // content-spec S10（失败原因）
  batchRollback: '本批 1 个文件失败，整批未发布；其他批次不受影响。', // content-spec S10
  previewText: '预览抽取文本', // content-spec S11
  previewUnavailableProcessing: '抽取文本预览暂不可用：文件仍在处理中，请稍后再试。', // content-spec S11（FR-DOC-004 原因）
  previewUnavailableFailed: '抽取文本预览不可用：未提取到文字（可能是扫描件，本期不支持 OCR）。', // content-spec S11（FR-DOC-004 原因）
} as const

/* ===================== S12 管理中心 · 课表维护（content-spec S11） ===================== */
export const S12 = {
  title: '管理中心 · 课表维护', // content-spec S11
  labelStudent: '学生', // content-spec S11
  labelCourse: '课程', // content-spec S11
  labelClassDate: '上课日期', // content-spec S11
  labelStartTime: '开始时间', // content-spec S11
  labelEndTime: '结束时间', // content-spec S11
  labelLocation: '地点', // content-spec S11
  labelReason: '冲突原因', // content-spec S11（原因，必填）
  timeRangeError: '结束时间必须晚于开始时间，且不支持跨日记录。', // content-spec S11
  duplicateSchedule: '该学生在同一天已有完全相同时间段的这门课，不能重复保存。', // content-spec S11
  confirmSave: '确认保存', // content-spec S11
  cancel: '取消', // content-spec S11
  /** 冲突提示，占位符 {date}/{start}/{end}/{course} 由调用方填充；逐字形态见 content-spec S11。 */
  overlapTemplate: '与 {date} {start}–{end} {course} 时间重叠。', // content-spec S11
  overlapAck: '需确认后继续', // content-spec S11（冲突确认面板的状态标记）
  deleteConfirmNote: '将记录操作人', // content-spec S11
  /** 停用课程不可选（content-spec S11）——只读提示，无冻结逐字文案，故不渲染自造句子。 */
} as const

/**
 * S15 桌面自适应增量（content-spec S15，按落地批次逐段追加）。
 *
 * 只放桌面布局带来的**新**句子；S01–S13 的既有文案不被改写（content-spec §2 S15 前言）。
 */
export const S15 = {
  /** 输入条提示行（content-spec S15.1）。放在 `.composer__bar` 左侧，随「发送」按钮同行。 */
  composerEnterHint: 'Enter 发送 · Shift+Enter 换行',
  /** 助手页右栏（content-spec S15.2）：标题、链接、两种空态、加载与错误。 */
  railScheduleTitle: '今日课表', // content-spec S15.2
  railPlansTitle: '学习计划', // content-spec S15.2
  railWeekLink: '本周 →', // content-spec S15.2
  railAllLink: '全部 →', // content-spec S15.2
  railNoClass: '今天没有课', // content-spec S15.2
  railNoPlans: '还没有学习计划。可以让助手根据课表和资料帮你拟定一份。', // content-spec S15.2
  railDraftAction: '让助手拟定', // content-spec S15.2
  railLoading: '正在读取…', // content-spec S15.2
  railScheduleError: '课表暂时读取不到', // content-spec S15.2
  railPlansError: '计划暂时读取不到', // content-spec S15.2

  /** 我的课表 · 只读信息层（content-spec S15.3）。 */
  statTodayCourses: '今日课程', // content-spec S15.3
  statNextClass: '下一节课', // content-spec S15.3
  statDayEnd: '今日结束', // content-spec S15.3
  statRange: '查询跨度', // content-spec S15.3
  dateField: '查询日期', // content-spec S15.3（日期框可见 label）
  timelineToday: '今日时间轴', // content-spec S15.3
  timelineEnd: '之后没有安排', // content-spec S15.3
  scheduleNoteTitle: '课表说明', // content-spec S15.3

  /** 学习计划 · 只读信息层（content-spec S15.4）。 */
  statPlanTotal: '计划总数', // content-spec S15.4
  statPlanOngoing: '进行中', // content-spec S15.4
  statPlanAssistant: '助手生成', // content-spec S15.4
  statPlanUpdated: '最近更新', // content-spec S15.4
  railRecent: '最近活动', // content-spec S15.4
  railEnding: '即将结束', // content-spec S15.4
  /** 占位符 `{N}` 由 `fill()` 填充，逐字形态见 content-spec S15.4。 */
  railDaysLeft: '还剩 {N} 天', // content-spec S15.4
  labelVersion: '版本', // content-spec S15.4
  planHint: '在对话里让助手拟定计划，确认后可直接保存到学习计划，无需手动搬运。', // content-spec S15.4

  /* ---- 管理中心 · 学生账号（content-spec S15.6，本轮冻结）---- */
  adminStudentsTitle: '管理中心 · 学生账号', // content-spec S15.6
  adminStudentsFilter: '按账号或名称筛选', // content-spec S15.6（原实现误用课程页筛选 label）
} as const

/**
 * 表单通用动作文案。
 *
 * 两条都**逐字取自 content-spec S11**（S12 重叠确认面板的主/次级按钮）：
 * 上游没有为其它表单的「保存」「取消」单独冻结文案，复用它比自造安全。
 * 这是**有意的复用**，已登记在 `web/BUILD-REPORT.md` 的未冻结文案缺口里。
 */
export const ACTIONS = {
  cancel: '取消', // content-spec S11
  save: '确认保存', // content-spec S11
} as const

/**
 * 组件 chrome 文案（**不是**屏幕内容文案）。
 *
 * 口径来自 `design/system/README.md` 收口裁决 13：content-spec 管屏幕内容文案，
 * 组件规格管组件 chrome 文案（跳转链接、landmark 命名、标识标签）。
 * P5b 裁决 B3（2026-10-26）把这里**逐条冻结进了组件规格**，本常量表不再是"待冻结登记"，
 * 而是规格的唯一实现处——改字必须先改规格：
 *
 *   01-shell-navigation.md §11 → C1–C6（skipToMain / mainId / primaryNav / mainLandmark / logout / adminNav）
 *   02-actions-status.md    §7  → C7–C8（requestIdLabel / errorCodeLabel）
 *
 * 未经登记的句子一律不允许（`content-spec` 与组件规格都没写的，就不渲染）。
 */
export const CHROME = {
  /** C7（02 §7）：`request_id` 的标签。§3.4 要求 500 可展示，供支持定位。 */
  requestIdLabel: '请求编号',
  /** C8（02 §7）：业务错误码的标签。§3.4/§4.8：分支一律基于 code，且 500 需可核对。 */
  errorCodeLabel: '错误码',
  /** C1（01 §11）：跳过链接文案（组件规格 01 §7；rb.css:115–118）。 */
  skipToMain: '跳到主要内容',
  /** C2（01 §11）：skip-link 的目标 id —— 是技术 id，不是文案（App.vue 提供 `<main id="main">`）。 */
  mainId: 'main',
  /** C3（01 §11）：主导航的 landmark 名称（组件规格 01 §2 AppBar；TabBar 复用同一名）。 */
  primaryNav: '主导航',
  /** C5（01 §11）：登出按钮的可访问名。§4.5 规定登出行为，文案归组件 chrome。 */
  logout: '退出登录',
  /** C4（01 §11）：`主体` landmark 名称（`<main id="main">`，skip-link 的目标）。 */
  mainLandmark: '主要内容',
  /** C6（01 §11）：管理中心二级导航的 landmark 名称。 */
  adminNav: '管理中心导航',
} as const

/**
 * **未冻结文案的缺口登记（实现期不得自造，故不渲染句子）**
 *
 * §3.4 对下列 code 只给了「客户端行为」，没有冻结用户可见句子；
 * content-spec 也没有对应屏幕块。因此 `mapError.ts` 在遇到它们时
 * **只展示 `code` + `request_id` + 已冻结的「重试」动作**，不自造一行 prose：
 *
 *   AUTH_REQUIRED / SESSION_EXPIRED（跳登录页，页脚用 S01.sessionFootnote）
 *   FORBIDDEN（守卫已拦，回 /assistant，不提示具体资源）
 *   RESOURCE_NOT_FOUND（不得区分「不存在」与「无权限」→ 因此**故意无文案**）
 *   VALIDATION_FAILED（逐字段 reason 由服务端给出，见 §4.8）
 *   MODEL_UNAVAILABLE / RETRIEVAL_UNAVAILABLE / MCP_UNAVAILABLE / STORAGE_UNAVAILABLE
 *   EXECUTION_TIMEOUT / SAVE_NOT_AUTHORIZED / SAVE_LIMIT_REACHED
 *   DUPLICATE_ACCOUNT / DUPLICATE_FILENAME / DOCUMENT_BUSY / CITATION_UNAVAILABLE
 *   UPLOAD_TOO_LARGE / UNSUPPORTED_FILE_TYPE（限额与类型清单见 S11.uploadHint）
 *   IDEMPOTENCY_CONFLICT（形态见 S06.idempotencyNote）
 *   CAPACITY_LIMITED / CALL_LIMIT_REACHED（§6.5 只要求「可理解提示」，无冻结句）
 *
 * 这条缺口必须随内容契约补齐（见 web/BUILD-REPORT.md「未覆盖 / 待裁决」）。
 */
export const UNFROZEN_ERROR_CODES = [
  'AUTH_REQUIRED',
  'SESSION_EXPIRED',
  'FORBIDDEN',
  'RESOURCE_NOT_FOUND',
  'VALIDATION_FAILED',
  'MODEL_UNAVAILABLE',
  'RETRIEVAL_UNAVAILABLE',
  'MCP_UNAVAILABLE',
  'STORAGE_UNAVAILABLE',
  'EXECUTION_TIMEOUT',
  'SAVE_NOT_AUTHORIZED',
  'SAVE_LIMIT_REACHED',
  'DUPLICATE_ACCOUNT',
  'DUPLICATE_FILENAME',
  'DOCUMENT_BUSY',
  'UPLOAD_TOO_LARGE',
  'UNSUPPORTED_FILE_TYPE',
  'CAPACITY_LIMITED',
  'CALL_LIMIT_REACHED',
  'INTERNAL_ERROR',
] as const
