/**
 * 焦点管理（§12.2、§12.3）。
 *
 * 硬规则：**流式内容绝不移动焦点**（NFR-UX-001）。焦点只在这三个时机移动：
 *   1. 用户动作（点击「打开计划」等）之后；
 *   2. 终态提示出现时（且只移动一次，不随 token 反复移动）；
 *   3. 错误摘要出现时（移到摘要容器，`tabindex="-1"`）。
 *
 * 另外两条：
 *   - 弹层/确认面板关闭后把焦点**回收**到触发它的元素（`ui.focusReturnTo`）；
 *   - 跳过链接必须聚焦到 `<main id="main">`，且该目标要可编程聚焦（`tabindex="-1"`，
 *     由 App.vue 提供），否则 `document.activeElement` 不会变，W1 的断言不成立。
 */

/** 可编程聚焦：`tabindex="-1"` 的元素也能接住焦点。 */
export function moveFocusTo(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  el.focus({ preventScroll: false })
  return document.activeElement === el
}

export function focusById(id: string): boolean {
  return moveFocusTo(document.getElementById(id))
}

/** 错误摘要出现时调用：把焦点移到摘要容器（§11.3）。 */
export function focusErrorSummary(summaryId = 'error-summary'): boolean {
  return focusById(summaryId)
}

/** 字段级错误：移到首个出错控件（其 id 由 `.field__error` 的 `aria-describedby` 反向关联）。 */
export function focusFirstInvalid(container: ParentNode): boolean {
  const el = container.querySelector<HTMLElement>('[aria-invalid="true"]')
  return moveFocusTo(el)
}

/** 记录触发元素，供弹层关闭后回收焦点。 */
export function rememberFocusReturn(): string | null {
  const el = document.activeElement
  if (!(el instanceof HTMLElement)) return null
  if (el.id) return `#${el.id}`
  return null
}

/** 回收焦点到选择器指向的元素。 */
export function restoreFocus(selector: string | null): boolean {
  if (!selector) return false
  try {
    return moveFocusTo(document.querySelector(selector))
  } catch {
    return false
  }
}

/**
 * 「回到最新」/「滚动跟随」的判定（§5.10）：
 * 仅当用户已在底部附近（距底 < 48px）时才自动跟随；上滑后停止跟随。
 */
export function isNearBottom(el: HTMLElement, thresholdPx: number): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < thresholdPx
}
