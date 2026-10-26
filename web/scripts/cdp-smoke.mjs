#!/usr/bin/env node
/**
 * cdp-smoke.mjs —— 浏览器级冒烟（Edge headless + CDP，**零新增依赖**）
 *
 * 依据：PHASE-04 F8「浏览器冒烟（可选但推荐）：Node 24 内置 WebSocket + Edge CDP，
 * 检查控制台无 error、关键选择器存在、SSE 文本流入；截图存 web/reports/」。
 *
 * 为什么自己写 CDP 客户端而不是引 Playwright：本车道约束「不新增依赖」，而需要的能力
 * （导航、求值、截图、控制台采集）只用到 CDP 的 4 个域，内置 WebSocket 足够。
 *
 * 用法：
 *   node scripts/cdp-smoke.mjs                 # 默认：守卫 + 登录页渲染检查（不需要后端）
 *   node scripts/cdp-smoke.mjs --full          # 真实链路（需要后端 8100 + 种子账号，F8 后续扩展）
 *   环境变量：WEB_BASE（默认 http://localhost:5173）、EDGE_PATH（默认自动探测）、
 *             BACKEND_BASE（默认 http://127.0.0.1:8100/api/v1）、E2E_ACCOUNT / E2E_PASSWORD
 *
 * 退出码：0 = 全绿；1 = 有 FAIL 或环境不可用。
 */

import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = path.resolve(HERE, '..')
const REPORTS = path.join(WEB_ROOT, 'reports')
const ARTIFACTS = path.join(REPORTS, 'artifacts')

const WEB_BASE = (process.env.WEB_BASE ?? 'http://localhost:5173').replace(/\/$/, '')
const BACKEND_BASE = (process.env.BACKEND_BASE ?? 'http://127.0.0.1:8100/api/v1').replace(/\/$/, '')
const FULL = process.argv.includes('--full')
const PAGES = process.argv.includes('--pages')
const LOGIN = process.argv.includes('--login') || FULL || PAGES
const askArg = process.argv.find((a) => a.startsWith('--ask='))
const ASK = askArg ? askArg.slice('--ask='.length) : FULL ? '查今天的课' : null
const ACCOUNT = process.env.E2E_ACCOUNT ?? 'student_demo'
const PASSWORD = process.env.E2E_PASSWORD ?? 'demo1234'
const ADMIN_ACCOUNT = process.env.E2E_ADMIN_ACCOUNT ?? 'admin_demo'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'demo1234'
const DEBUG_PORT = 9333

const results = []
function check(name, ok, detail = '') {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

/* ------------------------------- CDP 客户端 ------------------------------- */

class Cdp {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl)
    this.nextId = 1
    this.pending = new Map()
    this.handlers = new Map()
    this.closed = false
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true })
      this.ws.addEventListener('error', () => reject(new Error('CDP WebSocket 连接失败')), { once: true })
    })
    this.ws.addEventListener('message', (ev) => this.onMessage(ev.data))
    this.ws.addEventListener('close', () => {
      this.closed = true
      for (const { reject } of this.pending.values()) reject(new Error('CDP 连接已关闭'))
      this.pending.clear()
    })
  }

  onMessage(raw) {
    let msg
    try {
      msg = JSON.parse(typeof raw === 'string' ? raw : raw.toString())
    } catch {
      return
    }
    if (msg.id !== undefined) {
      const p = this.pending.get(msg.id)
      if (!p) return
      this.pending.delete(msg.id)
      if (msg.error) p.reject(new Error(`${p.method}: ${msg.error.message}`))
      else p.resolve(msg.result)
      return
    }
    for (const fn of this.handlers.get(msg.method) ?? []) fn(msg.params)
  }

  send(method, params = {}) {
    if (this.closed) return Promise.reject(new Error('CDP 已关闭'))
    const id = this.nextId++
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }

  on(event, fn) {
    const arr = this.handlers.get(event) ?? []
    arr.push(fn)
    this.handlers.set(event, arr)
  }

  close() {
    try {
      this.ws.close()
    } catch {
      /* ignore */
    }
  }
}

/* -------------------------------- 工具函数 -------------------------------- */

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function waitFor(fn, { timeoutMs = 10_000, intervalMs = 100, label = '条件' } = {}) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    try {
      const v = await fn()
      if (v) return v
    } catch {
      /* 继续等 */
    }
    if (Date.now() > deadline) throw new Error(`${label} 等待超时（${timeoutMs}ms）`)
    await sleep(intervalMs)
  }
}

function findEdge() {
  if (process.env.EDGE_PATH) return process.env.EDGE_PATH
  const candidates = [
    path.join(process.env['ProgramFiles'] ?? '', 'Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env['ProgramFiles(x86)'] ?? '', 'Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env.LOCALAPPDATA ?? '', 'Microsoft/Edge/Application/msedge.exe'),
  ]
  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c
  }
  return null
}

async function launchEdge() {
  const edge = findEdge()
  if (!edge) throw new Error('找不到 msedge.exe（可用 EDGE_PATH 指定）')
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'cca-cdp-'))
  const proc = spawn(
    edge,
    [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-extensions',
      '--hide-scrollbars',
      '--window-size=1366,850',
      `--remote-debugging-port=${DEBUG_PORT}`,
      `--user-data-dir=${profile}`,
      'about:blank',
    ],
    { stdio: 'ignore', windowsHide: true },
  )
  // 等调试端口就绪（唯一可信判据：/json/version 可读）
  await waitFor(
    async () => {
      const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`, { signal: AbortSignal.timeout(1000) })
      return r.ok
    },
    { timeoutMs: 20_000, label: 'Edge CDP 端口' },
  )
  const list = await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)).json()
  const page = list.find((t) => t.type === 'page')
  if (!page?.webSocketDebuggerUrl) throw new Error('没有可用的 page target')
  return { proc, profile, wsUrl: page.webSocketDebuggerUrl }
}

function savePng(name, base64) {
  fs.mkdirSync(ARTIFACTS, { recursive: true })
  const file = path.join(ARTIFACTS, name)
  fs.writeFileSync(file, Buffer.from(base64, 'base64'))
  return file
}

/* --------------------------------- 主流程 --------------------------------- */

async function main() {
  console.log(`== 浏览器冒烟（Edge headless + CDP）==`)
  console.log(`WEB_BASE=${WEB_BASE}  FULL=${FULL}`)

  // 前置：前端可达
  try {
    const r = await fetch(`${WEB_BASE}/`, { signal: AbortSignal.timeout(3000) })
    check('前端 dev server 可达', r.ok, `HTTP ${r.status}`)
    if (!r.ok) throw new Error('前端不可达')
  } catch (e) {
    check('前端 dev server 可达', false, e.message)
    return finish()
  }

  const { proc, profile, wsUrl } = await launchEdge()
  const cdp = new Cdp(wsUrl)
  const consoleErrors = []
  const exceptions = []
  try {
    await cdp.open()
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Log.enable')
    await cdp.send('Network.enable')

    const netLog = []
    cdp.on('Network.responseReceived', (p) => {
      const r = p.response
      if (r?.url?.includes('/api/')) netLog.push(`${r.status} ${r.url.replace(/^https?:\/\/[^/]+/, '')}`)
    })

    cdp.on('Runtime.consoleAPICalled', (p) => {
      if (p.type === 'error') consoleErrors.push(p.args.map((a) => a.value ?? a.description ?? '').join(' '))
    })
    cdp.on('Runtime.exceptionThrown', (p) => {
      exceptions.push(p.exceptionDetails?.exception?.description ?? p.exceptionDetails?.text ?? 'exception')
    })
    cdp.on('Log.entryAdded', (p) => {
      if (p.entry?.level === 'error') consoleErrors.push(`${p.entry.source}: ${p.entry.text}`)
    })

    const evaluate = async (expression) => {
      const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.text ?? 'evaluate 异常')
      return r.result?.value
    }

    const navigate = async (url) => {
      await cdp.send('Page.navigate', { url })
      await waitFor(() => evaluate("document.readyState === 'complete'"), { label: 'readyState=complete' })
    }

    // ---- 1) 未登录访问受保护路由 → 跳 /login（G2）----
    await navigate(`${WEB_BASE}/me/schedules`)
    const pathname = await waitFor(
      async () => {
        const p = await evaluate('location.pathname')
        return p === '/login' ? p : false
      },
      { label: '未登录守卫跳转 /login', timeoutMs: 10_000 },
    )
    check('G2 未登录访问 /me/schedules → /login', pathname === '/login', `实际 ${pathname}`)

    // ---- 2) 登录页关键选择器与标题 ----
    const dom = await evaluate(`(() => ({
      main: !!document.querySelector('main#main'),
      account: !!document.querySelector('#login-account'),
      password: !!document.querySelector('#login-password'),
      submit: !!document.querySelector('button[type="submit"]'),
      title: document.title,
    }))()`)
    check('main#main 存在（skip-link 目标）', dom.main === true)
    check('登录表单字段存在（#login-account/#login-password/submit）', dom.account && dom.password && dom.submit)
    check('document.title 带固定后缀', /· 校园课程智能助手$/.test(dom.title ?? ''), dom.title)

    // ---- 3) 刷新后仍在登录页（令牌仅内存，G6）----
    await cdp.send('Page.reload', { ignoreCache: false })
    await waitFor(() => evaluate("document.readyState === 'complete'"), { label: 'reload complete' })
    const afterReload = await evaluate('location.pathname')
    check('G6 刷新后仍在 /login（令牌不持久化）', afterReload === '/login', `实际 ${afterReload}`)

    // ---- 4) 控制台无 error ----
    await sleep(300)
    const ignore = /favicon|net::ERR_|Failed to load resource/i
    const realErrors = consoleErrors.filter((e) => !ignore.test(e))
    check('控制台无 error', realErrors.length === 0, realErrors.slice(0, 3).join(' | '))
    check('无未捕获异常', exceptions.length === 0, exceptions.slice(0, 2).join(' | '))

    // ---- 5) 截图取证 ----
    fs.mkdirSync(REPORTS, { recursive: true })
    const shot = await cdp.send('Page.captureScreenshot', { format: 'png' })
    const file = savePng('smoke-login.png', shot.data)
    check('截图已保存', fs.existsSync(file), path.relative(WEB_ROOT, file))

    // ---- 6) 登录 + 关键页面（--login / --full）----
    // 用 CDP Input.insertText 走**浏览器真实输入事件**（比合成 Event('input') 更接近用户操作，
    // 且能验证 v-model 真的把值写进了组件状态）。
    const typeInto = async (selector, text) => {
      const focused = await evaluate(`(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return false;
        el.focus();
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, '');
        el.dispatchEvent(new Event('input', { bubbles: true }));
        return document.activeElement === el;
      })()`)
      if (!focused) return false
      await cdp.send('Input.insertText', { text })
      return (await evaluate(`document.querySelector(${JSON.stringify(selector)})?.value ?? ''`)) === text
    }
    const clickByText = (text, scope = 'button') =>
      evaluate(`(() => {
        const btns = [...document.querySelectorAll(${JSON.stringify(scope)})];
        const b = btns.find((x) => x.textContent.trim() === ${JSON.stringify(text)} && !x.disabled);
        if (!b) return false;
        b.click();
        return true;
      })()`)
    const clickNav = async (text) => {
      await evaluate(`(() => {
        const links = [...document.querySelectorAll('nav a')];
        const a = links.find((x) => x.textContent.trim() === ${JSON.stringify(text)} && x.getClientRects().length > 0);
        if (a) a.click();
      })()`)
      await sleep(250)
    }
    /**
     * 按选择器点击。登录页改成两栏 + Tab 之后，「登录」这两个字同时出现在
     * 「登录 Tab」与「登录按钮」上，`clickByText('登录')` 会命中 Tab（§15.6 已登记）。
     * 因此登录提交一律用冻结的 id `#login-submit`。
     */
    const clickSelector = (selector) =>
      evaluate(`(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        if (!el || el.disabled || el.getClientRects().length === 0) return false;
        el.click();
        return true;
      })()`)
    const rows = () => evaluate("document.querySelectorAll('.table tbody tr').length")
    const loginAs = async (account, password) => {
      await typeInto('#login-account', account)
      await typeInto('#login-password', password)
      await clickSelector('#login-submit')
      return waitFor(
        async () => {
          const p = await evaluate('location.pathname')
          return p !== '/login' ? p : false
        },
        { label: `登录（${account}）`, timeoutMs: 20_000 },
      )
    }

    // ---- 5.1) 两栏登录页的 Tab 切换：只切面板、不改 URL（§15.2）----
    {
      const tabState = () =>
        evaluate(`(() => ({
          sel: document.querySelector('#login-tab')?.getAttribute('aria-selected'),
          regSel: document.querySelector('#register-tab')?.getAttribute('aria-selected'),
          loginHidden: document.querySelector('#login-panel')?.hasAttribute('hidden'),
          regHidden: document.querySelector('#register-panel')?.hasAttribute('hidden'),
          path: location.pathname,
        }))()`)
      const beforeTab = await tabState()
      check('§15.2 默认选中「登录」Tab 且注册面板 hidden', beforeTab.sel === 'true' && beforeTab.regSel === 'false' && beforeTab.loginHidden === false && beforeTab.regHidden === true)
      await clickSelector('#register-tab')
      await sleep(120)
      const afterTab = await tabState()
      check('§15.2 切到注册：aria-selected 与面板显隐同步', afterTab.regSel === 'true' && afterTab.sel === 'false' && afterTab.loginHidden === true && afterTab.regHidden === false)
      check('§15.2 切 Tab 不改 URL', afterTab.path === beforeTab.path, `${beforeTab.path} → ${afterTab.path}`)
      check(
        '§15.5 注册面板字段齐全（4 个冻结 id + 提交按钮）',
        await evaluate(`['#register-account','#register-name','#register-password','#register-password2','#register-submit'].every((s) => !!document.querySelector(s))`),
      )
      await clickSelector('#login-tab')
      await sleep(120)
      const backTab = await tabState()
      check('§15.2 切回登录：恢复默认面板', backTab.sel === 'true' && backTab.regHidden === true && backTab.loginHidden === false)
    }

    if (LOGIN) {
      check('填入账号', await typeInto('#login-account', ACCOUNT), ACCOUNT)
      check('填入密码', await typeInto('#login-password', PASSWORD), '******')
      check('提交登录', await clickSelector('#login-submit'))
      // 等页面**离开** /login（登录是异步的：login → /me → replace）。
      let landed = '/login'
      try {
        landed = await waitFor(
          async () => {
            const p = await evaluate('location.pathname')
            return p !== '/login' ? p : false
          },
          { label: '登录后落地', timeoutMs: 20_000 },
        )
      } catch {
        landed = await evaluate('location.pathname')
      }
      check('登录后落到 /assistant（G7）', landed === '/assistant', `实际 ${landed}`)
      if (landed !== '/assistant') {
        // 失败诊断：只读，不代替用户操作（不得用脚本补一次 submit 把失败掩盖掉）。
        await sleep(300)
        const err = await evaluate("document.querySelector('[role=alert]')?.textContent?.trim() ?? ''")
        check('登录失败有可见原因', err.length > 0, err.slice(0, 120))
        console.log(`DEBUG 页面正文：${(await evaluate('document.body.innerText')).slice(0, 400).replace(/\n/g, ' / ')}`)
        console.log(`DEBUG /api 请求：${netLog.join(' | ') || '(无)'}`)
        console.log(`DEBUG 控制台 error：${consoleErrors.slice(-5).join(' | ') || '(无)'}`)
        console.log(`DEBUG 异常：${exceptions.slice(-3).join(' | ') || '(无)'}`)
      }
      const page = await evaluate(`(() => ({
        composer: !!document.querySelector('.composer textarea'),
        boundary: document.body.innerText.includes('对话只保存在当前浏览器标签页'),
        nav: !!document.querySelector('nav'),
        title: document.title,
      }))()`)
      check('助手页输入框存在（.composer textarea）', page.composer === true)
      check('S02 边界提示条逐字存在', page.boundary === true)
      check('导航外壳存在（nav）', page.nav === true)
      check('助手页 document.title', /· 校园课程智能助手$/.test(page.title ?? ''), page.title)

      // ---- 输入条改版（2026-10-26）：一体式 / 圆形发送按钮 / 冒泡提示 / 贴底 ----
      const composerShape = await evaluate(`(() => {
        const form = document.querySelector('.composer');
        const box = form && form.querySelector('.composer__box');
        const ta = form && form.querySelector('textarea');
        const send = form && form.querySelector('.composer__send');
        const btn = send && send.querySelector('button');
        const label = form && form.querySelector('label.field__label');
        if (!form || !box || !ta || !btn) return null;
        const br = btn.getBoundingClientRect();
        const cs = getComputedStyle(btn);
        return {
          onePiece: box.contains(ta) && box.contains(btn),
          counterInBox: box.contains(form.querySelector('.composer__count')),
          visibleLabel: label ? label.textContent.trim() : '',
          placeholder: ta.getAttribute('placeholder'),
          sendText: (btn.textContent || '').trim(),
          ariaLabel: btn.getAttribute('aria-label'),
          radius: cs.borderRadius,
          square: Math.abs(br.width - br.height) <= 1,
          size: Math.round(br.width),
          tip: send.getAttribute('data-tip'),
        };
      })()`)
      check(
        '输入条一体式：textarea / 字数 / 发送按钮同在一个 .composer__box',
        composerShape?.onePiece === true && composerShape.counterInBox === true,
        JSON.stringify(composerShape),
      )
      check(
        '「你的问题」由可见 label 改为 placeholder',
        composerShape?.visibleLabel === '' && composerShape?.placeholder === '你的问题',
        `label=「${composerShape?.visibleLabel}」placeholder=「${composerShape?.placeholder}」`,
      )
      check(
        '发送按钮：圆形、无文字、可访问名仍是「发送」',
        composerShape?.square === true &&
          composerShape?.radius === '999px' &&
          composerShape?.sendText === '' &&
          composerShape?.ariaLabel === '发送',
        `size=${composerShape?.size} radius=${composerShape?.radius} text=「${composerShape?.sendText}」arialabel=「${composerShape?.ariaLabel}」`,
      )
      check(
        '快捷键说明变成发送按钮的冒泡提示（data-tip）',
        composerShape?.tip === 'Enter 发送 · Shift+Enter 换行',
        `tip=「${composerShape?.tip}」`,
      )
      const tipHidden = await evaluate(`getComputedStyle(document.querySelector('.composer__send'), '::after').visibility`)
      const sendPoint = await evaluate(`(() => {
        const r = document.querySelector('.composer__send').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
      })()`)
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: sendPoint.x, y: sendPoint.y })
      await sleep(200)
      const tipShown = await evaluate(`getComputedStyle(document.querySelector('.composer__send'), '::after').visibility`)
      check('悬停发送按钮时冒泡提示出现（无 transition，visibility 切换）', tipHidden === 'hidden' && tipShown === 'visible', `${tipHidden} → ${tipShown}`)

      // 固定底部 + 整页一个滚动条 + 右栏悬浮（2026-10-26 布局改版）：
      // 输入条 `position: fixed` 浮在内容之上；页面本身只有**一个**滚动条，
      // 不再有「大滚动条里套一个小滚动条」的主列滚动区（`.workspace__scroll` 已删除）。
      const pinInfo = await evaluate(`(async () => {
        const form = document.querySelector('.composer');
        const main = document.querySelector('.workspace__main');
        const rail = document.querySelector('.workspace__rail');
        if (!form || !main) return null;
        const fb = () => form.getBoundingClientRect();
        const gap0 = Math.round(innerHeight - fb().bottom);
        const before = Math.round(fb().top);
        const inner = !!document.querySelector('.workspace__scroll');
        const mainOverflow = getComputedStyle(main).overflowY;
        const railPos = rail ? getComputedStyle(rail).position : null;
        const railTop = rail ? getComputedStyle(rail).top : null;
        const railTop0 = rail ? Math.round(rail.getBoundingClientRect().top) : null;
        // 往主列顶部灌 1500px 内容 → 文档变长，只有文档这一个滚动条能滚
        const fill = document.createElement('div');
        fill.style.height = '1500px';
        main.insertBefore(fill, main.firstChild);
        await new Promise((r) => setTimeout(r, 80));
        const grew = document.documentElement.scrollHeight > innerHeight + 1000;
        window.scrollTo(0, 900);
        await new Promise((r) => setTimeout(r, 120));
        const pageScroll = Math.round(window.scrollY);
        const after = Math.round(fb().top);
        const gap1 = Math.round(innerHeight - fb().bottom);
        const railTop1 = rail ? Math.round(rail.getBoundingClientRect().top) : null;
        fill.remove();
        window.scrollTo(0, 0);
        return { gap0, gap1, before, after, pageScroll, grew, inner, mainOverflow, railPos, railTop, railTop0, railTop1, vw: innerWidth, vh: innerHeight };
      })()`)
      check(
        '输入条 fixed 钉在视口底部（页面滚 900 也不动）',
        pinInfo?.before === pinInfo?.after &&
          pinInfo?.gap0 === pinInfo?.gap1 &&
          pinInfo?.pageScroll === 900 &&
          pinInfo?.grew === true,
        `top=${pinInfo?.before}→${pinInfo?.after} 距底=${pinInfo?.gap0}→${pinInfo?.gap1} scrollY=${pinInfo?.pageScroll} 文档变长=${pinInfo?.grew}`,
      )
      check(
        '整页只有一个滚动条：主列没有内部滚动区',
        pinInfo?.inner === false && pinInfo?.mainOverflow === 'visible',
        `.workspace__scroll=${pinInfo?.inner ? '仍存在' : '已删除'} 主列 overflow-y=${pinInfo?.mainOverflow}`,
      )
      check(
        '右栏悬浮：≥1200 时 position:sticky，页面滚动时吸在顶栏下',
        pinInfo?.vw < 1200 ||
          (pinInfo?.railPos === 'sticky' &&
            parseFloat(pinInfo?.railTop) > 0 &&
            Math.abs(pinInfo?.railTop1 - parseFloat(pinInfo?.railTop)) <= 1),
        `vw=${pinInfo?.vw} position=${pinInfo?.railPos} top=${pinInfo?.railTop} 栏顶 ${pinInfo?.railTop0}→${pinInfo?.railTop1}`,
      )
      const shot2 = await cdp.send('Page.captureScreenshot', { format: 'png' })
      savePng('smoke-assistant.png', shot2.data)
    }

    // ---- 7) 发一条提问，验证流式文本真的进了 DOM（--ask / --full）----
    if (ASK) {
      const focused = await evaluate(`(() => {
        const el = document.querySelector('.composer textarea');
        if (!el) return false;
        el.focus();
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, '');
        el.dispatchEvent(new Event('input', { bubbles: true }));
        return document.activeElement === el;
      })()`)
      if (focused) await cdp.send('Input.insertText', { text: ASK })
      const typed = focused && (await evaluate("document.querySelector('.composer textarea')?.value ?? ''")) === ASK
      check('填入提问', typed)
      const sent = await evaluate(`(() => {
        const btns = [...document.querySelectorAll('button')];
        const b = btns.find((x) => x.getAttribute('aria-label') === '发送' && !x.disabled);
        if (!b) return false;
        b.click();
        return true;
      })()`)
      check('点击发送', sent)
      const streamed = await waitFor(
        async () => {
          const r = await evaluate(`(() => {
            const chat = document.querySelector('.chat');
            return { chat: !!chat, len: chat ? chat.innerText.trim().length : 0 };
          })()`)
          return r.chat && r.len > 20 ? r : false
        },
        { label: 'SSE 文本流入 DOM', timeoutMs: 30_000 },
      )
      check('SSE 文本流入 DOM（.chat 有正文）', streamed.len > 20, `正文 ${streamed.len} 字`)
      // 等流式结束（"正在处理" 消失或终态出现）
      await waitFor(
        async () => {
          const t = await evaluate('document.body.innerText')
          return !t.includes('正在处理') ? true : false
        },
        { label: '流式终态', timeoutMs: 60_000 },
      ).catch(() => undefined)
      const after = await evaluate(`(() => ({
        text: document.querySelector('.chat')?.innerText?.trim() ?? '',
        citations: document.querySelectorAll('[class*=cite]').length,
      }))()`)
      check('回答正文非空', after.text.length > 10, `${after.text.length} 字`)
      const shot3 = await cdp.send('Page.captureScreenshot', { format: 'png' })
      savePng('smoke-assistant-answer.png', shot3.data)

      // ---- 7b) --full：第二轮「资料问句」→ 真实引用卡 → 展开片段（F6）----
      if (FULL) {
        const docQuestion = process.env.E2E_CHAT_DOC_MESSAGE ?? '实验课预习要求是什么？'
        const focused2 = await evaluate(`(() => {
          const el = document.querySelector('.composer textarea');
          if (!el) return false;
          el.focus();
          Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(el, '');
          el.dispatchEvent(new Event('input', { bubbles: true }));
          return document.activeElement === el;
        })()`)
        if (focused2) await cdp.send('Input.insertText', { text: docQuestion })
        check('第二轮：填入资料问句', focused2)
        check(
          '第二轮：发送',
          await evaluate(`(() => {
            const b = [...document.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === '发送' && !x.disabled);
            if (!b) return false;
            b.click();
            return true;
          })()`),
        )
        const citeCount = await waitFor(
          async () => {
            const n = await evaluate("document.querySelectorAll('.cite').length")
            return n > 0 ? n : false
          },
          { label: '引用卡出现', timeoutMs: 60_000 },
        )
        check('真实引用卡渲染（.cite）', citeCount > 0, `${citeCount} 张`)
        // 展开第一张引用的片段（真实 GET /citations/{id}）
        const expanded = await evaluate(`(() => {
          const card = document.querySelector('.cite');
          if (!card) return false;
          const b = [...card.querySelectorAll('button')].find((x) => x.textContent.trim() === '展开片段');
          if (!b) return false;
          b.click();
          return true;
        })()`)
        check('点击「展开片段」', expanded)
        let snippet = ''
        try {
          snippet = await waitFor(
            async () => {
              const t = await evaluate("document.querySelector('.cite__body')?.innerText?.trim() ?? ''")
              return t.length > 10 ? t : false
            },
            { label: '引用片段正文', timeoutMs: 30_000 },
          )
        } catch {
          snippet = ''
        }
        check('引用片段正文展开（.cite__body）', snippet.length > 10, `${snippet.length} 字`)
        const invalidShown = await evaluate(
          "document.body.innerText.includes('这条引用已失效')",
        )
        check('引用未显示失效文案（410 未发生）', invalidShown === false)
        const shot4 = await cdp.send('Page.captureScreenshot', { format: 'png' })
        savePng('smoke-assistant-citations.png', shot4.data)
      }
    }

    // ---- 8) 逐屏 UI 走查（--pages）：学生课表/计划（含 UI 新建+删除）→ 管理员课程 ----
    if (PAGES) {
      const waitPath = (expected, label = expected) =>
        waitFor(
          async () => {
            const p = await evaluate('location.pathname')
            return p === expected ? p : false
          },
          { label: `导航到 ${label}`, timeoutMs: 15_000 },
        )
      const bodyText = () => evaluate('document.body.innerText')

      // 8.1 S07 我的课表：真实数据渲染
      await clickNav('我的课表')
      await waitPath('/me/schedules')
      let n = 0
      try {
        n = await waitFor(async () => {
          const c = await rows()
          return c > 0 ? c : false
        }, { label: '课表行', timeoutMs: 10_000 })
      } catch {
        n = await rows()
      }
      const scheduleText = await bodyText()
      check('S07 我的课表渲染真实课表行', n > 0, `${n} 行`)
      check('S07 未把「读取失败」与「当天无课」混为一谈', !scheduleText.includes('无法读取'), '')
      // 统计条 4 卡各带一个 20×20 装饰图标（`.stat__ico` 内含 svg，aria-hidden）
      const statIcons = await evaluate(`(() => {
        const cards = [...document.querySelectorAll('.stat')];
        const icos = cards.map((c) => {
          const ico = c.querySelector('.stat__ico');
          const svg = ico && ico.querySelector('svg');
          return ico ? { hidden: ico.getAttribute('aria-hidden'), paths: svg ? svg.querySelectorAll('path').length : 0 } : null;
        });
        return { cards: cards.length, icos };
      })()`)
      check(
        '课表统计条 4 卡各带 1 个装饰图标',
        statIcons?.cards === 4 && statIcons.icos.every((i) => i && i.hidden === 'true' && i.paths > 0),
        JSON.stringify(statIcons),
      )
      // P5b 裁决 B1：表格 <caption> 与卡头标题逐字重复（8 个调用点都传卡头标题）。
      // 处理：caption 加 `.sr-only` 视觉隐藏、留在 DOM 里当表格的可访问名。
      // 这里同时钉住三件事：不占布局、隐藏的确实是重复内容、读屏仍拿得到表格名。
      const capInfo = await evaluate(`(() => {
        const cap = document.querySelector('.table caption');
        if (!cap) return { present: false };
        const r = cap.getBoundingClientRect();
        const s = getComputedStyle(cap);
        const head = cap.closest('.card')?.querySelector('.card__head');
        const text = (cap.textContent || '').trim();
        const headText = head ? (head.textContent || '').trim() : '';
        // 命中测试：被 clip 裁掉的元素不可能成为某点的最上层元素 —— 与 padding 造成的盒尺寸无关
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return {
          present: true, text, headText,
          w: Math.round(r.width), h: Math.round(r.height),
          position: s.position, clip: s.clip,
          hitIsCaption: hit === cap || (!!hit && cap.contains(hit)),
          duplicate: headText.includes(text),
        };
      })()`)
      const fullyClipped = /^rect\(\s*0(px)?,?\s*0(px)?,?\s*0(px)?,?\s*0(px)?\s*\)$/.test(capInfo?.clip ?? '')
      check(
        'B1 caption 视觉隐藏（.sr-only：绝对定位 + 全裁 + 点不中）',
        capInfo?.present === true &&
          capInfo.position === 'absolute' &&
          fullyClipped &&
          capInfo.hitIsCaption === false,
        `rect=${capInfo?.w}×${capInfo?.h} position=${capInfo?.position} clip=${capInfo?.clip} hitIsCaption=${capInfo?.hitIsCaption}`,
      )
      check(
        'B1 caption 隐藏的正是卡头标题（重复而非信息）',
        capInfo?.duplicate === true,
        `caption=「${capInfo?.text}」cardHead=「${capInfo?.headText}」`,
      )
      const axTableName = await (async () => {
        try {
          const doc = await cdp.send('DOM.getDocument', { depth: 0 })
          const q = await cdp.send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: '.table' })
          const ax = await cdp.send('Accessibility.getPartialAXTree', { nodeId: q.nodeId, fetchRelatives: false })
          const t = (ax.nodes ?? []).find((x) => x.role?.value === 'table' || x.role?.value === 'grid')
          return t?.name?.value ?? ''
        } catch (e) {
          return `ERR ${e.message}`
        }
      })()
      check('B1 caption 仍是表格的可访问名（读屏可读）', axTableName === capInfo?.text, `AX name=「${axTableName}」`)
      savePng('pages-schedules.png', (await cdp.send('Page.captureScreenshot', { format: 'png' })).data)

      // 8.2 S09 学习计划列表
      await clickNav('学习计划')
      await waitPath('/me/plans')
      const planRows = await (async () => {
        try {
          return await waitFor(async () => {
            const c = await rows()
            return c > 0 ? c : false
          }, { label: '计划行', timeoutMs: 10_000 })
        } catch {
          return rows()
        }
      })()
      check('S09 学习计划列表渲染（种子计划）', planRows > 0, `${planRows} 行`)

      // 8.3 S09 新建表单展开 + 输入 + 取消（**不提交**）
      // 写路径（创建/删除/409）由 e2e-real.mjs 的 HTTP 级断言覆盖：UI 写操作要等列表重载，
      // 在无头浏览器里时序不稳，把 flaky 当证据比不测更糟。
      check('S09 打开新建表单（「新建计划」）', await clickByText('新建计划'))
      await sleep(250)
      const formOpen = await evaluate("!!document.querySelector('#plan-title')")
      check('S09 新建表单已展开（#plan-title 出现）', formOpen === true)
      if (formOpen) {
        check('S09 填标题', await typeInto('#plan-title', 'E2E 浏览器计划（不提交）'))
        check('S09 填正文', await typeInto('#plan-content', '仅验证前端表单可输入，不落库。'))
        check('S09 取消', await clickByText('取消'))
        const closed = !(await evaluate("!!document.querySelector('#plan-title')"))
        check('S09 取消后表单收起（不产生写入）', closed)
      }
      savePng('pages-plans.png', (await cdp.send('Page.captureScreenshot', { format: 'png' })).data)

      // 8.4 G8 登出 → 回登录页
      // 阶段 B 起「退出登录」**只**在用户菜单里（默认不可见），必须先展开菜单再点。
      check('G8 打开用户菜单', await evaluate(`(() => {
        const t = document.querySelector('.usermenu__trigger')
        if (!t) return false
        t.click()
        return true
      })()`))
      await sleep(200)
      check(
        'G8 菜单已展开（aria-expanded=true）',
        (await evaluate(`document.querySelector('.usermenu__trigger')?.getAttribute('aria-expanded')`)) === 'true',
      )
      check('G8 菜单内「退出登录」', await clickByText('退出登录'))
      await waitPath('/login', '登录页')
      check('G8 登出后回到 /login', (await evaluate('location.pathname')) === '/login')

      // 8.5 管理员登录 → 管理中心 · 课程管理（S10）
      let adminLanded = ''
      try {
        adminLanded = await loginAs(ADMIN_ACCOUNT, ADMIN_PASSWORD)
      } catch {
        adminLanded = await evaluate('location.pathname')
      }
      check('管理员登录落地 /assistant', adminLanded === '/assistant', adminLanded)
      const adminNav = await evaluate(
        `[...document.querySelectorAll('nav a')].some((a) => a.textContent.trim() === '管理中心')`,
      )
      check('管理员可见「管理中心」入口', adminNav === true)
      if (adminNav) {
        await clickNav('管理中心')
        await waitPath('/admin/courses')
        let courseRows = 0
        try {
          courseRows = await waitFor(async () => {
            const c = await rows()
            return c > 0 ? c : false
          }, { label: '课程行', timeoutMs: 10_000 })
        } catch {
          courseRows = await rows()
        }
        const courseText = await bodyText()
        check('S10 课程列表渲染', courseRows > 0, `${courseRows} 行`)
        check('S10 列表包含种子课程 CS101', courseText.includes('CS101'))
        // 8.6 S10 新建表单展开 + 取消（**不提交**，避免在演示库留下不可删除的 disabled 课程；
        //      创建/编辑/启停的契约行为由 e2e-real.mjs 的 HTTP 级断言覆盖）
        const uiCode = `E2EUI-${Date.now().toString(36)}`.toUpperCase()
        check('S10 打开「新建课程」', await clickByText('新建课程'))
        check('S10 填课程代码', await typeInto('#course-code', uiCode))
        check('S10 填课程名称', await typeInto('#course-name', 'E2E 浏览器课程（不提交）'))
        check('S10 取消', await clickByText('取消'))
        await sleep(250)
        const stillAbsent = !(await bodyText()).includes(uiCode)
        check('S10 取消后未创建课程（列表无该代码）', stillAbsent)
        savePng('pages-admin-courses.png', (await cdp.send('Page.captureScreenshot', { format: 'png' })).data)

        // ---- 8.6.1 管理中心二级导航：4 个管理页都必须能在应用内到达 ----
        // 此前顶栏只有「管理中心」一个入口（落到 /admin/courses），另外三页只能手输 URL。
        // 选择器限定在**卡片内的 nav**：顶栏一级导航与底部标签栏也指向 /admin/*，不限定会混淆。
        const ADMIN_NAV_SCOPE = '.card__body nav a'
        const adminLinks = await evaluate(`(() => [...document.querySelectorAll(${JSON.stringify(ADMIN_NAV_SCOPE)})]
          .map((a) => ({ label: a.textContent.trim(), href: a.getAttribute('href'), current: a.getAttribute('aria-current') })))()`)
        check(
          '管理中心二级导航 4 项齐全',
          Array.isArray(adminLinks) && adminLinks.length === 4 && adminLinks.every((l) => l.label && l.href),
          JSON.stringify(adminLinks?.map((l) => l.label)),
        )
        check(
          '二级导航当前项标记（课程管理 aria-current=page）',
          adminLinks?.find((l) => l.href === '/admin/courses')?.current === 'page',
        )
        /** 点二级导航里的某一项（限定卡片内的 nav）。 */
        const clickAdminLink = async (label) => {
          const ok = await evaluate(`(() => {
            const a = [...document.querySelectorAll(${JSON.stringify(ADMIN_NAV_SCOPE)})].find((x) => x.textContent.trim() === ${JSON.stringify(label)});
            if (!a) return false;
            a.click();
            return true;
          })()`)
          await sleep(900)
          return ok
        }
        for (const [label, path] of [
          ['学生账号', '/admin/students'],
          ['课表维护', '/admin/schedules'],
          ['文档与批次', '/admin/documents'],
        ]) {
          const clicked = await clickAdminLink(label)
          let landed = await evaluate('location.pathname')
          try {
            landed = await waitFor(async () => {
              const p = await evaluate('location.pathname')
              return p === path ? p : false
            }, { label: `二级导航 → ${path}`, timeoutMs: 8_000 })
          } catch {
            /* 保留实际路径用于断言失败信息 */
          }
          const current = await evaluate(`(() => {
            const a = [...document.querySelectorAll(${JSON.stringify(ADMIN_NAV_SCOPE)})].find((x) => x.getAttribute('aria-current') === 'page');
            return a ? a.getAttribute('href') : null;
          })()`)
          check(`二级导航「${label}」→ ${path}`, clicked && landed === path, `${landed}`)
          check(`二级导航「${label}」标记为当前页`, current === path, String(current))

          // 8.6b 文档页：拖放区（E4）= `.empty` 虚线区 + upload 图标 + 「选择文件」，
          // 拖入时由 JS 切 `.empty--over`（不是 :hover，白名单里没有 :drag-over）。
          if (path === '/admin/documents') {
            const zone = await evaluate(`(() => {
              const el = document.querySelector('.card__body .empty');
              const btn = el && [...el.querySelectorAll('button')].find((b) => b.textContent.trim() === '选择文件');
              return el ? { art: el.querySelectorAll('.empty__art svg path').length, hasBtn: !!btn, dashed: getComputedStyle(el).borderTopStyle } : null;
            })()`)
            check(
              '文档页上传区 = 拖放区（虚线 .empty + upload 图标 + 选择文件）',
              !!zone && zone.art > 0 && zone.hasBtn === true && zone.dashed === 'dashed',
              JSON.stringify(zone),
            )
            const over = await evaluate(`(async () => {
              const el = document.querySelector('.card__body .empty');
              if (!el) return null;
              const tick = () => new Promise((r) => setTimeout(r, 60));
              const dt = new DataTransfer();
              el.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }));
              await tick();
              const on = { cls: el.classList.contains('empty--over'), style: getComputedStyle(el).borderTopStyle };
              el.dispatchEvent(new DragEvent('dragleave', { bubbles: true, cancelable: true, dataTransfer: dt }));
              await tick();
              const off = el.classList.contains('empty--over');
              return { on: on.cls && on.style === 'solid', off };
            })()`)
            check('拖入时虚线转实线（.empty--over），离开后复原', over?.on === true && over?.off === false, JSON.stringify(over))

            // 8.6c 真 drop：构造带文件的 DataTransfer 派发 `drop`，断言上传请求**真的发出**。
            // 用 Fetch 域拦在请求阶段并立即 Abort —— 证明「拖放 → 上传」这条链路通，同时**不写库**。
            let pausedReq = null
            cdp.on('Fetch.requestPaused', (p) => {
              if (!pausedReq && p.request?.url?.includes('/admin/document-batches')) pausedReq = p
            })
            await cdp.send('Fetch.enable', {
              patterns: [{ urlPattern: '*/api/v1/admin/document-batches*', requestStage: 'Request' }],
            })
            const dispatched = await evaluate(`(() => {
              const el = document.querySelector('.card__body .empty');
              if (!el) return false;
              const dt = new DataTransfer();
              dt.items.add(new File(['e2e drop probe —— 只验证请求发出，不落库'], 'e2e-drop-probe.txt', { type: 'text/plain' }));
              el.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt }));
              return true;
            })()`)
            for (let i = 0; i < 60 && !pausedReq; i++) await sleep(100)
            const probe = pausedReq
              ? { method: pausedReq.request.method, url: pausedReq.request.url.replace(/^https?:\/\/[^/]+/, '') }
              : null
            if (pausedReq) await cdp.send('Fetch.failRequest', { requestId: pausedReq.requestId, errorReason: 'Aborted' })
            await cdp.send('Fetch.disable')
            await sleep(300)
            check(
              '拖入文件即发出上传请求（拦截后立即中止，不落库）',
              dispatched === true && probe?.method === 'POST' && probe.url.includes('/admin/document-batches'),
              JSON.stringify(probe),
            )
          }
        }
        await clickAdminLink('课程管理')
        await waitPath('/admin/courses')
        savePng('pages-admin-students.png', (await cdp.send('Page.captureScreenshot', { format: 'png' })).data)
      }
      // 8.7 最终控制台复查
      await sleep(300)
      const ignore2 = /favicon|net::ERR_|Failed to load resource/i
      const real2 = consoleErrors.filter((e) => !ignore2.test(e))
      check('逐屏走查后控制台仍无 error', real2.length === 0, real2.slice(0, 3).join(' | '))
      check('逐屏走查无未捕获异常', exceptions.length === 0, exceptions.slice(0, 2).join(' | '))
    }

    if (FULL) {
      console.log('INFO  --full 其余链路（引用展开 / 草稿保存 / 课表 / 计划 / 管理中心）由 e2e-real.mjs 覆盖')
    }
  } finally {
    cdp.close()
    try {
      proc.kill()
    } catch {
      /* ignore */
    }
    await sleep(200)
    try {
      fs.rmSync(profile, { recursive: true, force: true })
    } catch {
      /* Windows 上偶发占用；临时目录可留 */
    }
  }
  return finish()
}

function finish() {
  const failed = results.filter((r) => !r.ok)
  console.log(`\n== 结果：${results.length - failed.length}/${results.length} PASS ==`)
  if (failed.length > 0) {
    console.log('失败项：')
    for (const f of failed) console.log(`  - ${f.name}: ${f.detail}`)
    process.exitCode = 1
  }
  return failed.length
}

main().catch((e) => {
  console.error(`FAIL  冒烟脚本异常：${e.stack ?? e.message}`)
  process.exitCode = 1
})
