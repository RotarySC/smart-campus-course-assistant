/**
 * 鉴权端点封装。函数名 = `openapi` 的 `operationId`（§2.4）。
 * `api/**` 不得 import `stores/**`（§2.2 R2）—— 令牌由参数注入。
 */

import type { AuthSnapshot } from './client'
import { request } from './client'
import type { Login, User } from './types'

export interface LoginInput {
  account: string
  password: string
}

/** `POST /api/v1/auth/login`（operationId `login`） */
export function login(input: LoginInput): Promise<Login> {
  return request<Login>({
    method: 'POST',
    path: '/auth/login',
    body: { account: input.account, password: input.password },
  })
}

/**
 * `POST /api/v1/auth/register`（operationId `register`）的自助注册入参。
 * 与 openapi `RegisterInput` 逐字段对应；`role` 不在入参里（管理员账号不可自助注册）。
 */
export interface RegisterInput {
  account: string
  display_name: string
  password: string
}

/**
 * `POST /api/v1/auth/register`：201 + 与登录同结构的 `Envelope[Login]`（注册即自动登录）。
 * `DUPLICATE_ACCOUNT`(409) / `VALIDATION_FAILED`(422) 由调用方按 `field_errors[]` 就近回填。
 */
export function register(input: RegisterInput): Promise<Login> {
  return request<Login>({
    method: 'POST',
    path: '/auth/register',
    body: {
      account: input.account,
      display_name: input.display_name,
      password: input.password,
    },
  })
}

/**
 * `POST /api/v1/auth/logout`（operationId `logout`）
 * 幂等：无论响应如何，调用方都要完成 §4.5 的第 4–7 步（清空 + 跳登录）。
 */
export function logout(auth: AuthSnapshot): Promise<Record<string, never>> {
  return request<Record<string, never>>({ method: 'POST', path: '/auth/logout', auth })
}

/** 返回体里唯一会被前端保留的身份字段（不回写令牌：`/me` 响应不含令牌）。 */
export type { User }
