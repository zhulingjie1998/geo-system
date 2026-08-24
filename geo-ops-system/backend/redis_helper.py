"""redis_helper.py — Redis 抽象层 + feature flag + 自动降级

设计原则：
  1. 所有 Redis 操作都走 safe_*()，永不抛异常（异常时返回 sane default）。
  2. feature flag `redis_enabled` 全局开关，OFF 时所有 safe_* 走 fast-path no-op，
     业务代码不需要改 if 判断。
  3. lazy connection — 首次调用才连，避免 import 时副作用。
  4. 统一命名空间前缀 `geo:` —— 生产 Redis 与其他业务（dream:session）共享，
     必须隔离。
  5. 跨进程共享：gunicorn worker / scheduler_daemon 全用同一个 Redis 实例。

环境变量配置（.env 已添加）：
  GEO_REDIS_HOST  默认 127.0.0.1
  GEO_REDIS_PORT  默认 6379
  GEO_REDIS_DB    默认 0
  GEO_REDIS_ENABLED  默认 "false"（feature flag，可在 system_setting 表覆盖）

system_setting key（运行时可改，super_admin 用）：
  redis_enabled   "true" / "false"
  redis_inflight_enabled   "true" / "false"  （Stage 2.2 切换）
  redis_concurrency_enabled  "true" / "false"  （Stage 2.3 切换）
  redis_token_bucket_enabled  "true" / "false"  （Stage 2.4 切换）
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("redis_helper")

# 命名空间前缀 — 必须用，避免与 Redis 上其他业务冲突
NS = "geo:"

# 模块级单例，lazy init
_client = None
_client_lock = None


def _get_client():
    """惰性初始化 Redis 连接。任何错误返回 None，调用方降级。"""
    global _client, _client_lock
    if _client is not None:
        return _client
    if _client_lock is None:
        import threading
        _client_lock = threading.Lock()
    with _client_lock:
        if _client is not None:
            return _client
        try:
            import redis
            host = os.environ.get("GEO_REDIS_HOST", "127.0.0.1")
            port = int(os.environ.get("GEO_REDIS_PORT", "6379"))
            db = int(os.environ.get("GEO_REDIS_DB", "0"))
            c = redis.Redis(
                host=host, port=port, db=db,
                decode_responses=True,
                socket_timeout=2,           # 短超时避免阻塞业务
                socket_connect_timeout=2,
                health_check_interval=30,
            )
            c.ping()  # eager check 一次，失败立刻降级
            _client = c
            logger.info("[redis] connected to %s:%s db=%s", host, port, db)
            return _client
        except Exception:
            logger.warning("[redis] init failed, all calls will no-op", exc_info=True)
            _client = None
            return None


# ─── Feature Flag ───────────────────────────────────────────────────────────

def is_enabled(flag: str = "redis_enabled") -> bool:
    """检查 feature flag。
    优先级：system_setting > env GEO_REDIS_ENABLED > 默认 False
    各子项（inflight / concurrency / token_bucket）有独立 flag，
    任一开启都需要先 redis_enabled=true 总开关。
    """
    # 先看总开关
    if flag != "redis_enabled":
        if not _read_flag("redis_enabled"):
            return False
    return _read_flag(flag)


def feature_flag(key: str) -> bool:
    """纯代码行为开关（不依赖 Redis 数据，不受 redis_enabled 总开关约束）。
    用于 P1-P6 这类"是否启用某段优化代码路径"的开关，与 is_enabled
    （Redis 功能开关，需总开关）语义区分。读 system_setting + GEO_ env，默认 False。
    """
    return _read_flag(key)


def _read_flag(key: str) -> bool:
    """读 system_setting 表 + env fallback。不抛异常。"""
    try:
        import db
        v = db.get_setting(key, "") or ""
        if v.lower() in ("true", "1", "yes", "on"):
            return True
        if v.lower() in ("false", "0", "no", "off", ""):
            # 未设置或显式 false → 查 env
            env_key = "GEO_" + key.upper()
            ev = os.environ.get(env_key, "").lower()
            return ev in ("true", "1", "yes", "on")
    except Exception:
        # DB 故障时也别影响 — 直接走默认 False
        return False
    return False


# ─── 安全包装：所有错误返回 sane default ────────────────────────────────────

def safe_get(key: str, default: Any = None) -> Any:
    if not is_enabled():
        return default
    c = _get_client()
    if c is None:
        return default
    try:
        v = c.get(NS + key)
        return v if v is not None else default
    except Exception:
        logger.debug("[redis] get %s failed", key, exc_info=True)
        return default


def safe_set(key: str, value: Any, ex: Optional[int] = None) -> bool:
    if not is_enabled():
        return False
    c = _get_client()
    if c is None:
        return False
    try:
        return bool(c.set(NS + key, value, ex=ex))
    except Exception:
        logger.debug("[redis] set %s failed", key, exc_info=True)
        return False


def safe_set_nx(key: str, value: Any, ex: int) -> bool:
    """原子 SET if-Not-eXists + TTL。返回 True=抢到（key 原不存在），
    False=已存在（别人持有）或 Redis 不可用。用于分布式短锁（P6 continue 去重）。
    注意：Redis 不可用时返回 False（保守：拿不到锁就不执行被保护操作；
    但调用方对"锁失败"的处理应是 fail-open 还是 fail-closed 由其自行决定）。
    """
    if not is_enabled():
        return False
    c = _get_client()
    if c is None:
        return False
    try:
        return bool(c.set(NS + key, value, nx=True, ex=int(ex)))
    except Exception:
        logger.debug("[redis] set_nx %s failed", key, exc_info=True)
        return False


def safe_delete(*keys: str) -> int:
    if not is_enabled() or not keys:
        return 0
    c = _get_client()
    if c is None:
        return 0
    try:
        return int(c.delete(*[NS + k for k in keys]))
    except Exception:
        logger.debug("[redis] delete failed", exc_info=True)
        return 0


def safe_incr(key: str, amount: int = 1, default: int = 0) -> int:
    if not is_enabled():
        return default
    c = _get_client()
    if c is None:
        return default
    try:
        return int(c.incrby(NS + key, amount))
    except Exception:
        logger.debug("[redis] incr %s failed", key, exc_info=True)
        return default


def safe_decr(key: str, amount: int = 1, default: int = 0) -> int:
    if not is_enabled():
        return default
    c = _get_client()
    if c is None:
        return default
    try:
        return int(c.decrby(NS + key, amount))
    except Exception:
        logger.debug("[redis] decr %s failed", key, exc_info=True)
        return default


def safe_get_int(key: str, default: int = 0) -> int:
    v = safe_get(key, None)
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def safe_expire(key: str, seconds: int) -> bool:
    if not is_enabled():
        return False
    c = _get_client()
    if c is None:
        return False
    try:
        return bool(c.expire(NS + key, seconds))
    except Exception:
        return False


# ─── Hash 操作（inflight 用）────────────────────────────────────────────────

def safe_hset(key: str, field: str, value: Any) -> bool:
    if not is_enabled():
        return False
    c = _get_client()
    if c is None:
        return False
    try:
        c.hset(NS + key, field, value)
        return True
    except Exception:
        return False


def safe_hgetall(key: str, default: Optional[dict] = None) -> dict:
    if default is None:
        default = {}
    if not is_enabled():
        return default
    c = _get_client()
    if c is None:
        return default
    try:
        v = c.hgetall(NS + key)
        return v or default
    except Exception:
        return default


def safe_hdel(key: str, *fields: str) -> int:
    if not is_enabled() or not fields:
        return 0
    c = _get_client()
    if c is None:
        return 0
    try:
        return int(c.hdel(NS + key, *fields))
    except Exception:
        return 0


# ─── Lua 脚本（CAS / Token Bucket 用）─────────────────────────────────────

def safe_eval(script: str, keys: list[str], args: list, default: Any = None) -> Any:
    if not is_enabled():
        return default
    c = _get_client()
    if c is None:
        return default
    try:
        ns_keys = [NS + k for k in keys]
        return c.eval(script, len(ns_keys), *ns_keys, *args)
    except Exception:
        logger.debug("[redis] eval failed", exc_info=True)
        return default


# ─── 健康检查 ───────────────────────────────────────────────────────────────

def ping() -> bool:
    """主动健康检查，不走 feature flag（用于诊断）"""
    c = _get_client()
    if c is None:
        return False
    try:
        return bool(c.ping())
    except Exception:
        return False


def stats() -> dict:
    """返回 Redis 当前状态摘要（用于 admin 监控页）"""
    out = {"enabled": is_enabled(), "connected": False, "keys_geo": 0}
    c = _get_client()
    if c is None:
        return out
    try:
        out["connected"] = bool(c.ping())
        # 数 geo: 命名空间的 keys
        count = 0
        for _ in c.scan_iter(match=NS + "*", count=500):
            count += 1
            if count > 10000:  # 安全上限
                out["keys_geo"] = "10000+"
                return out
        out["keys_geo"] = count
        info = c.info("memory")
        out["used_memory"] = info.get("used_memory_human", "?")
    except Exception:
        pass
    return out
