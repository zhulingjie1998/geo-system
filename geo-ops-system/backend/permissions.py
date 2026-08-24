"""permissions.py — 中央权限注册表

后端权限校验、前端菜单渲染、角色管理 UI 的勾选框 都从这里读，
确保「页面 key、中文名、分组」全系统单一真相源。

新增页面时只需要在 PAGE_REGISTRY 加一行；前端 / 后端 / DB 不需要再改。

数据范围（data_scope）不在这里，是 role 表的独立字段：
  - all  : 看团队全部数据
  - self : 仅看自己 owner_id 的数据
"""
from __future__ import annotations

# (page_key, 中文名, 分组)
# 顺序就是 UI 上的展示顺序
PAGE_REGISTRY: list[tuple[str, str, str]] = [
    # —— 业务功能 ——
    ("home",                "首页",            "业务功能"),
    ("accounts",            "客户管理",        "业务功能"),
    ("keyword-search",      "查词管理",        "业务功能"),
    ("geo-expansion",       "GEO拓词",         "业务功能"),
    ("publish-customers",   "内容发布",        "业务功能"),

    # —— 系统管理 ——（高危）
    ("admin-users",         "账号管理",        "系统管理"),
    ("roles",               "角色管理",        "系统管理"),
    ("settings",            "系统设置",        "系统管理"),
]

# 派生数据
PAGE_KEYS: list[str] = [k for k, _, _ in PAGE_REGISTRY]
PAGE_LABEL: dict[str, str] = {k: l for k, l, _ in PAGE_REGISTRY}
PAGE_GROUPS: dict[str, list[dict]] = {}
for k, label, group in PAGE_REGISTRY:
    PAGE_GROUPS.setdefault(group, []).append({"key": k, "label": label})


def is_valid_page_key(k: str) -> bool:
    return k in PAGE_LABEL


def filter_valid_keys(keys: list) -> list[str]:
    """过滤掉 registry 不认识的 key（来自旧数据、前端误传）。"""
    if not isinstance(keys, list):
        return []
    return [k for k in keys if isinstance(k, str) and k in PAGE_LABEL]


# 数据范围（role.data_scope 字段的可选值）
DATA_SCOPE_ALL = "all"
DATA_SCOPE_TEAM = "team"
DATA_SCOPE_SELF = "self"
VALID_DATA_SCOPES = (DATA_SCOPE_ALL, DATA_SCOPE_TEAM, DATA_SCOPE_SELF)


# 内置角色 code（不可删除/不可改 code）
BUILTIN_ROLE_CODES = ("super_admin", "admin", "operator")
SUPER_ADMIN_CODE = "super_admin"
