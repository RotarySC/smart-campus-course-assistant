/**
 * stylelint 配置（前端详细设计 §8.2；路径由 CONTRACT §3.2 冻结为 `web/.stylelintrc.cjs`）。
 *
 * 规则实现见 `./stylelint-rules/layer-purity.cjs`。
 * `.vue` 用 `postcss-html` 解析 `<style>` 块。
 */
module.exports = {
  plugins: ['./stylelint-rules/layer-purity.cjs'],
  ignoreFiles: [
    'src/styles/tokens.css', // 生成物：它本身就是声明层，由 design/system/verify-system.py 校验
    'dist/**',
    'node_modules/**',
  ],
  rules: {
    // ① 禁裸 hex / 命名色 / rgb()/rgba()/hsl()
    'dsh/no-raw-color': true,
    // ② 禁带单位裸长度；白名单只放结构性 0/1px/100%/auto/none
    'dsh/no-raw-length': [true, { allow: ['0', '0px', '1px', '100%', 'auto', 'none'] }],
    // ③ 层纯度：组件样式（src/components/**、src/styles/base.css）禁消费 L1/L2/L0
    'dsh/layer-purity': [
      true,
      {
        scope: ['src/components/', 'src/styles/base.css'],
        forbidPrefixes: [
          '--p-', '--bg-', '--text-', '--accent', '--state-', '--border', '--danger-border', '--pending',
          '--layout-', '--shell-', '--elevation-', '--motion-', '--focus-ring-', '--size-',
        ],
        allow: [
          '--root-', '--wrap-', '--card-', '--btn-', '--pill-', '--notice-', '--chat-', '--msg-', '--bubble-',
          '--steps-', '--step-', '--composer-', '--cite-', '--draft-', '--empty-', '--field-', '--control-',
          '--errorsummary-', '--table-', '--kv-', '--chip-', '--chips-', '--prose-', '--login-', '--stack-',
          '--row-', '--muted-', '--small-', '--appbar-', '--brand-', '--navlink-', '--tabbar-', '--skiplink-',
          '--sr-', '--focus-outline-',
        ],
      },
    ],
    // ④ 状态白名单：出现 :active / transition 即 FAIL；animation 白名单到精确一处
    'dsh/no-unknown-state': true,
    // ⑤ 断点字面量只允许 tokens.json 的 6 档及其 min−1
    'dsh/breakpoint-whitelist': true,
  },
  overrides: [
    {
      files: ['**/*.vue'],
      customSyntax: 'postcss-html',
    },
  ],
}
