/** auth.ts — 认证状态工具函数（独立文件，避免循环依赖） */
let authChecked = false
let authOk = false
let isSuperAdmin = false

export function getAuthState() {
  return { authChecked, authOk, isSuperAdmin }
}

export function setAuthState(checked, ok, superAdmin) {
  authChecked = checked
  authOk = ok
  isSuperAdmin = superAdmin
}

/** 重置认证状态（用于登出/401） */
export function resetAuthState() {
  authChecked = false
  authOk = false
  isSuperAdmin = false
}
