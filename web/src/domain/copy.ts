/**
 * 用户可见文案的唯一落点。
 *
 * 真源：`design/directions/shared/content-spec.md`（S01–S13）。
 * 规则（前端详细设计 §8.5.1 硬规则③ / CONTRACT §3.7 第 3 条）：
 *   - 每一行都必须能在 content-spec 里逐字查到（行号写在注释里）；
 *   - **禁止自造**；禁止「正在思考」「AI 推理中」「推理过程」「思考中」；
 *   - 禁止「暂无数据」「暂无内容」；
 *   - 「当天无安排」与「课表无法读取」必须是两条不同文案（S08 ①②）。
 *
 * 组件 chrome 文案（跳转链接、landmark 命名）不在此文件，归组件规格管辖
 * （design/system/README.md 裁决 13）。
 */

/* ===================== S01 登录（content-spec:51–59） ===================== */
export const S01 = {
  productName: '校园课程智能助手', // content-spec:52
  subtitle: '查课表 · 问资料 · 存计划，一个入口', // content-spec:53
  labelAccount: '账号', // content-spec:54
  labelPassword: '密码', // content-spec:54
  required: '必填', // content-spec:54；§1「必填有文字标记『必填』」
  submit: '登录', // content-spec:55
  invalidCredentials: '账号或密码不正确，请重试。', // content-spec:56
  accountDisabled: '当前账号不可用，请联系管理员。', // content-spec:59
  sessionFootnote: '登录会话有效期 2 小时，到期后需要重新登录。', // content-spec:58
  /* ---- 阶段 B · P2d 两栏登录页与自助注册（content-spec S15.5） ---- */
  tabLogin: '登录', // content-spec:243
  tabRegister: '注册', // content-spec:243
  registerTitle: '查课表 · 问资料 · 存计划，一个入口', // content-spec:236（逐字同 subtitle，不新增词）
  lead: '基于本校课程资料回答问题，课表与学习计划都在同一个页面里。', // content-spec:237
  points: [
    { title: '查我的课表', desc: '按日期查今天的课、下一节课与当天结束时间。' }, // content-spec:239
    { title: '问课程资料', desc: '依据课程资料回答，并在回答里标出资料来源。' }, // content-spec:240
    { title: '存学习计划', desc: '把拟定好的计划直接存进学习计划，随时回看。' }, // content-spec:241
  ],
  toRegister: '还没有账号？去注册', // content-spec:244
  toLogin: '已有账号？去登录', // content-spec:245
  labelName: '显示名', // content-spec:245
  labelConfirm: '确认密码', // content-spec:245
  submitRegister: '创建账号', // content-spec:245
  accountTooShort: '账号至少 3 个字符。', // content-spec:247
  passwordTooShort: '密码至少 8 位。', // content-spec:248
  passwordMismatch: '两次输入的密码不一致。', // content-spec:249
  duplicateAccount: '该账号已被注册，请换一个或直接登录。', // content-spec:251
} as const

/* ===================== S02 助手 · 空闲态（content-spec:61–69） ===================== */
export const S02 = {
  title: '你好，我是校园课程助手', // content-spec:62
  capability: '我可以查你的课表、根据课程资料回答问题、帮你拟定学习计划。', // content-spec:63
  boundaryNotice: '对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。', // content-spec:64
  clearConversation: '清空对话', // content-spec:64
  examples: ['查今天的课', '根据资料回答问题', '制定学习计划'], // content-spec:66–68
  composerLabel: '你的问题', // content-spec:69
  composerHint: '最多 2000 字', // content-spec:69
  send: '发送', // content-spec:69
} as const

/* ===================== S03 助手 · 执行中（content-spec:72–79） ===================== */
export const S03 = {
  sampleQuestion: '明天有什么课？顺便看看实验课要准备什么。', // content-spec:73
  processTitle: '本轮执行', // content-spec:74；禁止「正在思考」「AI 推理中」
  processing: '正在处理 · 最长 60 秒', // content-spec:77
  stop: '停止', // content-spec:77
  pendingCiteMark: '〔资料 1〕', // content-spec:78（未验证引用标记，样式须与已验证可区分）
} as const

/* ===================== S04 助手 · 有据回答（content-spec:82–89） ===================== */
export const S04 = {
  answer:
    '根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：1）预习实验二排序算法；2）提交预习报告，不少于 500 字。', // content-spec:83
  expandSnippet: '展开片段', // content-spec:85
  sourcedTag: '课程规定', // content-spec:88
  adviceTag: '一般学习建议', // content-spec:88
  citeInvalid: '这条引用已失效（资料已被删除），依据可能已变化。', // content-spec:89
} as const

/* ===================== S05 助手 · 依据不足 / 检索失败 / 全库为空（content-spec:92–95） ===================== */
export const S05 = {
  insufficient: '已检索共享资料，但没有找到足以回答这项要求的内容。', // content-spec:92
  rephrase: '换个问法', // content-spec:93
  contactAdmin: '联系管理员补充材料', // content-spec:93
  retrievalFailed: '课程资料暂时无法查询，请稍后重试。', // content-spec:94
  retry: '重试', // content-spec:94
  libraryEmpty: '管理员还没有上传可检索的课程资料。', // content-spec:95
} as const

/* ===================== S06 助手 · 草稿（content-spec:99–110） ===================== */
export const S06 = {
  draftTitle: '复习计划草稿', // content-spec:100
  unsaved: '未保存', // content-spec:100
  basisSchedule: '本人课表', // content-spec:104
  basisDocuments: '课程资料', // content-spec:104
  saveAsPlan: '保存为我的计划', // content-spec:106
  continueEditing: '继续修改', // content-spec:106
  savedPrefix: '已保存 · 计划编号', // content-spec:107
  openPlan: '打开计划', // content-spec:107
  confirming: '正在确认是否保存…', // content-spec:109
  unconfirmedNotice: '写入结果尚未确认，请勿重复创建；可稍后查询状态。', // content-spec:109
  queryWriteStatus: '查询写入状态', // content-spec:109
  idempotencyNote: '重复提交同一操作只会得到同一份计划。', // content-spec:110
} as const

/* ===================== S07 我的课表（content-spec:113–119） ===================== */
export const S07 = {
  title: '我的课表', // content-spec:113
  today: '今天', // content-spec:114
  rangeLimit: '单次最多查询 31 天', // content-spec:114
  colTime: '开始–结束时间', // content-spec:115
  colCourse: '课程名', // content-spec:115
  colLocation: '地点', // content-spec:115
  /** 页脚逐字样例（content-spec:118）。 */
  footer: '时间为学校时区 Asia/Shanghai', // content-spec:118
  /** 页脚模板：只有 `Asia/Shanghai` 是**数据**（`SchedulePage.school_timezone`），其余逐字。 */
  footerTemplate: '时间为学校时区 {timezone}', // content-spec:118
  /**
   * 纯图标按钮的可访问名（组件 chrome，归组件规格管辖，不进 content-spec）：
   * 02-actions-status.md §Btn 明确「冻结原型 records.html:22/26 的『查看前一天 / 查看后一天』是范例」。
   */
  prevDay: '查看前一天',
  nextDay: '查看后一天',
} as const

/* ===================== S08 我的课表 · 两种空状态（content-spec:122–124） ===================== */
export const S08 = {
  /** ① 查询成功但无记录 —— 中性，不得使用错误色。占位符 {date}/{weekday} 由 domain/format.ts 填充。 */
  noCoursesTemplate: '{date}（{weekday}）没有课程安排。', // content-spec:122
  changeDate: '换个日期', // content-spec:122
  /** ② 服务异常 —— 错误/警告语义，与 ① 明显不同。两者绝不合并为「暂无数据」。 */
  fetchFailed: '课表数据暂时无法读取，这不代表当天没有课。', // content-spec:124
  retry: '重试', // content-spec:124
} as const

/* ===================== S09 学习计划（content-spec:129–138） ===================== */
export const S09 = {
  listTitle: '学习计划', // content-spec:129
  searchLabel: '按标题筛选', // content-spec:129（可见 label）
  colTitle: '标题', // content-spec:130
  colRange: '覆盖日期', // content-spec:130
  colSource: '来源', // content-spec:130
  colUpdatedAt: '更新时间', // content-spec:130
  colActions: '操作', // content-spec:130
  sourceAssistant: '助手生成', // content-spec:131
  sourceManual: '手动创建', // content-spec:132
  noDates: '未设置日期', // content-spec:132
  open: '打开', // content-spec:131
  remove: '删除', // content-spec:131
  emptyList: '还没有学习计划。', // content-spec:133
  createManual: '手动新建', // content-spec:133
  create: '新建计划', // content-spec:134
  labelTitle: '标题', // content-spec:135
  labelGoal: '目标', // content-spec:135
  labelStartDate: '开始日期', // content-spec:135
  labelEndDate: '结束日期', // content-spec:135
  labelContent: '正文', // content-spec:135
  labelSource: '来源', // content-spec:135（只读）
  dateRangeError: '开始与结束日期需要同时填写，且开始日期不能晚于结束日期。', // content-spec:136
  versionConflict:
    '这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。', // content-spec:137
  /** 删除确认，占位符 {title} 由调用方填充；逐字形态见 content-spec:138。 */
  deleteConfirmTemplate: '删除「{title}」？删除后无法恢复。助手对话不受影响。', // content-spec:138
} as const

/* ===================== S10 管理中心 · 课程管理（content-spec:141–148） ===================== */
export const S10 = {
  title: '管理中心 · 课程管理', // content-spec:140
  filterLabel: '按课程代码或名称筛选', // content-spec:148（必须有筛选/搜索区）
  colCode: '课程代码', // content-spec:142
  colName: '名称', // content-spec:142
  colDescription: '简介', // content-spec:142
  colEnabled: '状态', // content-spec:142
  colActions: '操作', // content-spec:142
  enabled: '启用', // content-spec:142
  disabled: '已停用', // content-spec:143
  edit: '编辑', // content-spec:142
  create: '新建课程', // content-spec:144
  labelCode: '课程代码', // content-spec:145
  labelName: '名称', // content-spec:145
  labelDescription: '简介', // content-spec:145
  labelEnabled: '启用状态', // content-spec:145
  codeReadonlyNote: '课程代码创建后不可修改', // content-spec:145（逐字，引号内）
  duplicateCode: '该课程代码已存在，请更换。', // content-spec:146
  disableConfirm: '停用后不能再为该课程新增课表记录；已有课表和计划仍可查看。', // content-spec:147
} as const

/* ===================== S11 管理中心 · 文档与批次（content-spec:151–161） ===================== */
export const S11 = {
  title: '管理中心 · 文档与批次', // content-spec:150
  uploadHint: 'TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB', // content-spec:151
  chooseFile: '选择文件', // content-spec:151
  publishRule: '整批可见或整批不可见', // content-spec:152
  colFile: '文件', // content-spec:160（原名）
  colType: '类型', // content-spec:160
  colSize: '大小', // content-spec:160
  colUploadedAt: '上传时间', // content-spec:160
  colStatus: '状态', // content-spec:160
  colActions: '操作', // content-spec:160
  statusSearchable: '可检索', // content-spec:154
  statusProcessing: '处理中', // content-spec:155
  statusFailed: '失败', // content-spec:156
  statusDeleting: '删除中', // content-spec:157
  statusDeleteFailed: '删除失败', // content-spec:158
  retryCleanup: '重试清理', // content-spec:158
  noTextExtracted: '未提取到文字，可能是扫描件；本期不支持 OCR。', // content-spec:156（失败原因）
  batchRollback: '本批 1 个文件失败，整批未发布；其他批次不受影响。', // content-spec:159
  previewText: '预览抽取文本', // content-spec:161
} as const

/* ===================== S12 管理中心 · 课表维护（content-spec:164–171） ===================== */
export const S12 = {
  title: '管理中心 · 课表维护', // content-spec:163
  labelStudent: '学生', // content-spec:164
  labelCourse: '课程', // content-spec:164
  labelClassDate: '上课日期', // content-spec:164
  labelStartTime: '开始时间', // content-spec:164
  labelEndTime: '结束时间', // content-spec:164
  labelLocation: '地点', // content-spec:164
  labelReason: '冲突原因', // content-spec:170（原因，必填）
  timeRangeError: '结束时间必须晚于开始时间，且不支持跨日记录。', // content-spec:165
  duplicateSchedule: '该学生在同一天已有完全相同时间段的这门课，不能重复保存。', // content-spec:166
  confirmSave: '确认保存', // content-spec:170
  cancel: '取消', // content-spec:170
  /** 冲突提示，占位符 {date}/{start}/{end}/{course} 由调用方填充；逐字形态见 content-spec:168。 */
  overlapTemplate: '与 {date} {start}–{end} {course} 时间重叠。', // content-spec:168
  overlapAck: '需确认后继续', // content-spec:169（冲突确认面板的状态标记）
  deleteConfirmNote: '将记录操作人', // content-spec:171
  /** 停用课程不可选（content-spec:164）——只读提示，无冻结逐字文案，故不渲染自造句子。 */
} as const

/**
 * S15 桌面自适应增量（content-spec:192–202，按落地批次逐段追加）。
 *
 * 只放桌面布局带来的**新**句子；S01–S13 的既有文案不被改写（content-spec §2 S15 前言）。
 */
export const S15 = {
  /** 输入条提示行（content-spec:201）。放在 `.composer__bar` 左侧，随「发送」按钮同行。 */
  composerEnterHint: 'Enter 发送 · Shift+Enter 换行',
  /** 助手页右栏（content-spec:204–213）：标题、链接、两种空态、加载与错误。 */
  railScheduleTitle: '今日课表', // content-spec:206
  railPlansTitle: '学习计划', // content-spec:206
  railWeekLink: '本周 →', // content-spec:207
  railAllLink: '全部 →', // content-spec:207
  railNoClass: '今天没有课', // content-spec:208
  railNoPlans: '还没有学习计划。可以让助手根据课表和资料帮你拟定一份。', // content-spec:209
  railDraftAction: '让助手拟定', // content-spec:210
  railLoading: '正在读取…', // content-spec:211
  railScheduleError: '课表暂时读取不到', // content-spec:212
  railPlansError: '计划暂时读取不到', // content-spec:212

  /** 我的课表 · 只读信息层（content-spec:215–222）。 */
  statTodayCourses: '今日课程', // content-spec:217
  statNextClass: '下一节课', // content-spec:217
  statDayEnd: '今日结束', // content-spec:217
  statRange: '查询跨度', // content-spec:217
  dateField: '查询日期', // content-spec:218（日期框可见 label）
  timelineToday: '今日时间轴', // content-spec:219
  timelineEnd: '之后没有安排', // content-spec:219
  scheduleNoteTitle: '课表说明', // content-spec:222

  /** 学习计划 · 只读信息层（content-spec:226–232）。 */
  statPlanTotal: '计划总数', // content-spec:228
  statPlanOngoing: '进行中', // content-spec:228
  statPlanAssistant: '助手生成', // content-spec:228
  statPlanUpdated: '最近更新', // content-spec:228
  railRecent: '最近活动', // content-spec:229
  railEnding: '即将结束', // content-spec:229
  /** 占位符 `{N}` 由 `fill()` 填充，逐字形态见 content-spec:227。 */
  railDaysLeft: '还剩 {N} 天', // content-spec:229
  labelVersion: '版本', // content-spec:230
  planHint: '在对话里让助手拟定计划，确认后可直接保存到学习计划，无需手动搬运。', // content-spec:231

  /* ---- 管理中心 · 学生账号（content-spec S15.6，本轮冻结）---- */
  adminStudentsTitle: '管理中心 · 学生账号', // content-spec:257
  adminStudentsFilter: '按账号或名称筛选', // content-spec:258（原实现误用课程页筛选 label）
} as const

/**
 * 表单通用动作文案。
 *
 * 两条都**逐字取自 content-spec:170**（S12 重叠确认面板的主/次级按钮）：
 * 上游没有为其它表单的「保存」「取消」单独冻结文案，复用它比自造安全。
 * 这是**有意的复用**，已登记在 `web/BUILD-REPORT.md` 的未冻结文案缺口里。
 */
export const ACTIONS = {
  cancel: '取消', // content-spec:170
  save: '确认保存', // content-spec:170
} as const

/**
 * 组件 chrome 文案（**不是**屏幕内容文案）。
 *
 * 口径来自 `design/system/README.md` 收口裁决 13：content-spec 管屏幕内容文案，
 * 组件规格管组件 chrome 文案（跳转链接、landmark 命名、标识标签）。
 * 这里只登记**必需但 content-spec 未冻结**的标识标签，并显式标注归属待办 ——
 * 未经登记的自造句子一律不允许。
 */
export const CHROME = {
  /** `request_id` 的标签（§3.4「500 → 展示安全文案 + request_id 供支持定位」要求可展示）。 */
  requestIdLabel: '请求编号',
  /** 业务错误码的标签（§3.4/§4.8：分支一律基于 code，且 500 需可核对）。 */
  errorCodeLabel: '错误码',
  /** 跳过链接文案（组件规格 01 §7；rb.css:115–118）。 */
  skipToMain: '跳到主要内容',
  /** skip-link 的目标 id（App.vue 提供 `<main id="main">`）。 */
  mainId: 'main',
  /** 主导航的 landmark 名称（组件规格 01 §2 AppBar）。 */
  primaryNav: '主导航',
  /**
   * 登出按钮的可访问名。§4.5 规定登出行为，但 content-spec 没有冻结按钮文案；
   * 归组件 chrome 文案（裁决 13 的口径），并在报告里登记为待冻结项。
   */
  logout: '退出登录',
  /** `主体` landmark 名称（`<main id="main">`，skip-link 的目标）。 */
  mainLandmark: '主要内容',
  /**
   * 管理中心二级导航的 landmark 名称。content-spec 未冻结导航容器名，
   * 归组件 chrome 文案（裁决 13 的口径），登记为待冻结项。
   */
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
