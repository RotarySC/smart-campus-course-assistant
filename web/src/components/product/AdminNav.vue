<script setup lang="ts">
/**
 * 管理中心二级导航（`ADMIN_PAGES` 的 4 个入口 + 文档批次详情页归属「文档与批次」）。
 *
 * 为什么需要它：顶栏只有一个「管理中心」入口（落到 `/admin/courses`），
 * 另外三个管理页原本**只能靠直接输入 URL 到达**——管理端在桌面端有 4 个平级页面，
 * 没有二级导航就是死路。此处只补导航，不改任何页面的业务逻辑。
 *
 * 约束与取法：
 * - 只消费既有 class（`nav` + `.row` + `.navlink`），**不新增 class / token**；
 * - 标签 = 对应路由 `meta.title` 去掉冻结的页面标题前缀「管理中心 · 」，
 *   **不新增任何句子**（`S10.title` / `S11.title` / `S12.title` 已在 content-spec 冻结，
 *   「学生账号」是 routes.ts 里已登记的待冻结标题）；
 * - 当前项由 `NavLink` 的 `aria-current="page"` 表达，不额外加状态类。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavLink from '@/components/base/NavLink.vue'
import { ADMIN_DETAIL_PARENT, ADMIN_PAGES, routes } from '@/router/routes'
import { CHROME } from '@/domain/copy'

const route = useRoute()

/** 页面标题的冻结前缀：去掉它才适合当 Tab 文案（否则每项都以「管理中心 · 」开头）。 */
const TITLE_PREFIX = '管理中心 · '

const items = computed(() =>
  ADMIN_PAGES.map((name) => {
    const record = routes.find((r) => r.name === name)
    const title = String(record?.meta?.title ?? name)
    return {
      name,
      to: String(record?.path ?? ''),
      label: title.startsWith(TITLE_PREFIX) ? title.slice(TITLE_PREFIX.length) : title,
    }
  }),
)

/** 详情页没有自己的 Tab，归属到父页面，避免导航整排都不高亮。 */
const current = computed<string | undefined>(() =>
  route.name === 'adminBatch' ? ADMIN_DETAIL_PARENT : (route.name as string | undefined),
)
</script>

<template>
  <nav class="row" :aria-label="CHROME.adminNav">
    <NavLink v-for="it in items" :key="it.name" :to="it.to" :current="current === it.name">
      {{ it.label }}
    </NavLink>
  </nav>
</template>
