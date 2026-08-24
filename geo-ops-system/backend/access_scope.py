"""access_scope.py — 数据可见性(RBAC data_scope)的【单一可信源】。

所有「按客户归属隔离」的业务模块(内容库 / 拓词 / 知识库 / 客户 / 查词 / 排名 / 报告 /
生文 / 发布 …)对数据范围的判定都必须经由本模块,严禁各路由各写一套,以防口径漂移。

三态(取 admin_user 所属 role.data_scope,登录时写入 session["data_scope"]):
  - all  → 超级管理员,看全部
  - team → 团队负责人,看本团队(account.team_id)下的全部客户
  - self → 运营人员,看自己被指派(account_owner 多对多)的客户

设计约束:
  - 只依赖 flask.session + db,不被 db 反向依赖 → 无循环导入。
  - account_id 为锚点;某资源 account_id 为空(如未绑定客户的拓词任务)时,
    归属判断退回「创建者本人 + 超管」,由各模块用 can_access_orphan() 处理。
"""
from __future__ import annotations

from flask import session

import db


def data_scope() -> str:
    """当前会话的数据范围;缺省按最严的 self 处理。"""
    return session.get("data_scope") or "self"


def current_user_id():
    return session.get("user_id")


def is_full_view() -> bool:
    """超管看全部。data_scope='all' 或 super_admin 角色(无论其 data_scope 配置)均放行,
    避免超管因 data_scope 未配成 all 而被误挡(如延长报告有效期报"无权限")。"""
    if session.get("is_super_admin") or session.get("role") == "super_admin":
        return True
    return data_scope() == "all"


def account_scope_kwargs() -> dict:
    """传给 db.list_accounts() 的可见性参数:
      all  → {}            (无过滤,看全部)
      team → {team_id}     (本团队;未绑团队则退化为只看自己,避免误看全部)
      self → {owner_id}    (自己被指派的)
    """
    ds = data_scope()
    if ds == "all":
        return {}
    if ds == "team":
        tid = session.get("team_id")
        return {"team_id": tid} if tid else {"owner_id": session.get("user_id")}
    return {"owner_id": session.get("user_id")}


def accessible_account_ids():
    """当前用户可见的 account_id 集合。

    返回 None 表示「全部」(超管);否则返回 set[int](可能为空集 = 看不到任何客户)。
    含临时号(自己名下的),以兼容拓词等先建号后转正的流程。
    """
    if is_full_view():
        return None
    accs = db.list_accounts(include_temp=True, **account_scope_kwargs())
    return {int(a["id"]) for a in accs}


def can_access_account(account_id) -> bool:
    """当前用户能否访问该客户的数据。

    account_id 为空:仅超管可见(孤儿资源的创建者豁免请用 can_access_orphan)。
    """
    if account_id in (None, "", 0, "0"):
        return is_full_view()
    if is_full_view():
        return True
    ids = accessible_account_ids()
    return ids is not None and int(account_id) in ids


def can_access_orphan(account_id, created_by) -> bool:
    """未绑定客户(account_id 为空)的资源:创建者本人或超管可访问;
    已绑定客户的资源:按 can_access_account 判定。"""
    if account_id in (None, "", 0, "0"):
        if is_full_view():
            return True
        uid = current_user_id()
        return uid is not None and created_by is not None and int(created_by) == int(uid)
    return can_access_account(account_id)


def filter_accounts(items, *keys):
    """把 dict 列表按可见的 account_id 过滤。keys 为候选字段名(兼容 snake/camel)。
    超管直接原样返回。"""
    ids = accessible_account_ids()
    if ids is None:
        return list(items)

    def _aid(it):
        for k in keys:
            if k in it and it[k] not in (None, ""):
                return it[k]
        return None

    out = []
    for it in items:
        aid = _aid(it)
        if aid is not None and int(aid) in ids:
            out.append(it)
    return out
