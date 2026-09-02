"""数据库操作层 — MySQL (PyMySQL)"""

from __future__ import annotations

import calendar
import json
import os
import re
import threading
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, unquote

from geo_common import load_dotenv as _load_dotenv
_load_dotenv()

_MYSQL_CONFIG = {
    "host": os.environ.get("GEO_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("GEO_DB_PORT", "3306")),
    "user": os.environ.get("GEO_DB_USER", "geo_system"),
    "password": os.environ.get("GEO_DB_PASSWORD", ""),
    "database": os.environ.get("GEO_DB_NAME", "geo_system"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

_local = threading.local()
# schema 初始化:进程级一次。原线程局部会让 threaded 服务每个新线程都重跑几十条
# CREATE TABLE IF NOT EXISTS;远程库/隧道下每请求 ~30s(本地 dev 登录转圈的根因)。
_schema_init_done = False
_schema_init_lock = threading.Lock()

from geo_common import now_str as _now  # 共享时间戳工具


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.ping(reconnect=True)
        except Exception:
            conn = None
            _local.conn = None
    if conn is None:
        conn = pymysql.connect(**_MYSQL_CONFIG)
        _local.conn = conn
        global _schema_init_done
        if not _schema_init_done:
            with _schema_init_lock:
                if not _schema_init_done:
                    _init_schema(conn)
                    _schema_init_done = True
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    conn.begin()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _exec(conn, sql, args=None):
    # DEBUG: 打印所有 SQL 执行
    if 'UPDATE search_result' in sql:
        try:
            print(f"[DEBUG-_EXEC] sql={sql}", flush=True)
            print(f"[DEBUG-_EXEC] args={args}", flush=True)
        except UnicodeEncodeError:
            print(f"[DEBUG-_EXEC] sql={sql} (args含特殊字符，省略)", flush=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur


def _fetchone(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def _fetchall(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def _init_schema(conn):
    stmts = [
        """CREATE TABLE IF NOT EXISTS account (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            company_brand VARCHAR(255) NOT NULL,
            user_type VARCHAR(20) NOT NULL DEFAULT 'paid',
            current_status TEXT,
            optimize_start_date VARCHAR(255),
            platforms TEXT,
            insight_bullets TEXT,
            next_week_bullets TEXT,
            owner_id INT,
            created_at VARCHAR(255),
            updated_at VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS account_keyword (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id BIGINT NOT NULL,
            intent_category VARCHAR(255) NOT NULL,
            core_intent_word VARCHAR(255) NOT NULL,
            intent_prompt VARCHAR(500) NOT NULL,
            sort_order INT,
            created_at VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS search_task (
            id VARCHAR(36) PRIMARY KEY,
            account_id BIGINT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
            total_queries INT,
            completed_queries INT DEFAULT 0,
            current_keyword VARCHAR(255),
            error_message TEXT,
            priority TINYINT NOT NULL DEFAULT 7,
            source VARCHAR(30) NOT NULL DEFAULT 'internal_manual',
            created_at VARCHAR(255),
            completed_at VARCHAR(255),
            last_heartbeat VARCHAR(30),
            INDEX idx_st_status_priority (status, priority, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS search_result (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(36) NOT NULL,
            account_id BIGINT NOT NULL,
            keyword_id BIGINT,
            platform VARCHAR(255) NOT NULL,
            model VARCHAR(255) NOT NULL,
            keyword VARCHAR(500) NOT NULL,
            intent_category VARCHAR(255),
            core_intent_word VARCHAR(255),
            intent_prompt VARCHAR(500),
            success TINYINT(1),
            response_json LONGTEXT,
            answer_text LONGTEXT,
            answer_html LONGTEXT,
            summarys_json LONGTEXT,
            screenshot_url VARCHAR(1000),
            brand_rank INT,
            brand_analysis_json LONGTEXT,
            duration FLOAT,
            attempt INT,
            search_date VARCHAR(255) NOT NULL,
            created_at VARCHAR(255),
            updated_at VARCHAR(255),
            INDEX idx_sr_task (task_id),
            INDEX idx_sr_account_date (account_id, search_date),
            UNIQUE KEY uk_sr_task_platform_keyword (task_id, platform, keyword(200))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS report_info (
            id INT AUTO_INCREMENT PRIMARY KEY,
            share_code VARCHAR(255) UNIQUE,
            title VARCHAR(255),
            report_date VARCHAR(255),
            brand VARCHAR(255),
            platforms VARCHAR(255),
            optimize_start_date VARCHAR(255),
            search_mode VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS overview_bullet (
            id INT AUTO_INCREMENT PRIMARY KEY,
            share_code VARCHAR(255),
            section VARCHAR(50),
            content TEXT,
            sort_order INT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS ranking_record (
            id INT AUTO_INCREMENT PRIMARY KEY,
            share_code VARCHAR(255),
            platform VARCHAR(255),
            intent_category VARCHAR(255),
            core_intent VARCHAR(255),
            intent_prompt VARCHAR(500),
            record_date VARCHAR(255),
            rank_status VARCHAR(255),
            remark TEXT,
            summary_text TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS question_record (
            id INT AUTO_INCREMENT PRIMARY KEY,
            share_code VARCHAR(255),
            platform VARCHAR(255),
            record_date VARCHAR(255),
            intent_word VARCHAR(255),
            question TEXT,
            answer LONGTEXT,
            rank_status VARCHAR(255),
            remark TEXT,
            screenshot_url VARCHAR(1000)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS cite_item (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question_id BIGINT,
            title VARCHAR(500),
            url VARCHAR(1000),
            snippet TEXT,
            site_name VARCHAR(255),
            site_icon VARCHAR(1000),
            cite_index INT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS result_scrape (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id BIGINT NOT NULL,
            search_date VARCHAR(255) NOT NULL,
            url VARCHAR(1000) NOT NULL,
            title VARCHAR(500),
            site_name VARCHAR(255),
            markdown_content LONGTEXT,
            pub_date VARCHAR(255),
            content_type VARCHAR(255),
            website_type VARCHAR(255),
            scrape_status VARCHAR(20) DEFAULT 'pending',
            error_message TEXT,
            created_at VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS ranking_task (
            id VARCHAR(36) PRIMARY KEY,
            search_task_id VARCHAR(36),
            account_id BIGINT,
            brand_name VARCHAR(255) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            total INT DEFAULT 0,
            done INT DEFAULT 0,
            skipped INT DEFAULT 0,
            hit INT DEFAULT 0,
            top1 INT DEFAULT 0,
            top3 INT DEFAULT 0,
            gen_total INT DEFAULT 0,
            gen_hit INT DEFAULT 0,
            gen_top3 INT DEFAULT 0,
            gen_top1 INT DEFAULT 0,
            error_message TEXT,
            created_at VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS ranking_result (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ranking_task_id VARCHAR(36) NOT NULL,
            result_id BIGINT,
            keyword VARCHAR(500),
            model VARCHAR(255),
            brand_rank INT,
            brand_frequency INT DEFAULT 0,
            total_brands INT DEFAULT 0,
            all_brands_json TEXT,
            skipped TINYINT(1) DEFAULT 0,
            error TEXT,
            created_at VARCHAR(255),
            INDEX idx_rr_task (ranking_task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS system_setting (
            setting_key VARCHAR(255) PRIMARY KEY,
            setting_value TEXT,
            description VARCHAR(500),
            updated_at VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS account_webhook_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id INT NOT NULL,
            webhook_url VARCHAR(1000) NOT NULL,
            oauth_token VARCHAR(255) NOT NULL,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            created_by INT NULL,
            created_at VARCHAR(30),
            updated_at VARCHAR(30),
            UNIQUE KEY uk_awc_account (account_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS site_price (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source TEXT,
            name TEXT,
            channel TEXT,
            cost DOUBLE,
            status INT DEFAULT 1,
            INDEX idx_sp_name (name(191)),
            INDEX idx_sp_channel (channel(191))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS quote_task (
            id VARCHAR(36) PRIMARY KEY,
            account_id BIGINT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            stage VARCHAR(20),
            progress_done INT DEFAULT 0,
            progress_total INT DEFAULT 0,
            base_price DOUBLE DEFAULT 2500000.0,
            final_score DOUBLE,
            final_price DOUBLE,
            error_message TEXT,
            created_at VARCHAR(255),
            started_at VARCHAR(255),
            completed_at VARCHAR(255),
            last_heartbeat VARCHAR(30)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS quote_query_run (
            id INT AUTO_INCREMENT PRIMARY KEY,
            quote_task_id VARCHAR(36) NOT NULL,
            keyword TEXT NOT NULL,
            model VARCHAR(50) NOT NULL,
            d1 DOUBLE, d2 DOUBLE, d3 DOUBLE, d4 DOUBLE, d5 DOUBLE,
            final_score DOUBLE,
            multiplier DOUBLE,
            run_price DOUBLE,
            result_count INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            error_message TEXT,
            created_at VARCHAR(255),
            INDEX idx_qqr_task (quote_task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS quote_result (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query_run_id INT NOT NULL,
            source_site TEXT,
            source_url TEXT,
            title TEXT,
            page_content LONGTEXT,
            scrape_status VARCHAR(20) DEFAULT 'pending',
            pub_date TEXT,
            content_type TEXT,
            website_type TEXT,
            clean_content LONGTEXT,
            relevance_percent INT,
            relevance_level INT,
            relevance_reason TEXT,
            extract_status VARCHAR(20) DEFAULT 'pending',
            d1 DOUBLE, d2 DOUBLE, d3 DOUBLE, d4 DOUBLE, d5 DOUBLE,
            created_at VARCHAR(255),
            INDEX idx_qr_run (query_run_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS scheduled_search_task (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id INT NOT NULL,
            name VARCHAR(255),
            sub_type VARCHAR(20) NOT NULL DEFAULT 'search',
            models TEXT,
            frequency VARCHAR(10) NOT NULL DEFAULT 'daily',
            run_time VARCHAR(5) NOT NULL DEFAULT '00:01',
            day_of_week INT DEFAULT 6,
            day_of_month INT DEFAULT -1,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            next_run_at VARCHAR(30),
            last_run_at VARCHAR(30),
            last_task_id VARCHAR(40),
            last_status VARCHAR(20),
            manual_trigger_pending TINYINT(1) NOT NULL DEFAULT 0,
            created_at VARCHAR(30),
            INDEX idx_sched_next (enabled, next_run_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS cancel_signal (
            task_id VARCHAR(64) PRIMARY KEY,
            requested_at VARCHAR(30)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS scheduled_task_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sched_id INT NOT NULL,
            account_id INT NOT NULL,
            task_id VARCHAR(40),
            status VARCHAR(20) NOT NULL,
            started_at VARCHAR(30),
            finished_at VARCHAR(30),
            duration_seconds INT,
            trigger_type VARCHAR(20) DEFAULT 'scheduled',
            detail TEXT,
            created_at VARCHAR(30),
            INDEX idx_hist_sched (sched_id),
            INDEX idx_hist_time (started_at),
            INDEX idx_hist_account (account_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS admin_user (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'operator',
            role_id INT NULL,
            permissions TEXT,
            created_at VARCHAR(30),
            last_login_at VARCHAR(30),
            INDEX idx_admin_role_id (role_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS role (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            code VARCHAR(50) NOT NULL UNIQUE,
            data_scope ENUM('all','self') NOT NULL DEFAULT 'self',
            is_builtin TINYINT(1) NOT NULL DEFAULT 0,
            description VARCHAR(200),
            created_at VARCHAR(30),
            updated_at VARCHAR(30)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS role_page (
            role_id INT NOT NULL,
            page_key VARCHAR(50) NOT NULL,
            PRIMARY KEY (role_id, page_key),
            INDEX idx_rp_role (role_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS team (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            leader_user_id INT NULL,
            created_at VARCHAR(30),
            updated_at VARCHAR(30),
            INDEX idx_team_leader (leader_user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS account_owner (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id INT NOT NULL,
            owner_user_id INT NOT NULL,
            created_at VARCHAR(30),
            UNIQUE KEY uq_ao (account_id, owner_user_id),
            INDEX idx_ao_owner (owner_user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS external_invite (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(32) NOT NULL UNIQUE,
            description VARCHAR(200),
            max_uses INT NOT NULL DEFAULT 3,
            used_count INT NOT NULL DEFAULT 0,
            max_keywords INT NOT NULL DEFAULT 100,
            allowed_platforms TEXT,
            expires_at VARCHAR(30),
            created_by INT,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at VARCHAR(30),
            updated_at VARCHAR(30),
            INDEX idx_ei_code (code),
            INDEX idx_ei_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS external_brute_lock (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ip VARCHAR(45) NOT NULL,
            failed_at DATETIME NOT NULL,
            INDEX idx_ebl_ip_time (ip, failed_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS external_use (
            id INT AUTO_INCREMENT PRIMARY KEY,
            invite_id INT NOT NULL,
            account_id BIGINT,
            weekly_report_id INT,
            brand_name VARCHAR(200) NOT NULL,
            keywords_count INT NOT NULL DEFAULT 0,
            keywords_text MEDIUMTEXT,
            platforms TEXT,
            modules TEXT,
            share_password VARCHAR(64),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            progress_percent INT NOT NULL DEFAULT 0,
            progress_message VARCHAR(255),
            error_message TEXT,
            ip VARCHAR(45),
            user_agent VARCHAR(500),
            created_at VARCHAR(30),
            completed_at VARCHAR(30),
            INDEX idx_eu_invite (invite_id),
            INDEX idx_eu_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS login_attempt (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ip VARCHAR(45) NOT NULL,
            attempted_at DATETIME NOT NULL,
            INDEX idx_la_ip_time (ip, attempted_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS login_lockout (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ip VARCHAR(45) NOT NULL,
            locked_at DATETIME NOT NULL,
            INDEX idx_ll_ip_time (ip, locked_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        """CREATE TABLE IF NOT EXISTS account_keyword_audit (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            account_id BIGINT NOT NULL,
            changed_by INT,
            changed_by_name VARCHAR(64),
            changed_ip VARCHAR(45),
            before_count INT NOT NULL DEFAULT 0,
            after_count INT NOT NULL DEFAULT 0,
            before_snapshot LONGTEXT,
            after_snapshot LONGTEXT,
            changed_at VARCHAR(30) NOT NULL,
            INDEX idx_aka_account (account_id, changed_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]
    with conn.cursor() as cur:
        for stmt in stmts:
            cur.execute(stmt)
    _ensure_columns(conn)
    _run_bundled_schema_files(conn)
    conn.commit()


def _run_bundled_schema_files(conn) -> None:
    """执行 migrations/ 下随仓库附带的整表 DDL 文件（均为 CREATE TABLE IF NOT EXISTS，幂等）。
    用于体量较大、不便内联进 stmts 的模块表（如知识库 7 张表）。"""
    from pathlib import Path as _Path
    mig_dir = _Path(__file__).resolve().parent / "migrations"
    for fname in ("kb_schema.sql", "extra_schema.sql"):
        fp = mig_dir / fname
        if not fp.exists():
            continue
        try:
            sql = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        with conn.cursor() as cur:
            for stmt in _split_sql_statements(sql):
                cur.execute(stmt)


def _split_sql_statements(sql: str) -> list:
    """按「行尾分号」切分 SQL 语句。

    不能用 sql.split(";")——列 COMMENT 里可能含分号（如 '(NULL=不过期);格式 ...'），
    裸切会把一条 CREATE 撕成无效片段并静默建表失败。语句总是以行尾的 ';' 结束，
    据此累积成句即可。
    """
    stmts, buf = [], []
    for line in sql.splitlines():
        if not line.strip():
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _ensure_columns(conn) -> None:
    """对老库做轻量列补齐（IF NOT EXISTS 风格，靠 information_schema 判断）。
    新增表只需在上面 stmts 里写 CREATE；只有"已经存在的表想加列"才需要在这里登记。
    """
    needed = [
        ("admin_user", "role",        "VARCHAR(20) NOT NULL DEFAULT 'user'"),
        ("admin_user", "permissions", "TEXT"),
        ("admin_user", "team_id",     "INT NULL"),
        # 团队/客户归属所需（team 管理页 + access_scope 团队隔离 + 登录后首页概览）
        ("account",    "team_id",     "INT NULL"),
        ("account",    "deleted_at",  "VARCHAR(30) NULL"),
        ("account",    "is_temp",     "TINYINT(1) NOT NULL DEFAULT 0"),
        ("account",    "status",      "VARCHAR(20) NOT NULL DEFAULT 'formal'"),
        ("account",    "archived_at",  "VARCHAR(30) NULL"),
        ("account",    "created_at",  "VARCHAR(30) NULL"),
        # 客户管理模块所需业务列
        ("account",    "business_owner",    "VARCHAR(255) NULL"),
        ("account",    "kpi_json",          "TEXT NULL"),
        ("account",    "brand_report_mode", "VARCHAR(20) NULL"),
        ("account",    "data_share_json",   "TEXT NULL"),
        ("account",    "share_token",       "VARCHAR(64) NULL"),
        ("account",    "writing_requirements", "LONGTEXT NULL"),
        ("account",    "prompt_modules",    "LONGTEXT NULL"),
        # 查词模块 search_task 漂移列（对应 migrations/001-004 + live_inflight）
        ("search_task", "recheck_count",    "INT NOT NULL DEFAULT 0"),
        ("search_task", "last_progress_at", "VARCHAR(30) NULL"),
        ("search_task", "override_payload", "TEXT NULL"),
        ("search_task", "live_inflight",    "TEXT NULL"),
        # 查词结果表漂移列（重试可观测 + 结果轻列读取所需）
        ("search_result", "error_message",       "TEXT NULL"),
        ("search_result", "first_attempt_error", "TEXT NULL"),
        ("search_result", "rescue_round",        "VARCHAR(30) NOT NULL DEFAULT 'initial'"),
        # 定时任务执行锁（防止API和调度器并发执行）
        ("scheduled_search_task", "execution_lock", "VARCHAR(20) DEFAULT NULL"),
        # 定时任务子类型（search 查词 / ranking 排名分析）
        ("scheduled_search_task", "sub_type", "VARCHAR(20) NOT NULL DEFAULT 'search'"),
        # 知识库资料智能识别文本（Qwen3.7 识别后输出）
        ("customer_knowledge_source", "ai_text", "LONGTEXT NULL"),
        ("customer_knowledge_source", "ai_status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
        # 知识库任务类型区分（generate / recognize）
        ("kb_gen_task", "task_type", "VARCHAR(20) NOT NULL DEFAULT 'generate'"),
        ("kb_gen_task", "source_id", "BIGINT DEFAULT NULL"),
    ]
    # 全局 cursor 是 DictCursor，fetchone() 返回 dict 不是 tuple；用列别名 + dict 取值兼容
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS dbname")
        row = cur.fetchone() or {}
        dbname = row["dbname"] if isinstance(row, dict) else row[0]
        for table, col, ddl in needed:
            cur.execute(
                "SELECT 1 AS x FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
                (dbname, table, col))
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        # role.data_scope 老库枚举缺 'team'（三态 all/team/self）→ 幂等补齐
        cur.execute(
            "SELECT column_type AS ct FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name='role' AND column_name='data_scope'",
            (dbname,))
        drow = cur.fetchone() or {}
        ctype = (drow.get("ct") if isinstance(drow, dict) else (drow[0] if drow else "")) or ""
        if "team" not in ctype:
            cur.execute(
                "ALTER TABLE role MODIFY COLUMN data_scope "
                "ENUM('all','team','self') NOT NULL DEFAULT 'self'")
        
        # 【防重复】确保防重复触发器存在
        try:
            cur.execute("DROP TRIGGER IF EXISTS prevent_duplicate_history_insert")
            trigger_sql = """
            CREATE TRIGGER prevent_duplicate_history_insert
            BEFORE INSERT ON scheduled_task_history
            FOR EACH ROW
            BEGIN
                DECLARE recent_count INT;
                SELECT COUNT(*) INTO recent_count 
                FROM scheduled_task_history 
                WHERE sched_id = NEW.sched_id 
                  AND created_at >= DATE_SUB(NOW(), INTERVAL 120 SECOND);
                IF recent_count > 0 THEN
                    SIGNAL SQLSTATE '45000' 
                        SET MESSAGE_TEXT = 'Duplicate history record within 120 seconds';
                END IF;
            END;
            """
            cur.execute(trigger_sql)
            print("[OK] 防重复触发器已就绪")
        except Exception as trig_err:
            print(f"[WARN] 创建防重复触发器失败: {trig_err}")


# ═══════════════════════════════════════════
# Account CRUD
# ═══════════════════════════════════════════

def list_accounts(owner_id: int | None = None, include_temp: bool = False, include_deleted: bool = False, only_formal: bool = False, team_id: int | None = None) -> list[dict]:
    """默认排除临时账号 + 已软删除账号；include_deleted=True 时只返回回收站。

    only_formal=True 时只返回正式客户(status='formal')，用于查词/报告/首页概览等
    运营功能模块；账户管理列表传 False 以显示初始客户(draft) + 转正入口。

    可见性三态(调用方按 data_scope 二选一传):
      - team_id 传入:团队负责人 → 看本团队 account.team_id 的全部客户
      - owner_id 传入:运营人 → 看自己被指派(account_owner)的客户
      - 都不传:super_admin → 看全部"""
    conn = get_conn()
    where = []
    clauses = []
    all_params = []
    # 团队负责人:看本团队全部客户
    if team_id is not None:
        clauses.append("a.team_id=%s")
        all_params.append(team_id)
    # 运营人:多业务负责人 —— 当前用户是该客户负责人之一即可见(account_owner 多对多)
    if owner_id is not None:
        clauses.append("EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)")
        all_params.append(owner_id)
    if not include_temp:
        where.append("(is_temp IS NULL OR is_temp=0)")
    if only_formal:
        where.append("status='formal'")
    if include_deleted:
        where.append("deleted_at IS NOT NULL")
    else:
        where.append("deleted_at IS NULL")
    # JOIN admin_user 获取主负责人 owner_name（列表锚点显示，多负责人见 owners 字段）
    base = "SELECT a.*, u.username AS owner_name FROM account a LEFT JOIN admin_user u ON u.id = a.owner_id"
    if where:
        import re as _re
        for w in where:
            clauses.append(_re.sub(r"\b(owner_id|is_temp|deleted_at|status)\b", r"a.\1", w))
    if clauses:
        base += " WHERE " + " AND ".join(clauses)
    base += " ORDER BY a.created_at DESC"
    rows = _fetchall(conn, base, tuple(all_params)) if all_params else _fetchall(conn, base)
    owners_map = _batch_account_owners([r["id"] for r in rows])
    leaders = _team_leaders()
    out = []
    for r in rows:
        d = _account_to_dict(r)
        d["owners"] = _order_owners_leader_first(
            owners_map.get(r["id"], []), leaders.get(r.get("team_id")))
        out.append(d)
    return out


def _team_leaders() -> dict:
    """{team_id: leader_user_id} —— 团队负责人查表。"""
    try:
        rows = _fetchall(get_conn(), "SELECT id, leader_user_id FROM team")
        return {r["id"]: r.get("leader_user_id") for r in rows if r.get("leader_user_id")}
    except Exception:
        return {}


def _order_owners_leader_first(owners: list, leader_id) -> list:
    """业务负责人列表:团队负责人永远排最前(其余保持原序)。"""
    if not owners or not leader_id:
        return owners
    lead = [o for o in owners if o.get("id") == leader_id]
    if not lead:
        return owners
    return lead + [o for o in owners if o.get("id") != leader_id]


def _batch_account_owners(account_ids: list) -> dict:
    """批量取多个客户的全部业务负责人。返回 {account_id: [{id, username}]}。"""
    if not account_ids:
        return {}
    conn = get_conn()
    ph = ",".join(["%s"] * len(account_ids))
    rows = _fetchall(conn,
        f"SELECT ao.account_id, ao.owner_user_id, u.username, u.role "
        f"FROM account_owner ao LEFT JOIN admin_user u ON u.id = ao.owner_user_id "
        f"WHERE ao.account_id IN ({ph}) ORDER BY ao.id",
        tuple(account_ids))
    m: dict = {}
    for r in rows:
        m.setdefault(r["account_id"], []).append(
            {"id": r["owner_user_id"], "username": r.get("username") or "",
             "role": r.get("role") or "operator"})
    return m


def get_account_owners(account_id: int) -> list:
    """取单个客户的全部业务负责人 [{id, username}]。"""
    return _batch_account_owners([account_id]).get(account_id, [])


def set_account_owners(account_id: int, owner_user_ids: list) -> None:
    """全量设置某客户的业务负责人(多对多)。第一个作为主负责人写回 account.owner_id。"""
    ids = []
    for uid in (owner_user_ids or []):
        try:
            iv = int(uid)
        except (TypeError, ValueError):
            continue
        if iv not in ids:
            ids.append(iv)
    now = _now()
    with transaction() as conn:
        _exec(conn, "DELETE FROM account_owner WHERE account_id=%s", (account_id,))
        for uid in ids:
            _exec(conn,
                "INSERT IGNORE INTO account_owner (account_id, owner_user_id, created_at) VALUES (%s,%s,%s)",
                (account_id, uid, now))
        # 主负责人:取第一个(无则置空)
        primary = ids[0] if ids else None
        _exec(conn, "UPDATE account SET owner_id=%s, updated_at=%s WHERE id=%s",
              (primary, now, account_id))


# ─── 团队(team)+ 用户/客户归属 ───
def get_user_team_id(user_id: int) -> Optional[int]:
    conn = get_conn()
    row = _fetchone(conn, "SELECT team_id FROM admin_user WHERE id=%s", (user_id,))
    if not row:
        return None
    return row.get("team_id") or row.get("teamId")


def list_teams() -> list[dict]:
    """全部团队 + 负责人名 + 成员数 + 客户数。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT t.id, t.name, t.leader_user_id, u.username AS leader_name, t.created_at "
        "FROM team t LEFT JOIN admin_user u ON u.id = t.leader_user_id ORDER BY t.id")
    out = []
    for r in rows:
        tid = r["id"]
        mc = _fetchone(conn, "SELECT COUNT(*) AS c FROM admin_user WHERE team_id=%s", (tid,))
        ac = _fetchone(conn, "SELECT COUNT(*) AS c FROM account WHERE team_id=%s AND deleted_at IS NULL", (tid,))
        out.append({
            "id": tid, "name": r.get("name"),
            "leaderUserId": r.get("leader_user_id"),
            "leaderName": r.get("leader_name") or "",
            "memberCount": (mc or {}).get("c", 0),
            "accountCount": (ac or {}).get("c", 0),
            "createdAt": r.get("created_at") or "",
        })
    return out


def get_team(team_id: int) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn, "SELECT id, name, leader_user_id, created_at FROM team WHERE id=%s", (team_id,))
    return dict(row) if row else None


def create_team(name: str, leader_user_id: int | None = None) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            "INSERT INTO team (name, leader_user_id, created_at, updated_at) VALUES (%s,%s,%s,%s)",
            ((name or "").strip()[:100], leader_user_id, now, now))
        tid = cur.lastrowid
        # 团队负责人自动归入本团队
        if leader_user_id:
            _exec(conn, "UPDATE admin_user SET team_id=%s WHERE id=%s", (tid, leader_user_id))
    return int(tid)


def update_team(team_id: int, *, name: str | None = None, leader_user_id: int | None = None) -> None:
    sets, args = [], []
    if name is not None:
        sets.append("name=%s"); args.append(name.strip()[:100])
    if leader_user_id is not None:
        sets.append("leader_user_id=%s"); args.append(leader_user_id or None)
    if not sets:
        return
    sets.append("updated_at=%s"); args.append(_now())
    args.append(team_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE team SET {', '.join(sets)} WHERE id=%s", tuple(args))
        # 设置负责人时，将该用户的团队也切换到当前团队（一个负责人只属于一个团队）
        if leader_user_id:
            _exec(conn, "UPDATE admin_user SET team_id=%s WHERE id=%s", (team_id, leader_user_id))


def delete_team(team_id: int) -> bool:
    """删除团队（仅空团队可删除）。返回是否成功。"""
    with transaction() as conn:
        # 检查是否有成员
        row = _fetchone(conn, "SELECT COUNT(*) AS cnt FROM admin_user WHERE team_id=%s", (team_id,))
        if row and row["cnt"] > 0:
            return False
        # 检查是否有客户
        row = _fetchone(conn, "SELECT COUNT(*) AS cnt FROM account WHERE team_id=%s", (team_id,))
        if row and row["cnt"] > 0:
            return False
        _exec(conn, "DELETE FROM team WHERE id=%s", (team_id,))
        return True


def set_user_team(user_id: int, team_id: int | None) -> None:
    with transaction() as conn:
        _exec(conn, "UPDATE admin_user SET team_id=%s WHERE id=%s", (team_id, user_id))


def set_account_team(account_id: int, team_id: int | None) -> None:
    with transaction() as conn:
        _exec(conn, "UPDATE account SET team_id=%s, updated_at=%s WHERE id=%s",
              (team_id, _now(), account_id))


def list_team_members(team_id: int) -> list[dict]:
    """某团队的全部成员(用户)。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, username, role, team_id FROM admin_user WHERE team_id=%s ORDER BY id", (team_id,))
    return [dict(r) for r in rows]


def get_account(account_id: int, include_deleted: bool = False) -> Optional[dict]:
    conn = get_conn()
    if include_deleted:
        row = _fetchone(conn, "SELECT * FROM account WHERE id=%s", (account_id,))
    else:
        row = _fetchone(conn, "SELECT * FROM account WHERE id=%s AND deleted_at IS NULL", (account_id,))
    if not row:
        return None
    d = _account_to_dict(row)
    d["owners"] = _order_owners_leader_first(
        get_account_owners(account_id), _team_leaders().get(row.get("team_id")))
    return d


def _safe_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _normalize_user_type(data: dict) -> str:
    ut = str(data.get("userType", "") or "").strip().lower()
    return "quote" if ut == "quote" else "paid"


def create_account(data: dict, owner_id: int | None = None) -> dict:
    now = _now()
    user_type = _normalize_user_type(data)
    is_temp = 1 if data.get("isTemp") else 0
    # status: 知识库新建客户传 'draft'(初始客户,不进运营外层);其余默认 'formal'(正式)
    status = "draft" if str(data.get("status", "") or "").strip().lower() == "draft" else "formal"
    # team_id 兜底(2026-05-27 修):未显式传则继承 owner.team_id
    #   超管 owner.team_id=NULL → 新客户 NULL → 不进任何团队视图(超管私有)
    #   admin/operator owner.team_id=N → 新客户归 N 团队
    #   显式传则尊重传入值(用户可 override)
    explicit_team = data.get("teamId") or data.get("team_id")
    if explicit_team:
        team_id_val = explicit_team
    elif owner_id:
        with transaction() as _conn0:
            _row = _fetchone(_conn0,
                "SELECT team_id FROM admin_user WHERE id=%s", (owner_id,))
        team_id_val = (_row or {}).get("team_id")
    else:
        team_id_val = None
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO account (company_name, company_brand, user_type, status, platforms,
               optimize_start_date, current_status, insight_bullets, next_week_bullets,
               owner_id, is_temp, business_owner, team_id, kpi_json, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                _safe_str(data.get("companyName", "")),
                _safe_str(data.get("companyBrand", "")),
                user_type,
                status,
                json.dumps(data.get("platforms") or [], ensure_ascii=False),
                _safe_str(data.get("optimizeStartDate", "")),
                _safe_str(data.get("currentStatus", "")),
                _safe_str(data.get("insightBullets", "")),
                _safe_str(data.get("nextWeekBullets", "")),
                owner_id,
                is_temp,
                _safe_str(data.get("businessOwner", "")),
                team_id_val,
                json.dumps(_normalize_kpi(data.get("kpi")), ensure_ascii=False),
                now, now,
            ),
        )
        new_id = cur.lastrowid
        # 创建人写入多对多负责人表(可见性)
        if owner_id:
            _exec(conn,
                "INSERT IGNORE INTO account_owner (account_id, owner_user_id, created_at) VALUES (%s,%s,%s)",
                (new_id, owner_id, now))
    return get_account(new_id)


def _sync_account_platforms_to_schedules(account_id: int, platforms_list: list) -> int:
    """把账号的 platforms 同步到该账号下所有 scheduled_search_task.models（方案 A）。

    写入前先用 platforms.normalize_platforms 把 "千问" 等简写归一为标准 platform 名，
    避免 DB 字段存非标准值带来的隐患（即便当前消费方都经过 _build_search_inputs 二次 normalize）。

    返回受影响的调度行数。"""
    try:
        from platforms import _normalize_platforms
        platforms_list = _normalize_platforms(platforms_list or [])
    except Exception:
        # 极端情况下 platforms 加载失败，退回原样写入（仍由消费方 normalize 兜底）
        platforms_list = list(platforms_list or [])
    models_json = json.dumps(platforms_list, ensure_ascii=False)
    with transaction() as conn:
        cur = _exec(conn,
            "UPDATE scheduled_search_task SET models=%s WHERE account_id=%s",
            (models_json, account_id),
        )
        try:
            return cur.rowcount or 0
        except Exception:
            return 0


def update_account(account_id: int, data: dict) -> Optional[dict]:
    now = _now()
    user_type = _normalize_user_type(data)
    platforms_list = data.get("platforms") or []
    # 防误清:update_account 是全量更新。若调用方未带 companyName(部分字段更新/只改
    # kpi/dataShare 等),跳过主字段 UPDATE,避免把公司名/品牌/平台等已有信息清空。
    # 单字段更新请用 update_account_partial;此处只放行明确带了 companyName 的全量保存。
    _has_main = bool((data.get("companyName") or "").strip())
    with transaction() as conn:
        if _has_main:
            _exec(conn,
            """UPDATE account SET company_name=%s, company_brand=%s, user_type=%s, platforms=%s,
               optimize_start_date=%s, current_status=%s, insight_bullets=%s,
               next_week_bullets=%s, updated_at=%s
               WHERE id=%s""",
            (
                _safe_str(data.get("companyName", "")),
                _safe_str(data.get("companyBrand", "")),
                user_type,
                json.dumps(platforms_list, ensure_ascii=False),
                _safe_str(data.get("optimizeStartDate", "")),
                _safe_str(data.get("currentStatus", "")),
                _safe_str(data.get("insightBullets", "")),
                _safe_str(data.get("nextWeekBullets", "")),
                now,
                account_id,
            ),
        )
    # KPI 单独更新:仅当调用方显式传了 kpi 才写,避免其它 update 调用把已有 KPI 抹掉
    if "kpi" in data:
        with transaction() as conn:
            _exec(conn, "UPDATE account SET kpi_json=%s WHERE id=%s",
                  (json.dumps(_normalize_kpi(data.get("kpi")), ensure_ascii=False), account_id))
    # 品牌报告模式(single/multi):仅当显式传了才写,NULL=默认单品牌别名归并
    if "brandReportMode" in data:
        mode = (data.get("brandReportMode") or "").strip().lower()
        mode = mode if mode in ("single", "multi") else None
        with transaction() as conn:
            _exec(conn, "UPDATE account SET brand_report_mode=%s WHERE id=%s", (mode, account_id))
    # 数据共享:本账号报告从来源账号取指定范围的数据(拆分客户:发布集中在老账号等)。仅显式传才写
    if "dataShare" in data:
        with transaction() as conn:
            ds = _normalize_data_share(data.get("dataShare"))
            _exec(conn, "UPDATE account SET data_share_json=%s WHERE id=%s",
                  (json.dumps(ds, ensure_ascii=False) if ds else None, account_id))
    if _has_main:
        _sync_account_platforms_to_schedules(account_id, platforms_list)
    return get_account(account_id)


# 所有引用 account_id 的子表（删除账号 / 清理临时账号时一并清空）
_ACCOUNT_CHILD_TABLES = (
    # 调度类
    "scheduled_search_task",
    "scheduled_ranking_task",
    "scheduled_quote_task",
    "scheduled_citation_task",
    "scheduled_pipeline_task",
    "scheduled_weekly_report_task",
    # 任务执行类
    "search_task",
    "search_result",
    "ranking_task",
    "quote_task",
    "kb_gen_task",
    "content_gen_task",
    "keyword_expand_task",
    "citation_scrape_task",
    "pipeline_execution",
    "publish_batch_task",
    "publish_order",
    "result_scrape",
    "weekly_report",
    # 知识/内容/产物类
    "customer_knowledge",
    "customer_knowledge_kb",
    "customer_knowledge_source",
    "customer_article",
    "customer_content_insight",
    # 关键词审计
    "account_keyword",
    "account_keyword_audit",
)


def _purge_account_data(conn, account_id: int) -> dict:
    """删除某账号在所有子表里的数据（不含 account 行本身）。返回每表删除行数。"""
    stats = {}
    for tbl in _ACCOUNT_CHILD_TABLES:
        try:
            with conn.cursor() as c:
                c.execute(f"DELETE FROM {tbl} WHERE account_id=%s", (account_id,))
                stats[tbl] = c.rowcount
        except Exception as exc:
            # 单表失败不阻断整体；记到 stats 里以便排查
            stats[tbl] = f"ERR:{exc}"
    return stats


def delete_account(account_id: int) -> dict:
    """软删除：标记 deleted_at = now()。账号进回收站，30 天后被清理任务永久删除。
    保留所有子表数据，便于恢复。"""
    with transaction() as conn:
        _exec(conn, "UPDATE account SET deleted_at=%s, updated_at=%s WHERE id=%s",
              (_now(), _now(), account_id))
    return {"soft_deleted": True, "account_id": account_id}


def restore_account(account_id: int) -> Optional[dict]:
    """从回收站恢复账号：deleted_at 置 NULL"""
    with transaction() as conn:
        _exec(conn, "UPDATE account SET deleted_at=NULL, updated_at=%s WHERE id=%s",
              (_now(), account_id))
    return get_account(account_id, include_deleted=False)


def purge_account(account_id: int) -> dict:
    """永久删除：物理 DELETE + 子表清理（不可恢复）"""
    with transaction() as conn:
        stats = _purge_account_data(conn, account_id)
        _exec(conn, "DELETE FROM account WHERE id=%s", (account_id,))
    return stats


def list_deleted_accounts(owner_id: int | None = None, team_id: int | None = None) -> list[dict]:
    """回收站列表"""
    return list_accounts(owner_id=owner_id, team_id=team_id, include_temp=True, include_deleted=True)


# ═══════════════════════════════════════════
# Archive (归档) — 客户到期保留数据，不删除也不查词
# ═══════════════════════════════════════════

def archive_account(account_id: int) -> dict:
    """归档客户：标记 archived=1 + archived_at。
    归档后不再出现在客户列表，也不再执行查词任务。数据完整保留。
    """
    with transaction() as conn:
        _exec(conn,
               "UPDATE account SET status='archived', archived_at=%s, updated_at=%s WHERE id=%s AND deleted_at IS NULL",
               (_now(), _now(), account_id))
    return {"archived": True, "account_id": account_id}


def unarchive_account(account_id: int) -> Optional[dict]:
    """从归档恢复：status 改回 formal，清除 archived_at"""
    with transaction() as conn:
        _exec(conn,
               "UPDATE account SET status='formal', archived_at=NULL, updated_at=%s WHERE id=%s",
               (_now(), account_id))
    return get_account(account_id, include_deleted=False)


def list_archived_accounts(owner_id: int | None = None, team_id: int | None = None) -> list[dict]:
    """归档客户列表（只返回已归档的）"""
    conn = get_conn()
    where = ["a.status='archived'", "a.deleted_at IS NULL"]
    params = []
    if team_id is not None:
        where.append("a.team_id=%s")
        params.append(team_id)
    if owner_id is not None:
        where.append("EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)")
        params.append(owner_id)
    base = ("SELECT a.*, u.username AS owner_name FROM account a "
            "LEFT JOIN admin_user u ON u.id = a.owner_id "
            " WHERE " + " AND ".join(where) +
            " ORDER BY a.archived_at DESC")
    rows = _fetchall(conn, base, tuple(params)) if params else _fetchall(conn, base)
    owners_map = _batch_account_owners([r["id"] for r in rows])
    leaders = _team_leaders()
    out = []
    for r in rows:
        d = _account_to_dict(r)
        d["owners"] = _order_owners_leader_first(
            owners_map.get(r["id"], []), leaders.get(r.get("team_id")))
        out.append(d)
    return out


def purge_archived_account(account_id: int) -> dict:
    """永久删除已归档的客户（物理删除+子表清理）"""
    with transaction() as conn:
        stats = _purge_account_data(conn, account_id)
        _exec(conn, "DELETE FROM account WHERE id=%s", (account_id,))
    return stats


def cleanup_expired_deleted_accounts(days: int = 30) -> dict:
    """清理回收站超 N 天的账号（每日 maintenance 调用）"""
    with transaction() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, company_name FROM account "
                "WHERE deleted_at IS NOT NULL AND deleted_at < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (int(days),),
            )
            rows = c.fetchall()
        if not rows:
            return {"purged": 0, "accounts": []}
        purged = []
        for r in rows:
            acc_id = r["id"] if isinstance(r, dict) else r[0]
            name = r["company_name"] if isinstance(r, dict) else r[1]
            stats = _purge_account_data(conn, acc_id)
            _exec(conn, "DELETE FROM account WHERE id=%s", (acc_id,))
            purged.append({"account_id": acc_id, "company_name": name, "purged": stats})
        return {"purged": len(purged), "accounts": purged}


def cleanup_expired_temp_accounts(days: int = 7) -> dict:
    """删除创建时间 > N 天的临时账号（is_temp=1）及其所有子表数据。"""
    with transaction() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, company_name FROM account "
                "WHERE is_temp=1 AND created_at < NOW() - INTERVAL %s DAY",
                (int(days),),
            )
            rows = c.fetchall()
        if not rows:
            return {"deleted": 0, "accounts": []}
        deleted = []
        for r in rows:
            acc_id = r["id"] if isinstance(r, dict) else r[0]
            name = r["company_name"] if isinstance(r, dict) else r[1]
            stats = _purge_account_data(conn, acc_id)
            _exec(conn, "DELETE FROM account WHERE id=%s", (acc_id,))
            deleted.append({"account_id": acc_id, "company_name": name, "purged": stats})
        return {"deleted": len(deleted), "accounts": deleted}


_ACCOUNT_PARTIAL_FIELD_MAP = {
    "companyName":       ("company_name",        lambda v: _safe_str(v)),
    "businessOwner":     ("business_owner",      lambda v: _safe_str(v)),
    "companyBrand":      ("company_brand",       lambda v: _safe_str(v)),
    "userType":          ("user_type",           lambda v: "quote" if str(v) == "quote" else "paid"),
    "platforms":         ("platforms",           lambda v: json.dumps(v or [], ensure_ascii=False)),
    "optimizeStartDate": ("optimize_start_date", lambda v: _safe_str(v)),
    "currentStatus":     ("current_status",      lambda v: _safe_str(v)),
    "insightBullets":    ("insight_bullets",     lambda v: _safe_str(v)),
    "nextWeekBullets":   ("next_week_bullets",   lambda v: _safe_str(v)),
    "promptModules":     ("prompt_modules",      lambda v: json.dumps(v or [], ensure_ascii=False)),
    "brandReportMode":   ("brand_report_mode",   lambda v: (str(v).strip().lower() if str(v).strip().lower() in ("single", "multi") else None)),
}


def update_account_partial(account_id: int, data: dict) -> Optional[dict]:
    sets, vals = [], []
    for camel, (col, conv) in _ACCOUNT_PARTIAL_FIELD_MAP.items():
        if camel in data:
            sets.append(f"{col}=%s")
            vals.append(conv(data[camel]))
    if not sets:
        return get_account(account_id)
    sets.append("updated_at=%s")
    vals.append(_now())
    vals.append(account_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE account SET {', '.join(sets)} WHERE id=%s", tuple(vals))
    if "platforms" in data:
        _sync_account_platforms_to_schedules(account_id, data.get("platforms") or [])
    return get_account(account_id)


def _account_to_dict(row) -> dict:
    if not row:
        return None
    d = dict(row)
    try:
        plats = json.loads(d.get("platforms") or "[]")
    except (json.JSONDecodeError, TypeError):
        plats = []
    # 规范化 + 去重（容错历史脏数据：如 ["Kimi","kimi"]、["千问","通义千问"] 等）
    try:
        from platforms import _normalize_platforms  # lazy import 避免循环依赖
        plats = _normalize_platforms(plats)
    except Exception:
        # 兜底：仅去重
        seen = set(); cleaned = []
        for p in plats:
            ps = str(p or "").strip()
            if ps and ps not in seen:
                seen.add(ps); cleaned.append(ps)
        plats = cleaned
    d["platforms"] = plats
    return {
        "id": d["id"],
        "companyName": d["company_name"],
        "companyBrand": d["company_brand"],
        "userType": d.get("user_type", "paid") or "paid",
        "isTemp": bool(d.get("is_temp", 0)),
        "platforms": d["platforms"],
        "optimizeStartDate": d.get("optimize_start_date", ""),
        "currentStatus": d.get("current_status", ""),
        "insightBullets": d.get("insight_bullets", ""),
        "nextWeekBullets": d.get("next_week_bullets", ""),
        "ownerId": d.get("owner_id"),
        "createdAt": d.get("created_at", ""),
        "updatedAt": d.get("updated_at", ""),
        "businessOwner": d.get("business_owner", "") or "",
        "ownerName": d.get("owner_name", "") or "",
        "deletedAt": d.get("deleted_at", "") or "",
        "status": d.get("status", "formal") or "formal",
        "teamId": d.get("team_id"),
        "promptModules": _parse_prompt_modules(d.get("prompt_modules")),
        "kpi": _parse_kpi(d.get("kpi_json")),
        "brandReportMode": d.get("brand_report_mode") or None,
        "dataShare": _parse_data_share(d.get("data_share_json")),
    }


# 账号数据共享:本账号报告从来源账号取指定范围数据(消费方配置)。
_DATA_SHARE_SCOPES = {"publish_cite", "kb", "search_rank", "publish_spend"}


def _parse_data_share(raw) -> Optional[dict]:
    if not raw:
        return None
    try:
        v = raw if isinstance(raw, dict) else json.loads(raw)
        sid = v.get("sourceAccountId")
        scopes = [s for s in (v.get("scopes") or []) if s in _DATA_SHARE_SCOPES]
        if not sid or not scopes:
            return None
        return {"sourceAccountId": int(sid), "scopes": scopes}
    except Exception:
        return None


def _normalize_data_share(value) -> Optional[dict]:
    """{sourceAccountId, scopes:[...]} → 清洗后的 dict;无效返回 None(=取消共享)。"""
    if not value or not isinstance(value, dict):
        return None
    try:
        sid = value.get("sourceAccountId") or value.get("source_account_id")
        scopes = [s for s in (value.get("scopes") or []) if s in _DATA_SHARE_SCOPES]
        if not sid or not scopes:
            return None
        return {"sourceAccountId": int(sid), "scopes": scopes}
    except Exception:
        return None


# KPI 三选项(支持多选,每项运营填纯文本目标,用于后期 KPI 结算)
_KPI_LABELS = {
    "hit":   "命中数/命中率",
    "top3":  "TOP3数/TOP3率",
    "first": "首位数/首位率",
}


def _normalize_kpi(value) -> list:
    """规范化 KPI 选项为存储形态:已选项列表 [{"type","label","text"}]。
    兼容前端传 list(已选项) 或 dict({type:{on,text}})。"""
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in _KPI_LABELS and isinstance(v, dict) and v.get("on"):
                out.append({"type": k, "label": _KPI_LABELS[k], "text": str(v.get("text") or "").strip()})
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("type") in _KPI_LABELS:
                k = item["type"]
                out.append({"type": k, "label": _KPI_LABELS[k], "text": str(item.get("text") or "").strip()})
    return out


def _parse_kpi(raw) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_prompt_modules(raw) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ═══════════════════════════════════════════
# Account Keywords
# ═══════════════════════════════════════════

def get_keywords(account_id: int) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM account_keyword WHERE account_id=%s ORDER BY sort_order ASC",
        (account_id,),
    )
    return [_keyword_to_dict(r) for r in rows]


def save_keywords(
    account_id: int,
    keywords: list[dict],
    changed_by: int | None = None,
    changed_by_name: str | None = None,
    changed_ip: str | None = None,
):
    now = _now()
    # 去重:同一 intent_prompt 只保留首次出现。查词按提示词去重,词库混入重复会让
    # "应查数"虚高、与实际查询数对不上(如 200 行里 19 个重复 → 实际只查 181 个唯一词)。
    _seen: set = set()
    _dedup: list = []
    for _kw in keywords:
        _p = (_kw.get("intentPrompt") or "").strip()
        if not _p or _p in _seen:
            continue
        _seen.add(_p)
        _dedup.append(_kw)
    keywords = _dedup
    with transaction() as conn:
        before_rows = _fetchall(
            conn,
            "SELECT intent_category, core_intent_word, intent_prompt, sort_order FROM account_keyword WHERE account_id=%s ORDER BY sort_order ASC",
            (account_id,),
        )
        before_snapshot = json.dumps([dict(r) for r in before_rows], ensure_ascii=False)
        after_snapshot = json.dumps([
            {
                "intent_category": kw.get("intentCategory", ""),
                "core_intent_word": kw.get("coreIntentWord", ""),
                "intent_prompt": kw.get("intentPrompt", ""),
                "sort_order": kw.get("sortOrder", i),
            }
            for i, kw in enumerate(keywords)
        ], ensure_ascii=False)
        _exec(conn,
            """INSERT INTO account_keyword_audit
               (account_id, changed_by, changed_by_name, changed_ip,
                before_count, after_count, before_snapshot, after_snapshot, changed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                account_id,
                changed_by,
                changed_by_name,
                changed_ip,
                len(before_rows),
                len(keywords),
                before_snapshot,
                after_snapshot,
                now,
            ),
        )
        _exec(conn, "DELETE FROM account_keyword WHERE account_id=%s", (account_id,))
        for i, kw in enumerate(keywords):
            _exec(conn,
                """INSERT INTO account_keyword
                   (account_id, intent_category, core_intent_word, intent_prompt, sort_order, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    account_id,
                    kw.get("intentCategory", ""),
                    kw.get("coreIntentWord", ""),
                    kw.get("intentPrompt", ""),
                    kw.get("sortOrder", i),
                    now,
                ),
            )


def promote_to_formal(account_id: int, platforms: list, keywords: list,
                      changed_by: int | None = None, changed_by_name: str | None = None) -> tuple:
    """初始客户(draft)转正:校验覆盖平台非空 + 关键词≥1,写 platforms + account_keyword,
    置 status='formal'。返回 (ok: bool, error: str, account: dict|None)。"""
    plats = [str(p).strip() for p in (platforms or []) if str(p or "").strip()]
    kws = [k for k in (keywords or [])
           if isinstance(k, dict) and (str(k.get("intentPrompt") or k.get("coreIntentWord") or "").strip())]
    if not plats:
        return False, "请至少选择 1 个覆盖平台", None
    if not kws:
        return False, "请至少录入 1 个关键词", None
    acc = get_account(account_id)
    if not acc:
        return False, "客户不存在", None
    norm_plats = plats
    try:
        from platforms import _normalize_platforms
        norm_plats = _normalize_platforms(plats)
    except Exception:
        pass
    # 先写关键词(复用 save_keywords,含审计 + 覆盖)
    save_keywords(account_id, kws, changed_by=changed_by, changed_by_name=changed_by_name)
    now = _now()
    with transaction() as conn:
        _exec(conn, "UPDATE account SET platforms=%s, status='formal', updated_at=%s WHERE id=%s",
              (json.dumps(norm_plats, ensure_ascii=False), now, account_id))
    _sync_account_platforms_to_schedules(account_id, norm_plats)
    return True, "", get_account(account_id)


def list_keyword_audits(account_id: int, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(
        conn,
        """SELECT id, account_id, changed_by, changed_by_name, changed_ip,
                  before_count, after_count, before_snapshot, after_snapshot, changed_at
           FROM account_keyword_audit
           WHERE account_id=%s
           ORDER BY id DESC
           LIMIT %s""",
        (account_id, int(limit)),
    )
    return [dict(r) for r in rows]


def _keyword_to_dict(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "accountId": d["account_id"],
        "intentCategory": d["intent_category"],
        "coreIntentWord": d["core_intent_word"],
        "intentPrompt": d["intent_prompt"],
        "sortOrder": d.get("sort_order", 0),
        "createdAt": d.get("created_at", ""),
    }


# ═══════════════════════════════════════════
# Search Task
# ═══════════════════════════════════════════

def create_search_task(task_id: str, account_id: int, total: int,
                       status: str = "RUNNING",
                       priority: int = 7,
                       source: str = "internal_manual",
                       bump_counter: bool = True) -> dict:
    """status='PENDING' 表示排队中，由 scheduler 挑出来执行；'RUNNING' 立即开跑（快速路径）。

    S3.1: bump_counter=False 用于"调用方已通过 try_acquire_running_slot 预占槽位
    （Lua 已 INCR）"的场景，避免 counter 双重 +2。
    """
    now = _now()
    with transaction() as conn:
        _exec(conn,
            """INSERT INTO search_task (id, account_id, status, total_queries,
               completed_queries, priority, source, created_at, last_heartbeat)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (task_id, account_id, status, total, 0, int(priority), source, now, now),
        )
    # S2.3: 快速路径创建即 RUNNING，需 INCR Redis 计数器
    # S3.1: bump_counter=False 时跳过（try_acquire 已预占 INCR）
    if status == "RUNNING" and bump_counter:
        _redis_bump_running_counter(+1)
    return {"taskId": task_id, "status": status, "total": total, "completed": 0,
            "priority": int(priority), "source": source}


# ═══════════════════════════════════════════
# Worker-daemon enqueue / claim (search_worker_daemon.py 用)
# ═══════════════════════════════════════════
import uuid as _uuid_wd  # local alias to avoid shadow on the import line above

def enqueue_search_task(account_id: int, kind: str, params: dict,
                        total: int = 0, priority: int = 7,
                        source: str = "internal_manual") -> str:
    """写一行 status='PENDING' 的 search_task,由 search_worker_daemon 拉走执行。
    kind: 'continue' | 'search' | 'retry' | 'sweep' | 'recheck' | 'external_pipeline'
    params: 任务参数(account_id/target_date/rescue_round 等),序列化进 params_json。
    返回 task_id。不抢占 concurrency slot — daemon 拉取时再抢。
    """
    import json as _json_wd
    tid = str(_uuid_wd.uuid4())
    now = _now()
    with transaction() as conn:
        _exec(conn,
            """INSERT INTO search_task
               (id, account_id, status, kind, params_json, total_queries,
                completed_queries, priority, source, created_at, last_heartbeat)
               VALUES (%s,%s,'PENDING',%s,%s,%s,0,%s,%s,%s,%s)""",
            (tid, account_id, kind, _json_wd.dumps(params, ensure_ascii=False),
             int(total), int(priority), source, now, now),
        )
    return tid


def enqueue_or_reuse_search_task(account_id: int, kind: str, params: dict,
                                 target_date: str, total: int = 0,
                                 priority: int = 7,
                                 source: str = "internal_manual") -> tuple[str, bool]:
    """enqueue 但优先复用当天最近一个"非运行/非排队"任务,保持「一次查词=一个任务」。
    解决 PR2 回归:enqueue_search_task 每次建新行,导致初次/补差/recheck 各占一行,
    执行历史窗口被拉长 + PENDING total=0 幽灵态。

    复用规则(基于 target_date):
      - 当天已有 RUNNING/PENDING 任务 → 直接返回其 id(去重,不再建新),reused=True
      - 当天有 COMPLETED/ERROR/CANCELLED 任务 → 复用最近一个,翻成 PENDING + 写新 params/total,
        reused=True
      - 当天无任何任务 → 新建 PENDING,reused=False
    返回 (task_id, reused)。
    """
    import json as _json_wd
    now = _now()
    with transaction() as conn:
        latest = _fetchone(conn,
            "SELECT id, status FROM search_task "
            "WHERE account_id=%s AND DATE(created_at)=%s "
            "ORDER BY created_at DESC LIMIT 1",
            (account_id, target_date))
        if latest:
            st = (latest.get("status") or "").upper()
            if st in ("RUNNING", "PENDING"):
                # 已有在跑/排队任务 → 去重,不建新
                return latest["id"], True
            # COMPLETED/ERROR/CANCELLED → 复用翻 PENDING
            tid = latest["id"]
            _exec(conn,
                "UPDATE search_task SET status='PENDING', kind=%s, params_json=%s, "
                "total_queries=%s, completed_queries=0, error_message='', "
                "completed_at=NULL, last_heartbeat=%s, last_progress_at=%s, "
                "priority=%s, source=%s WHERE id=%s",
                (kind, _json_wd.dumps(params, ensure_ascii=False), int(total),
                 now, now, int(priority), source, tid))
            return tid, True
        # 当天无任务 → 新建
        tid = str(_uuid_wd.uuid4())
        _exec(conn,
            """INSERT INTO search_task
               (id, account_id, status, kind, params_json, total_queries,
                completed_queries, priority, source, created_at, last_heartbeat)
               VALUES (%s,%s,'PENDING',%s,%s,%s,0,%s,%s,%s,%s)""",
            (tid, account_id, kind, _json_wd.dumps(params, ensure_ascii=False),
             int(total), int(priority), source, now, now))
        return tid, False


def claim_pending_search_task() -> dict | None:
    """原子拉取一个 PENDING 任务并切到 RUNNING。
    使用 FOR UPDATE SKIP LOCKED 避免 daemon 多 worker 重拉。
    返回 {id, account_id, kind, params(dict)} 或 None(队列空)。
    优先级:priority ASC, created_at ASC。
    """
    import json as _json_wd
    with transaction() as conn:
        # 只抢 daemon 自己 enqueue 的任务(params_json IS NOT NULL 是 daemon 所有权标记)。
        # 关键:start_search 在槽位满时也会建 PENDING(kind='search', params_json=NULL),
        # 那是给 scheduler.try_dispatch_pending 调度的,daemon 必须避开,否则会抢来
        # 当成不支持的 kind 直接标 ERROR,误杀 scheduler 队列。与 revive 同口径。
        row = _fetchone(conn,
            """SELECT id, account_id, kind, params_json, priority
               FROM search_task
               WHERE status='PENDING' AND params_json IS NOT NULL
               ORDER BY priority ASC, created_at ASC
               LIMIT 1 FOR UPDATE SKIP LOCKED""")
        if not row:
            return None
        now = _now()
        _exec(conn,
            "UPDATE search_task SET status='RUNNING', last_heartbeat=%s, "
            "last_progress_at=%s WHERE id=%s",
            (now, now, row["id"]))
    # commit 在 with 块退出时
    _redis_bump_running_counter(+1)
    try:
        params = _json_wd.loads(row.get("params_json") or "{}")
    except Exception:
        params = {}
    return {
        "id": row["id"],
        "account_id": int(row["account_id"]),
        "kind": (row.get("kind") or "search").strip(),
        "params": params,
    }


def mark_task_for_worker(task_id: str, kind: str, params: dict) -> None:
    """把【现有】 task 翻成 PENDING + kind + params_json,交 daemon 接管。
    用于 retry(复用原 task_id,不新建行);与 enqueue_or_reuse 区别:这里指定 task_id。
    写 params_json(NOT NULL)→ scheduler 的 list_pending 自动避开,只 daemon claim。
    """
    import json as _json_wd
    now = _now()
    with transaction() as conn:
        _exec(conn,
            "UPDATE search_task SET status='PENDING', kind=%s, params_json=%s, "
            "error_message='', completed_at=NULL, last_heartbeat=%s, last_progress_at=%s "
            "WHERE id=%s",
            (kind, _json_wd.dumps(params, ensure_ascii=False), now, now, task_id))


def revive_crashed_running_tasks(stale_seconds: int = 180) -> int:
    """daemon 启动时调用:把 daemon 所有权(params_json IS NOT NULL)的 RUNNING 任务、
    且 last_heartbeat 早于 stale_seconds 的复活回 PENDING,让 daemon 重新拉。
    避免 daemon 崩溃后任务永远 RUNNING 卡死。
    NOT NULL 过滤确保不会误伤 gunicorn 内运行的 legacy thread 路径。
    返回复活的行数。
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE search_task
                   SET status='PENDING', last_heartbeat=%s, last_progress_at=%s,
                       error_message=CONCAT('[revive] 上次 RUNNING 中断,自动重排队 @',%s)
                   WHERE status='RUNNING' AND params_json IS NOT NULL
                     AND last_heartbeat < NOW() - INTERVAL %s SECOND""",
                (_now(), _now(), _now(), int(stale_seconds)))
            return int(cur.rowcount or 0)


# ═══════════════════════════════════════════
# Search 任务调度 - 全局队列 + 优先级
# ═══════════════════════════════════════════

def count_running_search_tasks() -> int:
    """全局正在跑的 search_task 数（用于 scheduler 判断是否还有空位）。

    Stage 2.3: feature flag redis_concurrency_enabled=true 时优先 Redis (geo:concurrency:running)，
              cache miss / Redis 故障降级到 DB COUNT(*)。
    Redis 计数器由 _redis_bump_running_counter() 在状态切换时维护。
    """
    # 优先 Redis（feature flag ON 时）
    try:
        import redis_helper
        if redis_helper.is_enabled("redis_concurrency_enabled"):
            v = redis_helper.safe_get("concurrency:running", None)
            if v is not None:
                try:
                    return max(0, int(v))
                except (TypeError, ValueError):
                    pass
    except Exception:
        pass
    # DB fallback
    conn = get_conn()
    row = _fetchone(conn, "SELECT COUNT(*) AS c FROM search_task WHERE status='RUNNING'")
    return int((row or {}).get("c") or 0)


def _redis_bump_running_counter(delta: int) -> None:
    """状态切换时调用：delta=+1 进入 RUNNING；delta=-1 退出 RUNNING。
    任何异常都吞掉，不影响 DB 主流程。redis_concurrency_enabled OFF 时 no-op。
    """
    try:
        import redis_helper
        if not redis_helper.is_enabled("redis_concurrency_enabled"):
            return
        if delta > 0:
            redis_helper.safe_incr("concurrency:running", amount=delta)
        elif delta < 0:
            redis_helper.safe_decr("concurrency:running", amount=-delta)
    except Exception:
        pass


def sync_running_counter_from_db() -> int:
    """从 DB 真实 RUNNING 数校准 Redis 计数器（防漂移）。
    scheduler_daemon 每 tick 调用一次。返回校准后的值。
    """
    try:
        conn = get_conn()
        row = _fetchone(conn, "SELECT COUNT(*) AS c FROM search_task WHERE status='RUNNING'")
        real = int((row or {}).get("c") or 0)
        import redis_helper
        if redis_helper.is_enabled("redis_concurrency_enabled"):
            redis_helper.safe_set("concurrency:running", real, ex=3600)
        return real
    except Exception:
        return 0


def try_acquire_running_slot(max_concurrent: int) -> bool:
    """原子 CAS：尝试占用一个 RUNNING 槽位。返回 True 表示获得。
    Stage 2.3: feature flag ON 时用 Redis Lua 脚本 GET-and-INCR-if-less-than（无竞态）；
              flag OFF 时降级到 DB SELECT COUNT + 判断（保留旧 check-then-act 语义）。

    释放路径(两选一,不要同时):
      1. **正常路径**:create_search_task / promote_pending_to_running 用 bump_counter=False
         + 任务正常结束时 update_search_task_status() 自动 _redis_bump_running_counter(-1)。
      2. **异常路径**:还没进 RUNNING 就 raise(create 失败等) → 必须主动调
         release_running_slot() 释放,否则 counter 泄漏直到下次重启。
    切勿在同一条 try 里同时走 update_search_task_status('COMPLETED') 和 release_running_slot(),
    那会 -2 让 counter 变负。
    """
    try:
        import redis_helper
        if redis_helper.is_enabled("redis_concurrency_enabled"):
            # Lua 原子操作：GET current；if < max → INCR 返回 1；else 返回 0
            lua = """
            local cur = tonumber(redis.call('GET', KEYS[1]) or 0)
            local maxv = tonumber(ARGV[1])
            if cur < maxv then
                redis.call('INCR', KEYS[1])
                return 1
            else
                return 0
            end
            """
            result = redis_helper.safe_eval(lua, ["concurrency:running"],
                                            [int(max_concurrent)], default=None)
            if result is not None:
                return int(result) == 1
    except Exception:
        pass
    # 降级：旧 check-then-act（有竞态但向后兼容）
    return count_running_search_tasks() < int(max_concurrent)


def release_running_slot() -> None:
    """S3.1: 释放一个由 try_acquire_running_slot 预占的槽位（counter -1）。
    用于 try_acquire 成功后、任务未真正进入 RUNNING 就失败的回滚，防 counter 泄漏。
    flag OFF 时 no-op（降级路径没 INCR，无需 release）。
    """
    _redis_bump_running_counter(-1)


def set_task_override_payload(task_id: str, payload: dict) -> None:
    """S3.5: 持久化 PENDING 任务的 override 入参，让 scheduler 跨进程能正确重建。
    写失败不抛（rebuild 会退回全量行为，不致命）。"""
    try:
        import json as _json
        with transaction() as conn:
            _exec(conn, "UPDATE search_task SET override_payload=%s WHERE id=%s",
                  (_json.dumps(payload, ensure_ascii=False), task_id))
    except Exception:
        pass


def get_task_override_payload(task_id: str) -> Optional[dict]:
    """S3.5: 读取 PENDING 任务持久化的 override 入参。无/解析失败返回 None。"""
    try:
        import json as _json
        conn = get_conn()
        row = _fetchone(conn,
            "SELECT override_payload FROM search_task WHERE id=%s", (task_id,))
        raw = (row or {}).get("override_payload")
        if not raw:
            return None
        d = _json.loads(raw)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def list_pending_search_tasks(limit: int = 10) -> list[dict]:
    """取待执行的 task。

    S3.3 账户公平：feature flag fair_dispatch_enabled=true 时，在 priority 之后
    按"该账户当前 RUNNING 任务数"升序——已占多个槽位的账户的 PENDING 排后面，
    防单账户提交一批任务霸占全局槽位饿死其它账户。flag OFF 退回纯 FIFO（零回归）。
    """
    conn = get_conn()
    fair = False
    try:
        import redis_helper
        fair = redis_helper.is_enabled("fair_dispatch_enabled")
    except Exception:
        fair = False

    # 关键:scheduler 只调度 legacy 任务(params_json IS NULL)。daemon enqueue 的
    # 任务(params_json IS NOT NULL)由 search_worker_daemon 通过 claim_pending_search_task
    # 拉走,两个队列必须按 params_json 互斥,否则 scheduler 会抢走 continue 任务并用
    # 全量词库重建 ctx 跑成完整重查(而非只补 missing)。与 claim_pending_search_task 对称。
    if fair:
        rows = _fetchall(conn,
            "SELECT pt.id, pt.account_id, pt.total_queries, pt.priority, pt.source, "
            "pt.created_at "
            "FROM search_task pt "
            "LEFT JOIN (SELECT account_id, COUNT(*) AS rc FROM search_task "
            "           WHERE status='RUNNING' GROUP BY account_id) r "
            "  ON r.account_id = pt.account_id "
            "WHERE pt.status='PENDING' AND pt.params_json IS NULL "
            "ORDER BY pt.priority DESC, COALESCE(r.rc,0) ASC, pt.created_at ASC "
            "LIMIT %s",
            (int(limit),))
    else:
        rows = _fetchall(conn,
            "SELECT id, account_id, total_queries, priority, source, created_at "
            "FROM search_task WHERE status='PENDING' AND params_json IS NULL "
            "ORDER BY priority DESC, created_at ASC LIMIT %s",
            (int(limit),))
    return list(rows)


def get_pending_position(task_id: str) -> int:
    """返回该 task 在 PENDING 队列里的位置（1-based），不在队列里返回 0。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT id, priority, created_at FROM search_task WHERE id=%s", (task_id,))
    if not row or row.get("priority") is None:
        return 0
    cur = get_conn().cursor()
    cur.execute(
        "SELECT COUNT(*) AS c FROM search_task WHERE status='PENDING' AND ("
        "  priority > %s OR (priority = %s AND created_at < %s)"
        ")",
        (row["priority"], row["priority"], row["created_at"]))
    r = cur.fetchone()
    cur.close()
    return int((r or {}).get("c", 0)) + 1


def count_running_by_account(account_id: int) -> int:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM search_task "
        "WHERE account_id=%s AND status IN ('PENDING','RUNNING')",
        (account_id,))
    return int((row or {}).get("c") or 0)


def count_running_by_external_ip(ip: str) -> int:
    """同 IP 在 external_use 里 status NOT IN (completed, failed) 的数量。"""
    if not ip:
        return 0
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM external_use "
        "WHERE ip=%s AND status NOT IN ('completed', 'failed')",
        (ip[:45],))
    return int((row or {}).get("c") or 0)


def count_running_by_invite(invite_id: int) -> int:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM external_use "
        "WHERE invite_id=%s AND status NOT IN ('completed', 'failed')",
        (int(invite_id),))
    return int((row or {}).get("c") or 0)


def promote_pending_to_running(task_id: str, bump_counter: bool = True) -> bool:
    """把 PENDING 改成 RUNNING（原子操作，幂等）。返回是否成功改了。

    S3.1: bump_counter=False 用于 try_dispatch_pending 已先调 try_acquire_running_slot
    预占槽位的场景，避免 counter 双重 +2。
    """
    with transaction() as conn:
        cur = _exec(conn,
            "UPDATE search_task SET status='RUNNING', last_heartbeat=%s "
            "WHERE id=%s AND status='PENDING'",
            (_now(), task_id))
        try:
            ok = cur.rowcount > 0
        except Exception:
            ok = False
    if ok and bump_counter:
        _redis_bump_running_counter(+1)  # S2.3
    return ok


def touch_search_task_heartbeat(task_id: str) -> None:
    conn = get_conn()
    _exec(conn, "UPDATE search_task SET last_heartbeat=%s WHERE id=%s", (_now(), task_id))
    conn.commit()


def update_search_task_progress(task_id: str, completed: int, current_keyword: str = ""):
    conn = get_conn()
    # S3.2: 同步 last_progress_at，供头部阻塞抢占精准判卡死（进度真在推进就不会被误判）
    _exec(conn,
        "UPDATE search_task SET completed_queries=%s, current_keyword=%s, "
        "last_progress_at=%s WHERE id=%s",
        (completed, current_keyword, _now(), task_id),
    )
    conn.commit()


def update_search_task_status(task_id: str, status: str, error_msg: str = ""):
    now = _now()
    conn = get_conn()
    # S2.3: 查 old_status，跨越 RUNNING 边界时维护 Redis 计数器
    old_status = ""
    try:
        row = _fetchone(conn, "SELECT status FROM search_task WHERE id=%s", (task_id,))
        old_status = (row or {}).get("status") or ""
    except Exception:
        pass
    _exec(conn,
        "UPDATE search_task SET status=%s, error_message=%s, completed_at=%s WHERE id=%s",
        (status, error_msg, now if status in ("COMPLETED", "ERROR", "CANCELLED") else "", task_id),
    )
    conn.commit()
    
    # 【修复Duration=0】当search_task完成时，更新关联的scheduled_task_history记录
    if status in ("COMPLETED", "ERROR", "CANCELLED") and old_status == "RUNNING":
        try:
            _update_history_duration_on_task_complete(conn, task_id, now)
        except Exception as hist_err:
            logger.warning("[update_search_task] 更新历史耗时失败: %s", hist_err)
    
    # S2.3: counter 维护
    if old_status == "RUNNING" and status in ("COMPLETED", "ERROR", "CANCELLED"):
        _redis_bump_running_counter(-1)
    elif old_status != "RUNNING" and status == "RUNNING":
        _redis_bump_running_counter(+1)


def _update_history_duration_on_task_complete(conn, task_id: str, completed_time: str):
    """当search_task完成时，更新关联的scheduled_task_history的duration和finished_at"""
    # 【调试】写入日志确认函数被调用
    try:
        with open(r'C:\Users\Administrator\Desktop\geo-ops-system\_duration_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"[{completed_time}] _update_history_duration called: task_id={task_id[:12]}\n")
    except: pass
    
    # 查找与此task_id关联的最近一条历史记录（且duration=0或很小的）
    history_row = _fetchone(conn,
        """SELECT id, sched_id, started_at, finished_at, duration_seconds, status 
           FROM scheduled_task_history 
           WHERE task_id=%s 
           ORDER BY id DESC LIMIT 1""",  # 【修复】移除 duration_seconds <= 5 条件
        (task_id,)
    )
    
    if not history_row:
        try:
            with open(r'C:\Users\Administrator\Desktop\geo-ops-system\_duration_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"  -> No history found for task_id={task_id[:12]}\n")
        except: pass
        return
    
    hist_id = history_row.get('id')
    started_at = str(history_row.get('started_at') or '')[:19]
    
    if not started_at:
        return
    
    try:
        start_dt = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(completed_time[:19], "%Y-%m-%d %H:%M:%S")
        duration = int((end_dt - start_dt).total_seconds())
        
        # 【修复】即使 duration <= 0 也更新（使用 completed_time 作为 finished_at）
        if duration >= 0:  # 允许 0 或正数
            _exec(conn,
                """UPDATE scheduled_task_history 
                   SET finished_at=%s, duration_seconds=%s, status=%s 
                   WHERE id=%s""",
                (completed_time[:19], max(duration, 1), "COMPLETED", hist_id)  // 至少1秒
            )
            conn.commit()
            
            # 【调试】记录更新结果
            try:
                with open(r'C:\Users\Administrator\Desktop\geo-ops-system\_duration_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"  -> UPDATED hist#{hist_id}: duration={max(duration,1)}s, finished={completed_time[:19]}\n")
            except: pass
            
            logger.info("[History-Duration] 已更新历史 #%s: duration=%ds, finished_at=%s", 
                       hist_id, max(duration, 1), completed_time[:19])
    except Exception as e:
        logger.warning("[History-Duration] 时间计算失败: %s", e)


def get_search_task(task_id: str) -> Optional[dict]:
    conn = get_conn()
    d = _fetchone(conn, "SELECT * FROM search_task WHERE id=%s", (task_id,))
    if not d:
        return None
    total = d.get("total_queries") or 0
    completed = d.get("completed_queries") or 0
    source = d.get("source", "internal_manual")
    # 根据 source 判断是否为重试任务
    retry_type = None
    pending_pairs = []
    if source == "retry_failed":
        retry_type = "failed"
        # 查询该账号最新已完成任务的失败记录作为 pendingPairs
        account_id = d.get("account_id")
        if account_id:
            try:
                # 找到该账号最新的 COMPLETED 任务
                latest = _fetchone(conn, """
                    SELECT id FROM search_task 
                    WHERE account_id=%s AND status='COMPLETED'
                    ORDER BY created_at DESC LIMIT 1
                """, (account_id,))
                if latest:
                    # 获取该任务的失败记录
                    rows = _fetchall(conn, """
                        SELECT keyword, platform, model 
                        FROM search_result 
                        WHERE task_id=%s AND success=0
                    """, (latest["id"],))
                    pending_pairs = [{"keyword": r["keyword"], "platform": r["platform"], "model": r.get("model", "")} for r in rows]
            except Exception as e:
                logger.warning("[get_search_task] 查询retry pendingPairs失败: %s", e)
    elif source == "retry_continue":
        retry_type = "continue"
    
    result = {
        "taskId": d["id"],
        "accountId": d.get("account_id"),
        "status": d["status"],
        "total": total,
        "completed": completed,
        "currentKeyword": d.get("current_keyword", ""),
        "percentage": round(completed / total * 100) if total else 0,
        "errorMessage": d.get("error_message", ""),
        "createdAt": d.get("created_at", ""),
        "completedAt": d.get("completed_at", ""),
        "priority": d.get("priority", 7),
        "source": source,
        "retryType": retry_type,
        "lastHeartbeat": d.get("last_heartbeat", ""),
        "lastProgressAt": d.get("last_progress_at", ""),
    }
    # 只有当查到有效的 pendingPairs 时才返回（避免空数组覆盖前端已有的数据）
    if pending_pairs:
        result["pendingPairs"] = pending_pairs
    return result


def is_search_cancelled(task_id: str) -> bool:
    conn = get_conn()
    row = _fetchone(conn, "SELECT status FROM search_task WHERE id=%s", (task_id,))
    return row and row["status"] == "CANCELLED"


def cancel_search_task(task_id: str):
    update_search_task_status(task_id, "CANCELLED")


# ═══════════════════════════════════════════
# Cross-worker cancel signal
# ═══════════════════════════════════════════

def request_cancel(task_id: str) -> None:
    with transaction() as conn:
        _exec(conn,
            "REPLACE INTO cancel_signal (task_id, requested_at) VALUES (%s,%s)",
            (task_id, _now()),
        )


def is_cancel_requested(task_id: str) -> bool:
    if not task_id:
        return False
    conn = get_conn()
    row = _fetchone(conn, "SELECT 1 FROM cancel_signal WHERE task_id=%s", (task_id,))
    return row is not None


def clear_cancel(task_id: str) -> None:
    if not task_id:
        return
    with transaction() as conn:
        _exec(conn, "DELETE FROM cancel_signal WHERE task_id=%s", (task_id,))


# ═══════════════════════════════════════════
# Admin auth
# ═══════════════════════════════════════════

def admin_user_exists() -> bool:
    conn = get_conn()
    row = _fetchone(conn, "SELECT 1 FROM admin_user LIMIT 1")
    return row is not None


def create_admin_user(username: str, password_hash: str, is_super: int = 0,
                     role: str = "operator", permissions: str = "[]") -> int:
    """is_super 形参保留作向后兼容，**不再使用**——角色全靠 role 字段。"""
    with transaction() as conn:
        cur = _exec(conn,
            "INSERT INTO admin_user (username, password_hash, role, permissions, created_at) VALUES (%s,%s,%s,%s,%s)",
            (username, password_hash, role, permissions, _now()),
        )
        return cur.lastrowid


def get_admin_user_by_name(username: str) -> Optional[dict]:
    conn = get_conn()
    return _fetchone(conn, "SELECT * FROM admin_user WHERE username=%s", (username,))


def get_admin_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    return _fetchone(conn, "SELECT * FROM admin_user WHERE id=%s", (user_id,))


def list_admin_users() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT u.id, u.username, u.role, u.role_id, u.permissions, u.team_id, "
        "       u.created_at, u.last_login_at, "
        "       r.name AS role_name, r.code AS role_code, r.data_scope, "
        "       t.name AS team_name "
        "FROM admin_user u LEFT JOIN role r ON r.id = u.role_id "
        "LEFT JOIN team t ON t.id = u.team_id "
        "ORDER BY u.id"
    )
    results = []
    for r in rows:
        perms = []
        try:
            perms = json.loads(r.get("permissions") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        role_code = r.get("role_code") or r.get("role") or "operator"
        results.append({
            "id":            r["id"],
            "username":      r["username"],
            "isSuperAdmin":  role_code == "super_admin",  # 兼容旧前端字段
            "role":          role_code,                    # 字符串 code（兼容旧前端）
            "roleId":        r.get("role_id"),
            "roleName":      r.get("role_name") or "",     # 中文名给前端显示
            "dataScope":     r.get("data_scope") or "self",
            "teamId":        r.get("team_id"),
            "teamName":      r.get("team_name") or "",
            "permissions":   perms,                        # 旧字段，废弃中
            "createdAt":     r.get("created_at") or "",
            "lastLoginAt":   r.get("last_login_at") or "",
        })
    return results


def delete_admin_user(user_id: int) -> None:
    """实际删除：上层 endpoint 已按 role 校验过，这里直接按 id 删。
    历史 DB 里部分账号 is_super_admin=1 是脏数据，不能再用此字段做安全栅栏。"""
    with transaction() as conn:
        cur = _exec(conn, "DELETE FROM admin_user WHERE id=%s AND role <> 'super_admin'", (user_id,))
        try:
            n = cur.rowcount
        except Exception:
            n = -1
        if n == 0:
            raise ValueError(f"删除失败：用户 {user_id} 不存在或为超级管理员")


def touch_admin_last_login(user_id: int) -> None:
    conn = get_conn()
    _exec(conn, "UPDATE admin_user SET last_login_at=%s WHERE id=%s", (_now(), user_id))
    conn.commit()




def update_admin_user(user_id: int, role: str = None, permissions: str = None) -> None:
    parts = []
    vals = []
    if role is not None:
        parts.append("role=%s")
        vals.append(role)
    if permissions is not None:
        parts.append("permissions=%s")
        vals.append(permissions)
    if not parts:
        return
    vals.append(user_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE admin_user SET {','.join(parts)} WHERE id=%s", tuple(vals))

def update_admin_password(user_id: int, password_hash: str) -> None:
    with transaction() as conn:
        _exec(conn, "UPDATE admin_user SET password_hash=%s WHERE id=%s", (password_hash, user_id))


def assign_user_role(user_id: int, role_id: int, role_code: str) -> None:
    """同步写 role_id（新）和 role 字符串（兼容老代码）。"""
    with transaction() as conn:
        _exec(conn,
            "UPDATE admin_user SET role_id=%s, role=%s WHERE id=%s",
            (role_id, role_code, user_id),
        )


# ═══════════════════════════════════════════
# Role / RBAC
# ═══════════════════════════════════════════

def get_role_pages(role_id: int) -> list[str]:
    conn = get_conn()
    rows = _fetchall(conn, "SELECT page_key FROM role_page WHERE role_id=%s", (role_id,))
    return [r["page_key"] for r in rows]


def set_role_pages(role_id: int, page_keys: list[str]) -> None:
    """全量替换 role 的 page_keys。空数组 = 没任何页面权限。"""
    with transaction() as conn:
        _exec(conn, "DELETE FROM role_page WHERE role_id=%s", (role_id,))
        for k in (page_keys or []):
            _exec(conn, "INSERT INTO role_page (role_id, page_key) VALUES (%s, %s)", (role_id, k))


def list_roles() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, name, code, data_scope, is_builtin, description, created_at, updated_at "
        "FROM role ORDER BY is_builtin DESC, id"
    )
    results = []
    for r in rows:
        pages = get_role_pages(r["id"])
        # 统计绑定该角色的用户数
        cnt_row = _fetchone(get_conn(), "SELECT COUNT(*) AS c FROM admin_user WHERE role_id=%s", (r["id"],))
        results.append({
            "id":          r["id"],
            "name":        r["name"],
            "code":        r["code"],
            "dataScope":   r["data_scope"],
            "isBuiltin":   bool(r["is_builtin"]),
            "description": r["description"] or "",
            "pages":       pages,
            "userCount":   int(cnt_row["c"] if cnt_row else 0),
            "createdAt":   r.get("created_at") or "",
            "updatedAt":   r.get("updated_at") or "",
        })
    return results


def get_role(role_id: int) -> Optional[dict]:
    conn = get_conn()
    r = _fetchone(conn, "SELECT * FROM role WHERE id=%s", (role_id,))
    if not r:
        return None
    return {
        "id":          r["id"],
        "name":        r["name"],
        "code":        r["code"],
        "dataScope":   r["data_scope"],
        "isBuiltin":   bool(r["is_builtin"]),
        "description": r.get("description") or "",
        "pages":       get_role_pages(r["id"]),
        "createdAt":   r.get("created_at") or "",
        "updatedAt":   r.get("updated_at") or "",
    }


def get_role_by_code(code: str) -> Optional[dict]:
    conn = get_conn()
    r = _fetchone(conn, "SELECT id FROM role WHERE code=%s", (code,))
    if not r:
        return None
    return get_role(r["id"])


def create_role(name: str, code: str, data_scope: str = "self",
                description: str = "", page_keys: Optional[list] = None,
                is_builtin: int = 0) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            "INSERT INTO role (name, code, data_scope, is_builtin, description, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (name, code, data_scope, is_builtin, description, now, now),
        )
        rid = cur.lastrowid
    if page_keys:
        set_role_pages(rid, page_keys)
    return rid


def update_role(role_id: int, name: Optional[str] = None,
                data_scope: Optional[str] = None,
                description: Optional[str] = None,
                page_keys: Optional[list] = None) -> None:
    parts = []
    vals: list = []
    if name is not None:
        parts.append("name=%s"); vals.append(name)
    if data_scope is not None:
        parts.append("data_scope=%s"); vals.append(data_scope)
    if description is not None:
        parts.append("description=%s"); vals.append(description)
    if parts:
        parts.append("updated_at=%s"); vals.append(_now())
        vals.append(role_id)
        with transaction() as conn:
            _exec(conn, f"UPDATE role SET {','.join(parts)} WHERE id=%s", tuple(vals))
    if page_keys is not None:
        set_role_pages(role_id, page_keys)


def delete_role(role_id: int) -> None:
    """删除前检查：① 内置不可删 ② 还有用户绑定不可删（上层自己处理 reassign）。"""
    role = get_role(role_id)
    if not role:
        raise ValueError("角色不存在")
    if role["isBuiltin"]:
        raise ValueError("内置角色不可删除")
    cnt = _fetchone(get_conn(), "SELECT COUNT(*) AS c FROM admin_user WHERE role_id=%s", (role_id,))
    if cnt and int(cnt["c"]) > 0:
        raise ValueError(f"该角色还有 {cnt['c']} 个用户绑定，请先改派或删除这些用户")
    with transaction() as conn:
        _exec(conn, "DELETE FROM role_page WHERE role_id=%s", (role_id,))
        _exec(conn, "DELETE FROM role WHERE id=%s", (role_id,))


# ═══════════════════════════════════════════
# External invite (无登录入口邀请码 + 使用记录)
# ═══════════════════════════════════════════

def _apply_monthly_reset(r: dict) -> dict:
    """长期邀请码惰性月重置:读到时若已跨月,used_count 归零、复活 active。"""
    if not r:
        return r
    if (r.get("invite_type") or "temporary") != "long_term":
        return r
    cur_month = datetime.now().strftime("%Y-%m")
    if (r.get("usage_period") or "") != cur_month:
        try:
            with transaction() as conn:
                _exec(conn,
                    "UPDATE external_invite SET used_count=0, usage_period=%s, status='active', updated_at=%s WHERE id=%s",
                    (cur_month, _now(), r["id"]))
            r["used_count"] = 0
            r["usage_period"] = cur_month
            r["status"] = "active"
        except Exception:
            pass
    return r


def _invite_to_dict(r: dict) -> dict:
    if not r:
        return None
    r = _apply_monthly_reset(r)
    try:
        platforms = json.loads(r.get("allowed_platforms") or "[]")
    except (json.JSONDecodeError, TypeError):
        platforms = []
    return {
        "id":               r["id"],
        "code":             r["code"],
        "description":      r.get("description") or "",
        "inviteType":       r.get("invite_type") or "temporary",
        "usagePeriod":      r.get("usage_period") or "",
        "maxUses":          int(r["max_uses"]),
        "usedCount":        int(r["used_count"]),
        "remaining":        max(0, int(r["max_uses"]) - int(r["used_count"])),
        "maxKeywords":      int(r["max_keywords"]),
        "allowedPlatforms": platforms,
        "expiresAt":        r.get("expires_at") or "",
        "createdBy":        r.get("created_by"),
        "status":           r.get("status") or "active",
        "createdAt":        r.get("created_at") or "",
        "updatedAt":        r.get("updated_at") or "",
    }


def list_invites() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn, "SELECT * FROM external_invite ORDER BY id DESC")
    return [_invite_to_dict(r) for r in rows]


def get_invite_by_id(invite_id: int) -> Optional[dict]:
    conn = get_conn()
    return _invite_to_dict(_fetchone(conn, "SELECT * FROM external_invite WHERE id=%s", (invite_id,)))


def get_invite_by_code(code: str) -> Optional[dict]:
    conn = get_conn()
    return _invite_to_dict(_fetchone(conn, "SELECT * FROM external_invite WHERE code=%s", (code,)))


def create_invite(code: str, description: str = "", max_uses: int = 3,
                  max_keywords: int = 100, allowed_platforms: Optional[list] = None,
                  expires_at: str = "", created_by: Optional[int] = None,
                  invite_type: str = "temporary") -> int:
    now = _now()
    invite_type = "long_term" if invite_type == "long_term" else "temporary"
    usage_period = datetime.now().strftime("%Y-%m") if invite_type == "long_term" else None
    platforms_json = json.dumps(allowed_platforms or ["豆包", "DeepSeek"], ensure_ascii=False)
    with transaction() as conn:
        cur = _exec(conn,
            "INSERT INTO external_invite (code, description, max_uses, max_keywords, allowed_platforms, "
            "expires_at, created_by, invite_type, usage_period, status, created_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s)",
            (code, description, int(max_uses), int(max_keywords), platforms_json,
             expires_at or None, created_by, invite_type, usage_period, now, now),
        )
        return cur.lastrowid


def update_invite(invite_id: int, **fields) -> None:
    parts, vals = [], []
    fmap = {
        "description":      ("description", lambda v: str(v)),
        "maxUses":          ("max_uses", lambda v: int(v)),
        "maxKeywords":      ("max_keywords", lambda v: int(v)),
        "allowedPlatforms": ("allowed_platforms", lambda v: json.dumps(v or [], ensure_ascii=False)),
        "expiresAt":        ("expires_at", lambda v: str(v) if v else None),
        "status":           ("status", lambda v: str(v)),
        "inviteType":       ("invite_type", lambda v: "long_term" if v == "long_term" else "temporary"),
    }
    for k, v in fields.items():
        if k in fmap and v is not None:
            col, conv = fmap[k]
            parts.append(f"{col}=%s")
            vals.append(conv(v))
    if not parts:
        return
    # 改为长期码时,若无计数周期则初始化为当月
    if fields.get("inviteType") == "long_term":
        parts.append("usage_period=COALESCE(usage_period,%s)")
        vals.append(datetime.now().strftime("%Y-%m"))
    parts.append("updated_at=%s"); vals.append(_now())
    vals.append(invite_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE external_invite SET {','.join(parts)} WHERE id=%s", tuple(vals))


def delete_invite(invite_id: int) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM external_use WHERE invite_id=%s", (invite_id,))
        _exec(conn, "DELETE FROM external_invite WHERE id=%s", (invite_id,))


def increment_invite_usage(invite_id: int) -> None:
    """used_count+=1，到上限时自动改 status='exhausted'。"""
    with transaction() as conn:
        _exec(conn, "UPDATE external_invite SET used_count=used_count+1, updated_at=%s WHERE id=%s",
              (_now(), invite_id))
        _exec(conn,
              "UPDATE external_invite SET status='exhausted' "
              "WHERE id=%s AND status='active' AND used_count >= max_uses",
              (invite_id,))


# —— external_use ——

def _use_to_dict(r: dict) -> Optional[dict]:
    if not r:
        return None
    try:
        platforms = json.loads(r.get("platforms") or "[]")
    except (json.JSONDecodeError, TypeError):
        platforms = []
    return {
        "id":              r["id"],
        "inviteId":        r["invite_id"],
        "accountId":       r.get("account_id"),
        "weeklyReportId":  r.get("weekly_report_id"),
        "brandName":       r.get("brand_name") or "",
        "brandMode":       r.get("brand_mode") or "single",
        "keywordsCount":   int(r.get("keywords_count") or 0),
        "platforms":       platforms,
        "sharePassword":   r.get("share_password") or "",
        "status":          r.get("status") or "pending",
        "progressPercent": int(r.get("progress_percent") or 0),
        "progressMessage": r.get("progress_message") or "",
        "errorMessage":    r.get("error_message") or "",
        "ip":              r.get("ip") or "",
        "userAgent":       r.get("user_agent") or "",
        "createdAt":       r.get("created_at") or "",
        "completedAt":     r.get("completed_at") or "",
        "notifyEmail":     r.get("notify_email") or "",
    }


def create_external_use(invite_id: int, brand_name: str, keywords: list,
                        platforms: list, share_password: str,
                        modules: Optional[list] = None,
                        ip: str = "", user_agent: str = "",
                        notify_email: str = "",
                        brand_mode: str = "single") -> int:
    """keywords 是关键词列表（字符串数组），持久化为 JSON 到 keywords_text。
    modules: 选中的报告模块 key 数组，None=全选（pipeline 端处理）。
    notify_email: 可选；报告完成时自动发件通知该邮箱。
    brand_mode: 'single'(默认,同品牌别名合并) / 'multi'(集团旗下多个独立子品牌,逐个独立分析)。"""
    now = _now()
    kws = list(keywords or [])
    mode = "multi" if str(brand_mode).lower() == "multi" else "single"
    with transaction() as conn:
        cur = _exec(conn,
            "INSERT INTO external_use (invite_id, brand_name, brand_mode, keywords_count, keywords_text, platforms, modules, "
            "share_password, status, progress_percent, progress_message, ip, user_agent, notify_email, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',0,'已提交，等待执行',%s,%s,%s,%s)",
            (invite_id, brand_name, mode, len(kws),
             json.dumps(kws, ensure_ascii=False),
             json.dumps(platforms or [], ensure_ascii=False),
             json.dumps(modules, ensure_ascii=False) if modules is not None else None,
             share_password, ip[:45], user_agent[:500], (notify_email or "")[:255], now),
        )
        return cur.lastrowid


def get_external_use_modules(use_id: int) -> Optional[list[str]]:
    """读取 external_use 选中的模块。None 或 [] 都视为全选。"""
    conn = get_conn()
    row = _fetchone(conn, "SELECT modules FROM external_use WHERE id=%s", (use_id,))
    if not row or not row.get("modules"):
        return None
    try:
        data = json.loads(row["modules"])
        return data if isinstance(data, list) and data else None
    except (json.JSONDecodeError, TypeError):
        return None


def get_external_use_keywords(use_id: int) -> list[str]:
    """读取 external_use 持久化的关键词原文。"""
    conn = get_conn()
    row = _fetchone(conn, "SELECT keywords_text FROM external_use WHERE id=%s", (use_id,))
    if not row or not row.get("keywords_text"):
        return []
    try:
        data = json.loads(row["keywords_text"])
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def update_external_use(use_id: int, **fields) -> None:
    """支持字段：account_id, weekly_report_id, status, progress_percent, progress_message,
    error_message, completed_at

    P5 (2026-05-19) 防御性截断：
      progress_message VARCHAR(500) — 截到 490（留 buffer 给 utf8mb4 多字节字符）
      error_message    TEXT          — 截到 1000（DB 装得下但避免日志爆炸）
    """
    parts, vals = [], []
    fmap = {
        "account_id":       "account_id",
        "weekly_report_id": "weekly_report_id",
        "status":           "status",
        "progress_percent": "progress_percent",
        "progress_message": "progress_message",
        "error_message":    "error_message",
        "completed_at":     "completed_at",
    }
    for k, v in fields.items():
        if k in fmap and v is not None:
            # P5: 长字段防御性截断，避免上游错误消息透传爆 1406
            if k == "progress_message" and isinstance(v, str) and len(v) > 490:
                v = v[:487] + "..."
            elif k == "error_message" and isinstance(v, str) and len(v) > 1000:
                v = v[:997] + "..."
            parts.append(f"{fmap[k]}=%s")
            vals.append(v)
    if not parts:
        return
    vals.append(use_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE external_use SET {','.join(parts)} WHERE id=%s", tuple(vals))


def get_external_use(use_id: int) -> Optional[dict]:
    conn = get_conn()
    return _use_to_dict(_fetchone(conn, "SELECT * FROM external_use WHERE id=%s", (use_id,)))


def list_uses_by_invite(invite_id: int, limit: int = 100) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM external_use WHERE invite_id=%s ORDER BY id DESC LIMIT %s",
        (invite_id, int(limit)))
    return [_use_to_dict(r) for r in rows]


def get_latest_failed_external_use_for_account(account_id: int) -> Optional[dict]:
    """补查完成后自动续报告用:取该账号最近一条 failed 且未出报告的外部邀请任务。
    不限定 error_message 文案(60% 门失败带的是友好提示,不含 TIMEOUT,
    所以 recover_timeout 的 LIKE 过滤抓不到,这里专门补上)。"""
    if not account_id:
        return None
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT * FROM external_use "
        "WHERE account_id=%s AND status='failed' AND weekly_report_id IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (account_id,))
    return _use_to_dict(row) if row else None


def try_claim_external_use_for_resume(use_id: int) -> bool:
    """原子认领待续跑的外部任务:仅当当前仍是 failed+无报告时,把状态推进到 reporting。
    返回 True 表示认领成功(本进程负责续跑一次);False 表示已被他处认领/状态已变。
    用于跨进程防重(daemon 补查钩子 vs scheduler recover 不会对同一 use 双跑)。"""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE external_use SET status='reporting', "
                "progress_message=%s "
                "WHERE id=%s AND status='failed' AND weekly_report_id IS NULL",
                ("[自动恢复] 补查完成，正在重新生成报告", use_id))
            claimed = (cur.rowcount or 0) == 1
    return claimed


# —— 邀请码爆破限速（DB 持久化，跨 worker 共享）——

def record_external_brute_failure(ip: str) -> None:
    """记录一次邀请码错误。"""
    if not ip:
        return
    with transaction() as conn:
        _exec(conn, "INSERT INTO external_brute_lock (ip, failed_at) VALUES (%s, NOW())", (ip[:45],))


def count_external_brute_failures(ip: str, window_minutes: int = 60) -> int:
    """统计该 IP 在过去 N 分钟内的失败次数。"""
    if not ip:
        return 0
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM external_brute_lock "
        "WHERE ip=%s AND failed_at >= NOW() - INTERVAL %s MINUTE",
        (ip[:45], int(window_minutes)))
    return int((row or {}).get("c") or 0)


def clear_external_brute_failures(ip: str) -> None:
    """验证成功时清掉该 IP 的失败记录。"""
    if not ip:
        return
    with transaction() as conn:
        _exec(conn, "DELETE FROM external_brute_lock WHERE ip=%s", (ip[:45],))


def cleanup_external_brute_old(days: int = 1) -> int:
    """清理过期的 brute lock 记录（cron 调用）。"""
    with transaction() as conn:
        cur = _exec(conn,
            "DELETE FROM external_brute_lock WHERE failed_at < NOW() - INTERVAL %s DAY",
            (int(days),))
        try:
            return cur.rowcount
        except Exception:
            return 0


# ═══════════════════════════════════════════
# Login rate limiting
# ═══════════════════════════════════════════

def record_login_failure(ip: str) -> None:
    with transaction() as conn:
        _exec(conn, "INSERT INTO login_attempt (ip, attempted_at) VALUES (%s, NOW())", (ip,))

def count_recent_login_failures(ip: str, window_seconds: int = 300) -> int:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) as cnt FROM login_attempt WHERE ip=%s AND attempted_at > DATE_SUB(NOW(), INTERVAL %s SECOND)",
        (ip, window_seconds),
    )
    return row["cnt"] if row else 0

def clear_login_failures(ip: str) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM login_attempt WHERE ip=%s", (ip,))

def record_lockout(ip: str) -> None:
    """记一次锁定事件(每达到 _LOGIN_MAX_ATTEMPTS 阈值就 insert 一行)。"""
    with transaction() as conn:
        _exec(conn, "INSERT INTO login_lockout (ip, locked_at) VALUES (%s, NOW())", (ip,))


def last_lockout_at(ip: str) -> Optional[str]:
    """该 IP 最近一次锁定时间(YYYY-MM-DD HH:MM:SS),无则 None。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT locked_at FROM login_lockout WHERE ip=%s ORDER BY locked_at DESC LIMIT 1",
        (ip,))
    if row and row.get("locked_at"):
        return row["locked_at"].strftime("%Y-%m-%d %H:%M:%S")
    return None


def count_recent_lockouts(ip: str, window_seconds: int = 86400) -> int:
    """该 IP 在过去 window_seconds 内被锁过几次(决定本次锁多久的渐进等级)。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS cnt FROM login_lockout WHERE ip=%s "
        "AND locked_at > DATE_SUB(NOW(), INTERVAL %s SECOND)",
        (ip, window_seconds))
    return int(row["cnt"]) if row else 0


def cleanup_old_login_lockouts(max_age_seconds: int = 86400 * 7) -> None:
    """清掉 7 天以前的锁定历史(避免无限堆积)。"""
    with transaction() as conn:
        _exec(conn, "DELETE FROM login_lockout WHERE locked_at < DATE_SUB(NOW(), INTERVAL %s SECOND)",
              (max_age_seconds,))


def cleanup_old_login_attempts(max_age_seconds: int = 3600) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM login_attempt WHERE attempted_at < DATE_SUB(NOW(), INTERVAL %s SECOND)", (max_age_seconds,))


# ═══════════════════════════════════════════
# Search Result
# ═══════════════════════════════════════════

def save_search_result(data: dict) -> int:
    """保存查词结果，支持去重更新（同一 task_id + platform + keyword 只保留最新一条）。
    
    Returns:
        int: 记录的ID（新插入或已更新的）
    """
    now = _now()
    with transaction() as conn:
        # 使用 INSERT ... ON DUPLICATE KEY UPDATE 实现去重
        # 如果 (task_id, platform, keyword) 已存在则更新，否则插入
        cur = _exec(conn,
            """INSERT INTO search_result
               (task_id, account_id, keyword_id, platform, model, keyword,
                intent_category, core_intent_word, intent_prompt,
                success, response_json, answer_text, answer_html, summarys_json,
                screenshot_url, duration, attempt, error_message,
                first_attempt_error, rescue_round, search_date, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 success=VALUES(success),
                 response_json=VALUES(response_json),
                 answer_text=VALUES(answer_text),
                 answer_html=VALUES(answer_html),
                 screenshot_url=VALUES(screenshot_url),
                 duration=VALUES(duration),
                 attempt=VALUES(attempt),
                 error_message=VALUES(error_message),
                 first_attempt_error=VALUES(first_attempt_error),
                 rescue_round=VALUES(rescue_round),
                 updated_at=%s""",
            (
                data["task_id"], data["account_id"], data.get("keyword_id"),
                data["platform"], data["model"], data["keyword"],
                data.get("intent_category", ""), data.get("core_intent_word", ""),
                data.get("intent_prompt", ""),
                data.get("success", False),
                data.get("response_json", ""),
                data.get("answer_text", ""),
                data.get("answer_html", ""),
                data.get("summarys_json", ""),
                data.get("screenshot_url", ""),
                data.get("duration", 0),
                data.get("attempt", 1),
                (data.get("error_message") or "")[:500],   # F4 失败原因（截 500 字防溢出）
                (data.get("first_attempt_error") or "")[:500] or None,
                (data.get("rescue_round") or "initial")[:20],
                data["search_date"],
                now,
                now,  # updated_at for ON DUPLICATE KEY UPDATE
            ),
        )
        return cur.lastrowid


def update_search_result_screenshot(task_id: str, platform: str, keyword: str, screenshot_url: str):
    """更新查词记录的截图URL（用于异步补全场景）。
    
    Args:
        task_id: 搜索任务ID
        platform: 平台名称
        keyword: 关键词
        screenshot_url: 截图URL，或 "TIMEOUT" 表示超时
    """
    conn = get_conn()
    if screenshot_url == "TIMEOUT":
        # 超时：用特殊标记
        _exec(conn,
            """UPDATE search_result 
               SET screenshot_url = 'TIMEOUT', updated_at = %s 
               WHERE task_id = %s AND platform = %s AND keyword = %s""",
            (_now(), task_id, platform, keyword),
        )
    else:
        _exec(conn,
            """UPDATE search_result 
               SET screenshot_url = %s, updated_at = %s 
               WHERE task_id = %s AND platform = %s AND keyword = %s""",
            (screenshot_url, _now(), task_id, platform, keyword),
        )
    conn.commit()


def update_result_brand(result_id: int, brand_rank: Optional[int], analysis_json: str):
    conn = get_conn()
    _exec(conn,
        "UPDATE search_result SET brand_rank=%s, brand_analysis_json=%s WHERE id=%s",
        (brand_rank, analysis_json, result_id),
    )
    conn.commit()


def get_failed_search_results(task_id: str) -> list[dict]:
    """获取指定任务中失败（success=0）的查词记录。"""
    conn = get_conn()
    rows = _fetchall(conn,
        f"SELECT {_SEARCH_RESULT_LIGHT_COLS} FROM search_result "
        "WHERE task_id=%s AND success=0 ORDER BY id",
        (task_id,),
    )
    return [_result_to_dict(r) for r in rows]


def update_search_result(result_id: int, data: dict):
    """更新已有查词记录（用于重试场景）。"""
    conn = get_conn()
    sets = []
    vals = []
    for col in ("success", "response_json", "answer_text", "screenshot_url",
                "error_message", "attempt", "search_date"):
        if col in data:
            sets.append(f"{col}=%s")
            vals.append(data[col])
    if not sets:
        return
    # 注意：_now() 返回时间戳字符串，必须作为参数传入以避免SQL注入/语法错误
    sql = f"UPDATE search_result SET {', '.join(sets)}, updated_at=%s WHERE id=%s"
    # 参数顺序：各列值 + updated_at(_now) + id(result_id)
    args = tuple(list(vals) + [_now(), result_id])
    # 调试输出（处理Unicode编码问题）
    try:
        print(f"[DEBUG-SQL] sql={sql}", flush=True)
        print(f"[DEBUG-SQL] args={args}", flush=True)
    except UnicodeEncodeError:
        print(f"[DEBUG-SQL] sql={sql} (args含特殊字符，省略)", flush=True)
    _exec(conn, sql, args)
    conn.commit()


# 查词详情页轻量列:排除 response_json / summarys_json / brand_analysis_json 三个大 JSON 列
# (前端不消费;不裁剪时单日结果可达 17MB/12s,是"SELECT * 带大 TEXT 列"炸弹)。
_SEARCH_RESULT_LIGHT_COLS = (
    "id, task_id, account_id, keyword_id, platform, model, keyword, "
    "intent_category, core_intent_word, intent_prompt, success, "
    "answer_text, answer_html, screenshot_url, brand_rank, duration, attempt, "
    "error_message, first_attempt_error, rescue_round, search_date, created_at"
)


def get_search_results_light(account_id: int, date: str = "") -> list[dict]:
    """查词详情页专用:同 get_search_results 的去重口径,但只取前端要用的列。"""
    conn = get_conn()
    if date:
        rows = _fetchall(conn,
            f"SELECT {_SEARCH_RESULT_LIGHT_COLS} FROM search_result r "
            "INNER JOIN (SELECT MAX(id) as max_id FROM search_result "
            "WHERE account_id=%s AND search_date=%s GROUP BY keyword, model) t "
            "ON r.id = t.max_id ORDER BY r.id",
            (account_id, date),
        )
    else:
        rows = _fetchall(conn,
            f"SELECT {_SEARCH_RESULT_LIGHT_COLS} FROM search_result r "
            "INNER JOIN (SELECT MAX(id) as max_id FROM search_result "
            "WHERE account_id=%s GROUP BY keyword, model, search_date) t "
            "ON r.id = t.max_id ORDER BY r.id DESC LIMIT 500",
            (account_id,),
        )
    # 与 get_search_results 同款 camelCase 转换(未取的大 JSON 列由 .get 默认空串兜底)
    return [_result_to_dict(r) for r in rows]


def get_search_results(account_id: int, date: str = "") -> list[dict]:
    conn = get_conn()
    if date:
        rows = _fetchall(conn,
            "SELECT r.* FROM search_result r "
            "INNER JOIN (SELECT MAX(id) as max_id FROM search_result "
            "WHERE account_id=%s AND search_date=%s GROUP BY keyword, model) t "
            "ON r.id = t.max_id ORDER BY r.id",
            (account_id, date),
        )
    else:
        rows = _fetchall(conn,
            "SELECT r.* FROM search_result r "
            "INNER JOIN (SELECT MAX(id) as max_id FROM search_result "
            "WHERE account_id=%s GROUP BY keyword, model, search_date) t "
            "ON r.id = t.max_id ORDER BY r.id DESC LIMIT 500",
            (account_id,),
        )
    return [_result_to_dict(r) for r in rows]


def get_search_results_by_task(task_id: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM search_result WHERE task_id=%s ORDER BY id",
        (task_id,),
    )
    return [_result_to_dict(r) for r in rows]


def get_date_query_completeness(account_id: int, date: str) -> dict:
    """排名分析门控:某 (account, date) 查词是否已补查完整。

    按 (keyword, model) 取最新一次结果去重(与 get_search_results 同口径),
    避免已补查成功的词因历史失败行被误判为"待补查"。
    complete=True 表示无待补查词、且该 account 无在跑/排队的查词任务,
    此时才适合做"完整排名分析"。
    """
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(r.success=1),0) AS ok, "
        "COALESCE(SUM(r.success=0),0) AS failed "
        "FROM search_result r "
        "INNER JOIN (SELECT MAX(id) AS max_id FROM search_result "
        "  WHERE account_id=%s AND search_date=%s GROUP BY keyword, model) t "
        "ON r.id = t.max_id",
        (account_id, date),
    )
    total = int((row or {}).get("total") or 0)
    ok = int((row or {}).get("ok") or 0)
    failed = int((row or {}).get("failed") or 0)
    busy = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM search_task "
        "WHERE account_id=%s AND status IN ('RUNNING','PENDING','QUEUED')",
        (account_id,),
    )
    in_progress = int((busy or {}).get("c") or 0) > 0
    complete = (not in_progress) and failed == 0 and ok > 0
    return {
        "total": total, "success": ok, "failed": failed,
        "pending": failed, "in_progress": in_progress, "complete": complete,
    }


_MODEL_TO_PLATFORM_NAME = {
    "douBao": "豆包", "deepseek": "DeepSeek", "yuanBao": "元宝", "kimi": "Kimi",
    "wenXin": "文心一言", "tongYi": "通义千问", "naMi": "纳米",
}

# 「疑似卡死」阈值按 model 调整，DeepSeek 单次成功调用可达 130s，不能再用全局 60s
# 否则正常 DeepSeek 跑到一半就被误判为卡死。值取每平台 P95 实测 *约 1.5 倍。
# 数据来源：实测 search_result.duration 分布 + searcher 单次请求 httpx timeout=180s。
_STALL_BASE_SEC: dict[str, int] = {
    "deepseek": 200,   # 正常 100-180s，单请求 timeout=180s
    "yuanBao":  120,   # yk 通道，30-90s
    "kimi":     120,   # yk 通道，30-90s
    "douBao":   90,    # 主通道
    "wenXin":   90,    # 主通道
    "tongYi":   90,    # 主通道
    "naMi":     30,    # 上游不稳，秒级返回为主
}
_STALL_DEFAULT_SEC = 90


def _stall_threshold(model: str, attempts: int) -> int:
    """单 keyword 的卡死阈值 = base + 每次重试再容忍 base/2，避免 busy backoff 期间误判。"""
    base = _STALL_BASE_SEC.get(model, _STALL_DEFAULT_SEC)
    retries = max(0, int(attempts or 1) - 1)
    return base + retries * (base // 2)


def get_search_progress_log(task_id: str) -> list[dict]:
    """已完成查询摘要 + 正在 in-flight 的查询（来自 search_task.live_inflight）。
    in-flight 行 success=None, inflight=True, elapsed=秒数；前端按其渲染"查询中/卡死"样式。
    """
    import json as _json
    import time as _time
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT keyword, platform, model, success, duration, intent_category FROM search_result WHERE task_id=%s ORDER BY id",
        (task_id,),
    )
    out = [
        {
            "keyword": r["keyword"],
            "platform": r["platform"],
            "model": r["model"],
            "success": bool(r.get("success")),
            "duration": r.get("duration", 0),
            "intentCategory": r.get("intent_category", ""),
            "inflight": False,
        }
        for r in rows
    ]
    # 心跳门禁:若任务非 RUNNING,或 RUNNING 但心跳超时(daemon 线程已死/被 HUP 杀),
    # 不再返回 in-flight 行——否则前端会把僵尸 in-flight 误显示为"查询中/响应慢",
    # 而后端其实已经没有任何 worker 在跑这些词。
    _INFLIGHT_HEARTBEAT_MAX = 180  # 与 reap_stale_running_tasks 阈值一致
    try:
        meta = _fetchall(conn,
            "SELECT status, last_heartbeat FROM search_task WHERE id=%s", (task_id,))
        m = meta[0] if meta else {}
        _status = (m.get("status") or "").upper()
        _hb = m.get("last_heartbeat") or ""
        _alive = _status in ("RUNNING", "PENDING")
        if _alive and _hb:
            try:
                hb_dt = datetime.strptime(_hb, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - hb_dt).total_seconds() > _INFLIGHT_HEARTBEAT_MAX:
                    _alive = False  # 心跳超时 → 视为已中断,不渲染 inflight
            except Exception:
                pass
    except Exception:
        _alive = True  # 查询失败时保守按活着处理,不影响主流程

    # 附加 in-flight：当前正在跑、还没产出结果行的查询
    # Stage 2.2: 优先读 Redis（feature flag ON 且 cache 命中），降级到 DB live_inflight
    raw = ""
    if _alive:
        try:
            import redis_helper
            if redis_helper.is_enabled("redis_inflight_enabled"):
                raw = redis_helper.safe_get(f"inflight:{task_id}", "") or ""
        except Exception:
            pass
        if not raw:
            # DB fallback：Redis 未启用 / cache miss / Redis 故障
            try:
                t = _fetchall(conn, "SELECT live_inflight FROM search_task WHERE id=%s", (task_id,))
                raw = (t[0].get("live_inflight") if t else None) or ""
            except Exception:
                raw = ""
    if raw:
        try:
            items = _json.loads(raw) or []
            now = _time.time()
            for it in items:
                if not isinstance(it, dict): continue
                kw = it.get("keyword") or it.get("kw")
                mc = it.get("model") or ""
                started = float(it.get("started_at") or now)
                elapsed = max(0, int(now - started))
                attempts = int(it.get("attempts") or 1)
                threshold = _stall_threshold(mc, attempts)
                wait_until = float(it.get("wait_until") or 0)
                out.append({
                    "keyword": kw,
                    "platform": _MODEL_TO_PLATFORM_NAME.get(mc, mc),
                    "model": mc,
                    "success": None,
                    "duration": elapsed,
                    "startedAt": started,         # 前端做本地 1s tick(避免 2s polling 跳动)
                    "intentCategory": "",
                    "inflight": True,
                    "attempts": attempts,
                    "stalled": elapsed >= threshold,
                    "stallThreshold": threshold,
                    "waitUntil": wait_until,      # >0 且 > now 时显示「等待 Ns」,否则显示「查询中」
                    "lastError": it.get("last_error") or "",
                })
        except Exception:
            pass
    return out


def update_task_inflight(task_id: str, inflight_list: list[dict]) -> None:
    """事件驱动写 search_task.live_inflight (JSON)。入参是 list[{keyword,model,started_at,attempts,last_error}]。"""
    import json as _json
    try:
        with transaction() as conn:
            _exec(conn, "UPDATE search_task SET live_inflight=%s WHERE id=%s",
                  (_json.dumps(inflight_list, ensure_ascii=False), task_id))
    except Exception:
        # 观测性附加项，写失败不影响主流程
        pass




def get_citation_scrape_dates(account_id: int) -> list[str]:
    """Return distinct search_date values from result_scrape for given account."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT DISTINCT search_date FROM result_scrape WHERE account_id=%s ORDER BY search_date DESC",
        (account_id,),
    )
    return [r["search_date"] for r in rows]


def get_search_results_for_quote(account_id: int, search_date: str) -> list[dict]:
    """Return search results with summarys for a given date, for importing into quote."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, keyword, intent_prompt, model, summarys_json "
        "FROM search_result WHERE account_id=%s AND search_date=%s AND success=1 AND summarys_json!=''",
        (account_id, search_date),
    )
    return [dict(r) for r in rows]


def get_scrape_results_for_quote(account_id: int, search_date: str) -> list[dict]:
    """Return scrape results with content for a given date."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT url, title, site_name, markdown_content, pub_date, content_type, website_type, scrape_status "
        "FROM result_scrape WHERE account_id=%s AND search_date=%s",
        (account_id, search_date),
    )
    return [dict(r) for r in rows]

def get_last_search_dates() -> dict:
    """Return {account_id: last_search_date} for all accounts."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT account_id, MAX(search_date) as last_date FROM search_result GROUP BY account_id"
    )
    return {r["account_id"]: r["last_date"] for r in rows}


def get_last_search_datetimes() -> dict:
    """Return {account_id: last_search_created_at} (full datetime) for all accounts."""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT account_id, MAX(created_at) as last_at FROM search_result GROUP BY account_id"
    )
    return {r["account_id"]: r["last_at"] for r in rows}


def get_last_ranking_dates() -> dict:
    """Return {account_id: last_ranking_analysis_time} (排名分析任务最近创建时间)。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT account_id, MAX(created_at) as last_at FROM ranking_task "
        "WHERE account_id IS NOT NULL GROUP BY account_id"
    )
    return {r["account_id"]: r["last_at"] for r in rows}


def get_search_history(account_id: int) -> list[str]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT DISTINCT search_date FROM search_result WHERE account_id=%s ORDER BY search_date DESC",
        (account_id,),
    )
    return [r["search_date"] for r in rows]


def get_search_history_grouped(account_id: int, limit_dates: int = 30) -> list[dict]:
    """按日期分组的查词执行历史，供前端"执行历史"展开行使用。

    返回结构（按日期降序）：
      [{
        date: "2026-08-11",
        status: "COMPLETED",
        targetQueries: 2,
        successQueries: 2,
        pendingQueries: 0,
        firstAt: "...",
        lastAt: "...",
        errorMessage: "",
        tasks: [{ id, totalQueries, completedQueries, status }],
        modelStats: [{ platform, successCount, failCount }]
      }, ...]
    """
    conn = get_conn()
    # 1. 取最近 N 个有查词记录的日期
    date_rows = _fetchall(conn,
        "SELECT DISTINCT search_date FROM search_result "
        "WHERE account_id=%s ORDER BY search_date DESC LIMIT %s",
        (account_id, limit_dates),
    )
    if not date_rows:
        return []
    dates = [r["search_date"] for r in date_rows]
    placeholders = ",".join("%s" for _ in dates)

    # 2. 按日期取任务汇总（从 search_task 表）
    # 注意: MariaDB 不支持 ::date 类型转换和 ROW_NUMBER() 窗口函数的 PostgreSQL 语法
    task_rows = _fetchall(conn,
        f"SELECT id, status, total_queries, completed_queries, error_message, "
        f"created_at, completed_at "
        f"FROM search_task WHERE account_id=%s ORDER BY created_at DESC",
        (account_id,),
    )

    # 3. 按日期取结果统计（从 search_result 表）
    result_stats = _fetchall(conn,
        f"SELECT search_date, platform, model, "
        f"SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS success_cnt, "
        f"SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail_cnt, "
        f"COUNT(*) AS total_cnt "
        f"FROM search_result WHERE account_id=%s AND search_date IN ({placeholders}) "
        f"GROUP BY search_date, platform, model ORDER BY search_date DESC",
        [account_id] + dates,
    )

    # 4. 组装返回结构
    from collections import defaultdict
    stats_by_date = defaultdict(lambda: {"success": 0, "fail": 0, "models": defaultdict(lambda: {"success": 0, "fail": 0})})
    for rs in result_stats:
        d = rs["search_date"]
        s = int(rs["success_cnt"] or 0)
        f = int(rs["fail_cnt"] or 0)
        stats_by_date[d]["success"] += s
        stats_by_date[d]["fail"] += f
        plat = rs.get("platform") or rs.get("model") or "unknown"
        stats_by_date[d]["models"][plat]["success"] += s
        stats_by_date[d]["models"][plat]["fail"] += f

    # 按 search_task 组装每日任务列表
    task_map = defaultdict(list)
    for tr in task_rows:
        # 从 created_at 提取日期
        created = str(tr.get("created_at") or "")[:10]
        if created and created in set(dates):
            source = tr.get("source", "internal_manual")
            # 根据source判断运行类型
            if source == "retry_failed":
                run_type = "重试失败"
            elif source == "retry_continue":
                run_type = "继续未完成"
            elif source == "scheduled":
                run_type = "定时任务"
            else:
                run_type = "手动查词"
            
            task_map[created].append({
                "taskId": tr["id"],  # 前端期望 taskId 字段
                "totalQueries": tr.get("total_queries", 0),
                "completedQueries": tr.get("completed_queries", 0),
                "status": tr.get("status", "UNKNOWN"),
                "errorMessage": tr.get("error_message") or "",
                "createdAt": str(tr.get("created_at") or ""),
                "completedAt": str(tr.get("completed_at") or ""),
                "runType": run_type,
                "totalInDb": int(tr.get("completed_queries") or 0),  # 数据库中的完成数
            })

    result = []
    for d in dates:
        stats = stats_by_date[d]
        tasks = task_map.get(d, [])
        total_success = stats["success"]
        total_fail = stats["fail"]
        total = total_success + total_fail

        # 取该日最早/最晚任务时间
        all_tasks = tasks if tasks else []
        first_at = min((t.get("createdAt") for t in all_tasks if t.get("createdAt")), default="")
        last_at = max((t.get("completedAt") or t.get("createdAt") for t in all_tasks if t), default="")

        # 判断整体状态
        has_running = any(t.get("status") == "RUNNING" for t in all_tasks)
        has_error = any(t.get("status") in ("ERROR", "FAILED") for t in all_tasks)
        if has_running:
            status = "RUNNING"
        elif has_error and total_success == 0:
            status = "FAILED"
        else:
            status = "COMPLETED"

        model_stats = [
            {"model": plat, "success": m["success"], "fail": m["fail"]}  # 前端使用 ms.fail
            for plat, m in stats["models"].items()
        ]

        result.append({
            "date": d,
            "status": status,
            "targetQueries": total,
            "successQueries": total_success,
            "pendingQueries": total - total_success,
            "firstAt": first_at,
            "lastAt": last_at,
            "errorMessage": "",
            "tasks": all_tasks,
            "modelStats": model_stats,
        })
    return result


def get_brand_ranking_data(account_id: int, dates: list[str]) -> list[dict]:
    conn = get_conn()
    if dates:
        placeholders = ",".join("%s" for _ in dates)
        rows = _fetchall(conn,
            f"SELECT * FROM search_result WHERE account_id=%s AND search_date IN ({placeholders}) AND brand_rank IS NOT NULL ORDER BY id",
            [account_id] + dates,
        )
    else:
        rows = _fetchall(conn,
            "SELECT * FROM search_result WHERE account_id=%s AND brand_rank IS NOT NULL ORDER BY id",
            (account_id,),
        )
    return [_result_to_dict(r) for r in rows]


def get_results_for_reanalysis(account_id: int, date: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM search_result WHERE account_id=%s AND search_date=%s AND success=1 ORDER BY id",
        (account_id, date),
    )
    return [_result_to_dict(r) for r in rows]




def get_search_results_by_ids(ids: list) -> list[dict]:
    """根据 ID 列表批量获取 search_result"""
    if not ids:
        return []
    conn = get_conn()
    placeholders = ','.join(['%s'] * len(ids))
    rows = _fetchall(conn,
        f"SELECT * FROM search_result WHERE id IN ({placeholders})",
        tuple(ids),
    )
    return [_result_to_dict(r) for r in rows]

def _result_to_dict(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "taskId": d["task_id"],
        "accountId": d["account_id"],
        "keywordId": d.get("keyword_id"),
        "platform": d["platform"],
        "model": d["model"],
        "keyword": d["keyword"],
        "intentCategory": d.get("intent_category", ""),
        "coreIntentWord": d.get("core_intent_word", ""),
        "intentPrompt": d.get("intent_prompt", ""),
        "success": bool(d.get("success")),
        "responseJson": d.get("response_json", ""),
        "answerText": d.get("answer_text", ""),
        "answerHtml": d.get("answer_html", ""),
        "summarysJson": d.get("summarys_json", ""),
        "screenshotUrl": d.get("screenshot_url", ""),
        "brandRank": d.get("brand_rank"),
        "brandAnalysisJson": d.get("brand_analysis_json", ""),
        "pubDate": d.get("pub_date", ""),
        "contentType": d.get("content_type", ""),
        "websiteType": d.get("website_type", ""),
        "duration": d.get("duration", 0),
        "attempt": d.get("attempt", 1),
        "searchDate": d["search_date"],
        "createdAt": d.get("created_at", ""),
    }


# ═══════════════════════════════════════════
# Result Scrape（引用源抓取）
# ═══════════════════════════════════════════

def get_citation_urls(account_id: int, search_date: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, keyword, model, summarys_json FROM search_result "
        "WHERE account_id=%s AND search_date=%s AND success=1 AND summarys_json!=''",
        (account_id, search_date),
    )
    seen: set[str] = set()
    citations: list[dict] = []
    for row in rows:
        try:
            summarys = json.loads(row["summarys_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(summarys, list):
            continue
        for s in summarys:
            href = (s.get("href") or s.get("url") or "").strip()
            if href and href not in seen and href.startswith("http"):
                seen.add(href)
                citations.append({
                    "url": href,
                    "title": s.get("title", ""),
                    "siteName": s.get("footerTitle") or s.get("site_name", ""),
                    "resultId": row["id"],
                    "keyword": row["keyword"],
                    "model": row["model"],
                })
    return citations


def save_scrape_result(data: dict) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO result_scrape
               (account_id, search_date, url, title, site_name,
                markdown_content, pub_date, content_type, website_type,
                scrape_status, error_message, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                data["account_id"], data["search_date"], data["url"],
                data.get("title", ""), data.get("site_name", ""),
                data.get("markdown_content", ""),
                data.get("pub_date", ""), data.get("content_type", ""),
                data.get("website_type", ""),
                data.get("scrape_status", "pending"),
                data.get("error_message", ""),
                now,
            ),
        )
        return cur.lastrowid


def update_scrape_result(scrape_id: int, data: dict):
    conn = get_conn()
    _exec(conn,
        """UPDATE result_scrape
           SET markdown_content=%s, pub_date=%s, content_type=%s, website_type=%s,
               scrape_status=%s, error_message=%s
           WHERE id=%s""",
        (
            data.get("markdown_content", ""),
            data.get("pub_date", ""), data.get("content_type", ""),
            data.get("website_type", ""),
            data.get("scrape_status", "done"),
            data.get("error_message", ""),
            scrape_id,
        ),
    )
    conn.commit()


def get_scrape_results(account_id: int, search_date: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM result_scrape WHERE account_id=%s AND search_date=%s ORDER BY id",
        (account_id, search_date),
    )
    return [_scrape_to_dict(r) for r in rows]


def get_scrape_results_light(account_id: int, search_date: str) -> list[dict]:
    """列表用:不含 markdown 正文,只带元数据 + 是否有正文 + 字数。
    避免单次响应膨胀到 10MB+(490 条全文)把前端解析/渲染卡死;正文按需单条拉取。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, account_id, search_date, url, title, site_name, pub_date, "
        "content_type, website_type, scrape_status, error_message, created_at, "
        "CHAR_LENGTH(markdown_content) AS md_len "
        "FROM result_scrape WHERE account_id=%s AND search_date=%s ORDER BY id",
        (account_id, search_date),
    )
    out: list[dict] = []
    for row in rows:
        d = dict(row)
        md_len = int(d.get("md_len") or 0)
        out.append({
            "id": d["id"], "accountId": d["account_id"], "searchDate": d["search_date"],
            "url": d["url"], "title": d.get("title", ""), "siteName": d.get("site_name", ""),
            "pubDate": d.get("pub_date", ""), "contentType": d.get("content_type", ""),
            "websiteType": d.get("website_type", ""), "scrapeStatus": d.get("scrape_status", "pending"),
            "errorMessage": d.get("error_message", ""), "createdAt": d.get("created_at", ""),
            "hasMarkdown": md_len > 0, "contentLength": md_len,
        })
    return out


def get_scraped_url_set(account_id: int, search_date: str) -> set[str]:
    """轻量:只取已抓取的 URL 集合(不加载 markdown 正文),用于标记 / 计数。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT url FROM result_scrape WHERE account_id=%s AND search_date=%s",
        (account_id, search_date),
    )
    return {r["url"] for r in rows}


def get_scrape_by_url(account_id: int, search_date: str, url: str) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT * FROM result_scrape WHERE account_id=%s AND search_date=%s AND url=%s",
        (account_id, search_date, url),
    )
    return _scrape_to_dict(row) if row else None


def delete_scrape_results(account_id: int, search_date: str):
    with transaction() as conn:
        _exec(conn,
            "DELETE FROM result_scrape WHERE account_id=%s AND search_date=%s",
            (account_id, search_date),
        )


def _scrape_to_dict(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"],
        "accountId": d["account_id"],
        "searchDate": d["search_date"],
        "url": d["url"],
        "title": d.get("title", ""),
        "siteName": d.get("site_name", ""),
        "markdownContent": d.get("markdown_content", ""),
        "pubDate": d.get("pub_date", ""),
        "contentType": d.get("content_type", ""),
        "websiteType": d.get("website_type", ""),
        "scrapeStatus": d.get("scrape_status", "pending"),
        "errorMessage": d.get("error_message", ""),
        "createdAt": d.get("created_at", ""),
    }


# ═══════════════════════════════════════════
# Ranking Task（排名分析任务）
# ═══════════════════════════════════════════

def create_ranking_task(task_id: str, search_task_id: str, account_id: int,
                        brand_name: str, total: int) -> dict:
    now = _now()
    with transaction() as conn:
        _exec(conn,
            """INSERT INTO ranking_task
               (id, search_task_id, account_id, brand_name, status, total, done, skipped, hit, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (task_id, search_task_id, account_id, brand_name, "running", total, 0, 0, 0, now),
        )
    return {"task_id": task_id, "status": "running", "total": total}


def update_ranking_task(task_id: str, **kwargs):
    conn = get_conn()
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in ("done", "skipped", "hit", "top1", "top3", "status", "error_message", "total"):
            sets.append(f"{k}=%s")
            vals.append(v)
    if not sets:
        return
    vals.append(task_id)
    _exec(conn, f"UPDATE ranking_task SET {', '.join(sets)} WHERE id=%s", vals)
    conn.commit()
    # 任务完成时,自动从 ranking_result 汇总 top1/top3(列表「前三率」用),不依赖 worker 传值
    if kwargs.get("status") == "completed" and "top1" not in kwargs:
        try:
            refresh_ranking_task_top_stats(task_id)
        except Exception:
            logger.exception("[ranking] 刷新 top1/top3 统计失败 task=%s", task_id)


def refresh_ranking_task_top_stats(task_id: str) -> None:
    """从 ranking_result 汇总该任务的统计写回 ranking_task：
      top1/top3（全部词）+ gen_total/gen_top3（仅通用词；通用词=提示词不含本品牌名）。
    通用词前三率更能体现 GEO 效果（品牌词里 AI 推荐自家本就理所当然）。"""
    conn = get_conn()
    trow = _fetchone(conn, "SELECT brand_name FROM ranking_task WHERE id=%s", (task_id,))
    aliases = _brand_aliases_lower(_parse_brand_list((trow or {}).get("brand_name") or ""))
    # 含 skipped(未上榜),仅排除 error 行 —— 与前端口径一致、与"跳过计入分母"口径一致
    rows = _fetchall(conn,
        "SELECT keyword, brand_rank, error FROM ranking_result WHERE ranking_task_id=%s", (task_id,))
    t1 = t3 = gen_total = gen_hit = gen_top3 = gen_top1 = 0
    for r in rows:
        if r.get("error"):
            continue
        rank = r.get("brand_rank")
        ranked = isinstance(rank, int) and rank > 0
        if ranked and rank == 1:
            t1 += 1
        if ranked and rank <= 3:
            t3 += 1
        kw = (r.get("keyword") or "").lower()
        is_brand = any(a and a in kw for a in aliases)
        if not is_brand:  # 通用词(含未上榜/skipped,作分母)
            gen_total += 1
            if ranked:
                gen_hit += 1
                if rank <= 3:
                    gen_top3 += 1
                if rank == 1:
                    gen_top1 += 1
    _exec(conn, "UPDATE ranking_task SET top1=%s, top3=%s, gen_total=%s, gen_hit=%s, gen_top3=%s, gen_top1=%s WHERE id=%s",
          (t1, t3, gen_total, gen_hit, gen_top3, gen_top1, task_id))
    conn.commit()


def _parse_brand_list(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        s = str(raw).strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                arr = json.loads(s)
                items = [str(x).strip() for x in arr] if isinstance(arr, list) else [s]
            except Exception:
                items = [s]
        else:
            items = [s]
    return [it for it in items if it]


def _brand_aliases_lower(brands: list) -> list:
    """品牌名展开成小写别名集合：含全称、去括号主体、括号内别名。"""
    out = set()
    for b in brands:
        b = (b or "").strip()
        if not b:
            continue
        out.add(b.lower())
        # 去括号主体 + 括号内别名（中英文括号）
        import re as _re
        main = _re.sub(r"[（(【\[].*?[）)】\]]", "", b).strip()
        if main:
            out.add(main.lower())
        for m in _re.findall(r"[（(【\[](.*?)[）)】\]]", b):
            m = m.strip()
            if m:
                out.add(m.lower())
    return [a for a in out if a]


def get_ranking_task_by_key(search_task_id: str, brand_name: str) -> Optional[dict]:
    """Find latest ranking_task for given (search_task_id, brand_name)."""
    conn = get_conn()
    d = _fetchone(conn,
        "SELECT * FROM ranking_task WHERE search_task_id=%s AND brand_name=%s "
        "ORDER BY created_at DESC LIMIT 1",
        (search_task_id, brand_name))
    if not d:
        return None
    return {
        "task_id": d["id"],
        "searchTaskId": d.get("search_task_id", ""),
        "accountId": d.get("account_id"),
        "brand_name": d["brand_name"],
        "status": d["status"],
    }


def get_citation_scrape_task_by_key(account_id: int, search_date: str) -> Optional[dict]:
    """Find latest citation_scrape_task for given (account_id, search_date)."""
    conn = get_conn()
    d = _fetchone(conn,
        "SELECT * FROM citation_scrape_task WHERE account_id=%s AND search_date=%s "
        "ORDER BY started_at DESC LIMIT 1",
        (account_id, search_date))
    if not d:
        return None
    return {"id": d["id"], "status": d["status"], "total": d.get("total", 0)}


def get_ranking_task(task_id: str) -> Optional[dict]:
    conn = get_conn()
    d = _fetchone(conn, "SELECT * FROM ranking_task WHERE id=%s", (task_id,))
    if not d:
        return None
    return {
        "task_id": d["id"],
        "searchTaskId": d.get("search_task_id", ""),
        "accountId": d.get("account_id"),
        "brand_name": d["brand_name"],
        "status": d["status"],
        "total": d.get("total", 0),
        "done": d.get("done", 0),
        "skipped": d.get("skipped", 0),
        "hit": d.get("hit", 0),
        "error": d.get("error_message", ""),
        "created_at": d.get("created_at", ""),
    }


def list_ranking_tasks() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn, "SELECT * FROM ranking_task ORDER BY created_at DESC LIMIT 50")
    return [{
        "task_id": r["id"],
        "brand_name": r["brand_name"],
        "total": r.get("total", 0),
        "done": r.get("done", 0),
        "skipped": r.get("skipped", 0),
        "hit": r.get("hit", 0),
        "status": r["status"],
        "created_at": r.get("created_at", ""),
    } for r in rows]


def get_ranking_result_keys(task_id: str) -> set:
    """返回该 ranking_task 已写入的 (keyword, model) 集合,用于增量补分析 diff。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT keyword, model FROM ranking_result WHERE ranking_task_id=%s",
        (task_id,),
    )
    return {(r.get("keyword") or "", r.get("model") or "") for r in (rows or [])}


def list_ranking_tasks_for_supplement(days: int = 14) -> list:
    """近 N 天的 ranking_task,用于自动补分析扫描。仅返回 completed / failed(不动 running)。"""
    conn = get_conn()
    return _fetchall(conn,
        """SELECT id, search_task_id, account_id, brand_name, status, total, done, hit, created_at
           FROM ranking_task
           WHERE status IN ('completed','failed')
             AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
           ORDER BY created_at DESC""",
        (int(days),),
    ) or []


def list_all_ranking_tasks() -> list:
    """全表 ranking_task(用于一次性回填脚本)。"""
    conn = get_conn()
    return _fetchall(conn,
        """SELECT id, search_task_id, account_id, brand_name, status, total, done, hit, created_at
           FROM ranking_task
           ORDER BY created_at DESC""",
        (),
    ) or []


def save_ranking_result(data: dict) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO ranking_result
               (ranking_task_id, result_id, keyword, model,
                brand_rank, brand_frequency, total_brands, all_brands_json,
                skipped, error, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                data["ranking_task_id"], data.get("result_id"),
                data.get("keyword", ""), data.get("model", ""),
                data.get("brand_rank"), data.get("brand_frequency", 0),
                data.get("total_brands", 0), data.get("all_brands_json", ""),
                data.get("skipped", False), data.get("error", ""),
                now,
            ),
        )
        return cur.lastrowid


def get_ranking_results(task_id: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT rr.*, sr.intent_prompt, sr.screenshot_url
           FROM ranking_result rr
           LEFT JOIN search_result sr ON rr.result_id = sr.id
           WHERE rr.ranking_task_id=%s ORDER BY rr.id""",
        (task_id,),
    )
    results = []
    for d in rows:
        all_brands = []
        try:
            all_brands = json.loads(d.get("all_brands_json", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        results.append({
            "id": d["id"],
            "result_id": d.get("result_id"),
            "keyword": d.get("keyword", ""),
            "model": d.get("model", ""),
            "brand_rank": d.get("brand_rank"),
            "brand_frequency": d.get("brand_frequency", 0),
            "total_brands": d.get("total_brands", 0),
            "all_brands": all_brands,
            "skipped": bool(d.get("skipped")),
            "error": d.get("error", ""),
            "intent_prompt": d.get("intent_prompt", ""),
            "screenshot_url": d.get("screenshot_url", ""),
        })
    return results


def get_recent_ranking_results(task_id: str, after_id: int = 0) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT rr.*, sr.intent_prompt, sr.screenshot_url
           FROM ranking_result rr
           LEFT JOIN search_result sr ON rr.result_id = sr.id
           WHERE rr.ranking_task_id=%s AND rr.id>%s
           ORDER BY rr.id""",
        (task_id, after_id),
    )
    results = []
    for r in rows:
        all_brands = []
        try:
            all_brands = json.loads(r.get("all_brands_json", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        results.append({
            "id": r["id"],
            "keyword": r.get("keyword", ""),
            "model": r.get("model", ""),
            "brand_rank": r.get("brand_rank"),
            "brand_frequency": r.get("brand_frequency", 0),
            "total_brands": r.get("total_brands", 0),
            "all_brands": all_brands,
            "skipped": bool(r.get("skipped")),
            "error": r.get("error", ""),
            "intent_prompt": r.get("intent_prompt", ""),
            "screenshot_url": r.get("screenshot_url", ""),
        })
    return results


def delete_ranking_task(task_id: str):
    with transaction() as conn:
        _exec(conn, "DELETE FROM ranking_result WHERE ranking_task_id=%s", (task_id,))
        _exec(conn, "DELETE FROM ranking_task WHERE id=%s", (task_id,))


def delete_search_task_by_id(task_id: str) -> dict:
    """按 search_task.id 精确删除一次查词任务（及其全部 search_result + 关联 ranking_task/result）。

    与 delete_search_history_by_date 的区别：
      - by_date 会把同一天所有 task 一并删（聚合粒度）
      - by_id 只删指定 task_id，同一天其他任务保留

    返回 {"task_id": ..., "account_id": ..., "search_date": ..., "results_deleted": N, "ranking_tasks_deleted": M}
    """
    with transaction() as conn:
        # 取 task 元信息（用于返回 + 判断 RUNNING 拒绝删）
        st = _fetchone(conn,
            "SELECT id, account_id, status FROM search_task WHERE id=%s", (task_id,))
        if not st:
            return {"task_id": task_id, "results_deleted": 0, "ranking_tasks_deleted": 0,
                    "not_found": True}
        if (st.get("status") or "").upper() in ("RUNNING", "QUEUED"):
            raise RuntimeError(f"任务 {task_id} 当前 status={st['status']}，不能删除运行中任务（请先取消）")
        account_id = st["account_id"]
        # search_date 取自首条 search_result（search_task 表无 search_date 字段）
        first = _fetchone(conn, "SELECT search_date FROM search_result WHERE task_id=%s LIMIT 1", (task_id,))
        search_date = first.get("search_date") if first else None

        # 关联的 ranking_task（search_task_id = task_id）连同 ranking_result 删
        rr = _fetchall(conn, "SELECT id FROM ranking_task WHERE search_task_id=%s", (task_id,))
        ranking_deleted = 0
        for r in rr:
            _exec(conn, "DELETE FROM ranking_result WHERE ranking_task_id=%s", (r["id"],))
            _exec(conn, "DELETE FROM ranking_task WHERE id=%s", (r["id"],))
            ranking_deleted += 1

        # search_result by task_id
        with conn.cursor() as cur:
            cur.execute("DELETE FROM search_result WHERE task_id=%s", (task_id,))
            results_deleted = cur.rowcount or 0
            cur.execute("DELETE FROM search_task WHERE id=%s", (task_id,))

    return {
        "task_id": task_id,
        "account_id": account_id,
        "search_date": search_date,
        "results_deleted": int(results_deleted),
        "ranking_tasks_deleted": int(ranking_deleted),
    }


def delete_search_history_by_date(account_id: int, search_date: str) -> int:
    """删除指定客户 + 日期的全部查词结果，并级联删除关联的排名结果。返回删除的 search_result 行数。"""
    with transaction() as conn:
        rows = _fetchall(conn,
            "SELECT DISTINCT task_id FROM search_result WHERE account_id=%s AND search_date=%s",
            (account_id, search_date))
        task_ids = [r["task_id"] for r in rows if r.get("task_id")]
        for tid in task_ids:
            rr = _fetchall(conn,
                "SELECT id FROM ranking_task WHERE search_task_id=%s", (tid,))
            for r in rr:
                _exec(conn, "DELETE FROM ranking_result WHERE ranking_task_id=%s", (r["id"],))
                _exec(conn, "DELETE FROM ranking_task WHERE id=%s", (r["id"],))
            _exec(conn, "DELETE FROM search_task WHERE id=%s", (tid,))
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM search_result WHERE account_id=%s AND search_date=%s",
                (account_id, search_date))
            affected = cur.rowcount
    return int(affected or 0)


def delete_citation_scrape_task(task_id: str) -> bool:
    with transaction() as conn:
        _exec(conn, "DELETE FROM citation_scrape_event WHERE task_id=%s", (task_id,))
        with conn.cursor() as cur:
            cur.execute("DELETE FROM citation_scrape_task WHERE id=%s", (task_id,))
            return (cur.rowcount or 0) > 0


def delete_citation_scrape_by_date(account_id: int, search_date: str) -> dict:
    """删除指定客户+日期的抓取任务(及事件)和已抓取的正文数据。"""
    with transaction() as conn:
        rows = _fetchall(conn,
            "SELECT id FROM citation_scrape_task WHERE account_id=%s AND search_date=%s",
            (account_id, search_date))
        task_ids = [r["id"] for r in rows]
        for tid in task_ids:
            _exec(conn, "DELETE FROM citation_scrape_event WHERE task_id=%s", (tid,))
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM citation_scrape_task WHERE account_id=%s AND search_date=%s",
                (account_id, search_date))
            tasks_deleted = cur.rowcount or 0
            cur.execute(
                "DELETE FROM result_scrape WHERE account_id=%s AND search_date=%s",
                (account_id, search_date))
            scrapes_deleted = cur.rowcount or 0
    return {"tasks": int(tasks_deleted), "scrapes": int(scrapes_deleted)}


def get_ranking_brands(owner_id: int | None = None, team_id: int | None = None) -> list[str]:
    conn = get_conn()
    if team_id is not None:
        rows = _fetchall(conn,
            "SELECT DISTINCT rt.brand_name FROM ranking_task rt JOIN account a ON rt.account_id=a.id WHERE a.team_id=%s ORDER BY rt.brand_name",
            (team_id,))
    elif owner_id is not None:
        rows = _fetchall(conn,
            "SELECT DISTINCT rt.brand_name FROM ranking_task rt JOIN account a ON rt.account_id=a.id "
            "WHERE (a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)) ORDER BY rt.brand_name",
            (owner_id, owner_id))
    else:
        rows = _fetchall(conn, "SELECT DISTINCT brand_name FROM ranking_task ORDER BY brand_name")
    return [r["brand_name"] for r in rows]


def get_ranking_trends(brand_name: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT rt.id, rt.created_at,
                  COUNT(rr.id) as total_count,
                  SUM(CASE WHEN rr.brand_rank > 0 AND rr.brand_rank IS NOT NULL THEN 1 ELSE 0 END) as ranked_count,
                  AVG(CASE WHEN rr.brand_rank > 0 AND rr.brand_rank IS NOT NULL THEN rr.brand_rank END) as avg_rank
           FROM ranking_task rt
           JOIN ranking_result rr ON rr.ranking_task_id = rt.id
           WHERE rt.brand_name=%s AND rt.status='completed' AND rr.skipped=0
           GROUP BY rt.id
           ORDER BY rt.created_at""",
        (brand_name,),
    )
    return [{
        "date": r.get("created_at", ""),
        "total_count": r.get("total_count", 0),
        "ranked_count": r.get("ranked_count", 0),
        "avg_rank": round(float(r.get("avg_rank") or 0), 1),
    } for r in rows]


def get_search_task_details(task_id: str) -> dict:
    conn = get_conn()
    kw_rows = _fetchall(conn,
        "SELECT DISTINCT keyword FROM search_result WHERE task_id=%s AND success=1",
        (task_id,),
    )
    model_rows = _fetchall(conn,
        "SELECT DISTINCT model FROM search_result WHERE task_id=%s",
        (task_id,),
    )
    cnt = _fetchone(conn,
        "SELECT COUNT(*) as cnt FROM search_result WHERE task_id=%s AND success=1",
        (task_id,),
    )
    return {
        "keywords": [r["keyword"] for r in kw_rows],
        "models": [r["model"] for r in model_rows],
        "file_count": cnt["cnt"] if cnt else 0,
    }


def list_search_tasks_for_ranking() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM search_task WHERE status='COMPLETED' ORDER BY created_at DESC LIMIT 50"
    )
    tasks = []
    for r in rows:
        details = get_search_task_details(r["id"])
        tasks.append({
            "task_id": r["id"],
            "created_at": r.get("created_at", ""),
            "keywords": details["keywords"],
            "models": details["models"],
            "file_count": details["file_count"],
            "status": r["status"].lower(),
        })
    return tasks












def delete_ranking_results_for_task(task_id: str):
    """删除某任务的所有排名结果"""
    with transaction() as conn:
        _exec(conn, "DELETE FROM ranking_result WHERE ranking_task_id=%s", (task_id,))

def delete_ranking_result_by_id(result_row_id: int):
    """删除单条排名结果"""
    with transaction() as conn:
        _exec(conn, "DELETE FROM ranking_result WHERE id=%s", (result_row_id,))

def delete_ranking_results_by_keys(task_id: str, keys: list):
    """删除指定 (keyword, model) 组合的排名结果"""
    if not keys:
        return
    with transaction() as conn:
        for kw, model in keys:
            _exec(conn,
                "DELETE FROM ranking_result WHERE ranking_task_id=%s AND keyword=%s AND model=%s",
                (task_id, kw, model),
            )

def _extract_search_date(search_task_id: str) -> str:
    """从 search_task_id (例如 'account_3_2026-04-17') 中解析查词数据日期。"""
    if not search_task_id:
        return ""
    tail = search_task_id.rsplit("_", 1)[-1]
    if len(tail) == 10 and tail[4] == '-' and tail[7] == '-':
        return tail
    return ""


def get_ranking_history_by_account(account_id: int) -> list:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, search_task_id, brand_name, status, total, done, skipped, hit, error_message, created_at FROM ranking_task WHERE account_id=%s ORDER BY created_at DESC LIMIT 50",
        (account_id,),
    )
    return [{
        "task_id": r["id"],
        "brand_name": r["brand_name"],
        "status": r["status"],
        "total": r.get("total", 0),
        "done": r.get("done", 0),
        "skipped": r.get("skipped", 0),
        "hit": r.get("hit", 0),
        "error": r.get("error_message", ""),
        "created_at": r.get("created_at", ""),
        "search_data_date": _extract_search_date(r.get("search_task_id", "")),
    } for r in rows]

def get_account_ranking_records(account_id: int, limit: int = 5000) -> list[dict]:
    """获取指定账号的全部排名分析记录（按时间倒序），用于 Excel 导出。
    JOIN ranking_task 拿到任务时间和品牌；JOIN search_result 拿到原始 prompt / 截图。
    """
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT rr.id, rr.keyword, rr.model, rr.brand_rank, rr.brand_frequency,
                  rr.total_brands, rr.skipped, rr.error,
                  sr.intent_prompt, sr.screenshot_url,
                  rt.id AS task_id, rt.brand_name, rt.created_at AS task_created_at,
                  rt.search_task_id AS search_task_id
           FROM ranking_result rr
           LEFT JOIN search_result sr ON rr.result_id = sr.id
           LEFT JOIN ranking_task rt ON rr.ranking_task_id = rt.id
           WHERE rt.account_id = %s
           ORDER BY rt.created_at DESC, rr.id ASC
           LIMIT %s""",
        (account_id, limit),
    )
    return [{
        "task_id": r.get("task_id", ""),
        "task_created_at": r.get("task_created_at", "") or "",
        "search_data_date": _extract_search_date(r.get("search_task_id", "")),
        "brand_name": r.get("brand_name", "") or "",
        "intent_prompt": r.get("intent_prompt") or r.get("keyword", ""),
        "keyword": r.get("keyword", ""),
        "model": r.get("model", ""),
        "brand_rank": r.get("brand_rank"),
        "brand_frequency": r.get("brand_frequency", 0),
        "total_brands": r.get("total_brands", 0),
        "skipped": bool(r.get("skipped")),
        "error": r.get("error", "") or "",
        "screenshot_url": r.get("screenshot_url", "") or "",
    } for r in rows]


def get_running_ranking_task(owner_id: int | None = None, team_id: int | None = None):
    conn = get_conn()
    if team_id is not None:
        d = _fetchone(conn,
            "SELECT rt.* FROM ranking_task rt JOIN account a ON rt.account_id=a.id WHERE rt.status=%s AND a.team_id=%s ORDER BY rt.created_at DESC LIMIT 1",
            ("running", team_id))
    elif owner_id is not None:
        d = _fetchone(conn,
            "SELECT rt.* FROM ranking_task rt JOIN account a ON rt.account_id=a.id "
            "WHERE rt.status=%s AND (a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)) "
            "ORDER BY rt.created_at DESC LIMIT 1",
            ("running", owner_id, owner_id))
    else:
        d = _fetchone(conn, "SELECT * FROM ranking_task WHERE status=%s ORDER BY created_at DESC LIMIT 1", ("running",))
    if not d:
        return None
    return {
        "task_id": d["id"],
        "accountId": d.get("account_id"),
        "brand_name": d["brand_name"],
        "status": d["status"],
        "total": d.get("total", 0),
        "done": d.get("done", 0),
        "skipped": d.get("skipped", 0),
        "hit": d.get("hit", 0),
        "created_at": d.get("created_at", ""),
    }


def list_ranking_tasks_with_account(owner_id: int | None = None,
                                     account_id: int | None = None,
                                     limit: int = 200, offset: int = 0):
    """ranking_task 历史列表。支持按客户过滤 + 分页。

    limit 默认 200(满足绝大多数日常浏览),最大 2000。
    """
    conn = get_conn()
    limit = max(1, min(int(limit or 200), 2000))
    offset = max(0, int(offset or 0))
    base = ("SELECT rt.*, a.company_name, a.company_brand "
            "FROM ranking_task rt LEFT JOIN account a ON rt.account_id = a.id ")
    where = []
    params: list = []
    if owner_id is not None:
        where.append("(a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s))")
        params.append(owner_id); params.append(owner_id)
    if account_id is not None:
        where.append("rt.account_id=%s")
        params.append(int(account_id))
    if where:
        base += "WHERE " + " AND ".join(where) + " "
    base += "ORDER BY rt.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    rows = _fetchall(conn, base, tuple(params))
    return [{
        "task_id": r["id"],
        "brand_name": r["brand_name"],
        "total": r.get("total", 0),
        "done": r.get("done", 0),
        "skipped": r.get("skipped", 0),
        "hit": r.get("hit", 0),
        "top1": r.get("top1", 0),
        "top3": r.get("top3", 0),
        "genTotal": r.get("gen_total", 0),
        "genHit": r.get("gen_hit", 0),
        "genTop3": r.get("gen_top3", 0),
        "genTop1": r.get("gen_top1", 0),
        "status": r["status"],
        "companyName": r.get("company_name", ""),
        "companyBrand": r.get("company_brand", ""),
        "accountId": r.get("account_id"),
        "created_at": r.get("created_at", ""),
        "search_data_date": _extract_search_date(r.get("search_task_id", "")),
    } for r in rows]


# ═══════════════════════════════════════════
# Report
# ═══════════════════════════════════════════

def get_report_info(share_code: str) -> Optional[dict]:
    conn = get_conn()
    d = _fetchone(conn, "SELECT * FROM report_info WHERE share_code=%s", (share_code,))
    if not d:
        return None
    return {
        "id": d["id"],
        "shareCode": d["share_code"],
        "title": d.get("title", ""),
        "reportDate": d.get("report_date", ""),
        "brand": d.get("brand", ""),
        "platforms": (d.get("platforms") or "").split(",") if d.get("platforms") else [],
        "optimizeStartDate": d.get("optimize_start_date", ""),
        "searchMode": d.get("search_mode", ""),
    }


def get_overview_bullets(share_code: str) -> dict:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM overview_bullet WHERE share_code=%s ORDER BY sort_order",
        (share_code,),
    )
    result = {"preOptBullets": [], "insightBullets": [], "nextWeekBullets": []}
    for r in rows:
        section = r["section"]
        item = {"id": r["id"], "content": r["content"], "sortOrder": r["sort_order"]}
        if section == "PRE_OPT":
            result["preOptBullets"].append(item)
        elif section == "INSIGHT":
            result["insightBullets"].append(item)
        elif section == "NEXT_WEEK":
            result["nextWeekBullets"].append(item)
    return result


def get_ranking_records(share_code: str, platform: str = "") -> list[dict]:
    conn = get_conn()
    if platform:
        rows = _fetchall(conn,
            "SELECT * FROM ranking_record WHERE share_code=%s AND platform=%s ORDER BY id",
            (share_code, platform),
        )
    else:
        rows = _fetchall(conn,
            "SELECT * FROM ranking_record WHERE share_code=%s ORDER BY id",
            (share_code,),
        )
    return [dict(r) for r in rows]


def get_question_records(share_code: str, platform: str = "", page: int = 1, page_size: int = 20):
    conn = get_conn()
    conditions = ["share_code=%s"]
    params: list[Any] = [share_code]
    if platform:
        conditions.append("platform=%s")
        params.append(platform)
    where = " AND ".join(conditions)
    cnt = _fetchone(conn, f"SELECT COUNT(*) as cnt FROM question_record WHERE {where}", params)
    total = cnt["cnt"] if cnt else 0
    offset = (page - 1) * page_size
    rows = _fetchall(conn,
        f"SELECT * FROM question_record WHERE {where} ORDER BY id LIMIT %s OFFSET %s",
        params + [page_size, offset],
    )
    records = []
    for d in rows:
        d = dict(d)
        cites = _fetchall(conn,
            "SELECT * FROM cite_item WHERE question_id=%s ORDER BY cite_index", (d["id"],)
        )
        d["citeList"] = [dict(c) for c in cites]
        d["hasScreenshot"] = bool(d.get("screenshot_url"))
        records.append(d)
    return {"total": total, "page": page, "pageSize": page_size, "records": records}


def get_question_detail(question_id: int) -> Optional[dict]:
    conn = get_conn()
    d = _fetchone(conn, "SELECT * FROM question_record WHERE id=%s", (question_id,))
    if not d:
        return None
    d = dict(d)
    cites = _fetchall(conn,
        "SELECT * FROM cite_item WHERE question_id=%s ORDER BY cite_index", (question_id,)
    )
    d["citeList"] = [dict(c) for c in cites]
    d["hasScreenshot"] = bool(d.get("screenshot_url"))
    return d


# ═══════════════════════════════════════════
# System Settings
# ═══════════════════════════════════════════

_DEFAULT_SETTINGS = {
    # search_api_url 留空：由 overseas_search_adapter 读取环境变量/系统设置。
    
    "search_api_url": "",
    "search_api_timeout": "180",
    "yuanbao_api_url": "",
    "yuanbao_api_timeout": "180",
    "llm_api_mode": "qwen",
    "llm_base_url": "",
    "llm_timeout": "120",
    "llm_model_name": "qwen-plus",
    "llm_api_key": "",
    "claude_model_name": "claude-sonnet-4-20250514",
    "claude_api_key": "",
    "chatgpt_model_name": "gpt-4o-mini",
    "chatgpt_api_key": "",
    "qwen_model_name": "qwen-plus",
    "qwen_api_key": "",
    "firecrawl_api_key": "",
    "firecrawl_api_url": "https://api.firecrawl.dev",
    "firecrawl_concurrency": "5",
    "analysis_industry_name": "通用行业",
    "analysis_brand_supplement": "",
    "analysis_product_supplement": "",
    "analysis_negative_list": "",
    "analysis_suffix_examples": "",
}


def get_all_settings() -> dict:
    conn = get_conn()
    rows = _fetchall(conn, "SELECT setting_key, setting_value FROM system_setting")
    result = dict(_DEFAULT_SETTINGS)
    for r in rows:
        result[r["setting_key"]] = r["setting_value"] or ""
    return result


def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    row = _fetchone(conn, "SELECT setting_value FROM system_setting WHERE setting_key=%s", (key,))
    if row and row["setting_value"]:
        return row["setting_value"]
    return _DEFAULT_SETTINGS.get(key, default)


def save_settings(settings: dict):
    now = _now()
    with transaction() as conn:
        for key, value in settings.items():
            _exec(conn,
                """INSERT INTO system_setting (setting_key, setting_value, updated_at)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE setting_value=%s, updated_at=%s""",
                (key, value, now, value, now),
            )


def get_or_create_flask_secret() -> str:
    import secrets
    val = get_setting("flask_secret_key", "")
    if not val:
        val = secrets.token_hex(32)
        save_settings({"flask_secret_key": val})
    return val


# ═══════════════════════════════════════════
# Official Webhook Config（官网配置）
# ═══════════════════════════════════════════

def get_account_webhook_config(account_id: int) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT id, account_id, webhook_url, oauth_token, enabled, created_by, created_at, updated_at "
        "FROM account_webhook_config WHERE account_id=%s",
        (int(account_id),)
    )
    return dict(row) if row else None


def list_account_webhook_configs() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, account_id, webhook_url, oauth_token, enabled, created_by, created_at, updated_at "
        "FROM account_webhook_config ORDER BY account_id ASC"
    )
    return [dict(r) for r in rows]


def save_account_webhook_config(account_id: int, webhook_url: str, oauth_token: str,
                                created_by: int | None = None, enabled: bool = True) -> dict:
    now = _now()
    with transaction() as conn:
        _exec(conn,
            """INSERT INTO account_webhook_config
               (account_id, webhook_url, oauth_token, enabled, created_by, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                 webhook_url=VALUES(webhook_url),
                 oauth_token=VALUES(oauth_token),
                 enabled=VALUES(enabled),
                 created_by=VALUES(created_by),
                 updated_at=VALUES(updated_at)""",
            (int(account_id), webhook_url, oauth_token, 1 if enabled else 0,
             int(created_by) if created_by else None, now, now)
        )
    return get_account_webhook_config(int(account_id)) or {}


def clear_account_webhook_config(account_id: int) -> bool:
    with transaction() as conn:
        cur = _exec(conn, "DELETE FROM account_webhook_config WHERE account_id=%s", (int(account_id),))
        return bool((cur.rowcount or 0) > 0)


# ═══════════════════════════════════════════
# Quote (报价管理)
# ═══════════════════════════════════════════

def create_quote_task(task_id: str, account_id: int, base_price: float = 2500000.0) -> dict:
    now = _now()
    with transaction() as conn:
        _exec(conn,
            """INSERT INTO quote_task (id, account_id, status, stage, base_price, created_at, last_heartbeat)
               VALUES (%s, %s, 'queued', 'pending', %s, %s, %s)""",
            (task_id, account_id, base_price, now, now),
        )
    return get_quote_task(task_id)


def touch_quote_task_heartbeat(task_id: str) -> None:
    conn = get_conn()
    _exec(conn, "UPDATE quote_task SET last_heartbeat=%s WHERE id=%s", (_now(), task_id))
    conn.commit()


def recover_stuck_kb_gen(stuck_min: int = 25) -> int:
    """知识库生成线程被中断(worker 重载/异常)卡 status='running'，但生成参数
    (素材ids/指令/上传报告)只在内存未存 DB → 无法自动续跑。超时自动标 failed，
    解除前端 running、允许用户重新发起。返回清理数。"""
    now = _now()
    msg = f"生成超时或线程中断(>{int(stuck_min)}min未完成)，已自动标记失败，请重新发起生成"
    sql = ("UPDATE kb_gen_task SET status='failed', error=%s, updated_at=%s "
           "WHERE status='running' AND "
           "STR_TO_DATE(created_at,'%%Y-%%m-%%d %%H:%%i:%%s') < (NOW() - INTERVAL "
           + str(int(stuck_min)) + " MINUTE)")
    with transaction() as conn:
        cur = _exec(conn, sql, (msg, now))
        try:
            return cur.rowcount or 0
        except Exception:
            return 0


def reap_stale_running_tasks(stale_seconds: int = 180) -> int:
    # 180s(原 300s):心跳停后更快判死,缩短前端把僵尸 inflight 误显示为"查询中"的窗口。
    # 正常 worker 心跳间隔远小于此,不会误杀活任务。
    cutoff_dt = datetime.now() - timedelta(seconds=stale_seconds)
    cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    now = _now()
    with transaction() as conn:
        cur1 = _exec(conn,
            """UPDATE search_task
                 SET status='ERROR',
                     error_message='服务中断，任务心跳超时',
                     live_inflight=NULL,
                     completed_at=%s
               WHERE status='RUNNING'
                 AND (last_heartbeat IS NULL OR last_heartbeat < %s)""",
            (now, cutoff),
        )
        r1 = cur1.rowcount
        cur2 = _exec(conn,
            """UPDATE quote_task
                 SET status='error',
                     error_message='服务中断，任务心跳超时',
                     completed_at=%s
               WHERE status IN ('queued','running')
                 AND (last_heartbeat IS NULL OR last_heartbeat < %s)""",
            (now, cutoff),
        )
        r2 = cur2.rowcount
    return (r1 or 0) + (r2 or 0)


def preempt_stalled_running_tasks() -> int:
    """S3.2 头部阻塞抢占：终结"心跳还活着但进度长时间零增长"的卡死任务，释放槽位。

    与 reap_stale_running_tasks 区别：
      - reaper 看 last_heartbeat（心跳线程死了才判）
      - 本函数看 last_progress_at（心跳活着但查询全卡住，completed 不增长）

    精准性：正常慢任务（DeepSeek 单查询可能 60-120s）只要持续有 progress
    （成功或失败都会调 update_search_task_progress），last_progress_at 持续刷新，
    不会被误判。只有所有查询都卡死（如上游全挂）才会触发。

    feature flag stall_preempt_enabled（默认 OFF，灰度）。
    阈值 stall_preempt_minutes（默认 15min，远大于单查询 timeout 400s）。
    逐个走 update_search_task_status → 自动触发 counter -1 钩子，真正释放槽位。
    """
    try:
        import redis_helper
        if not redis_helper.is_enabled("stall_preempt_enabled"):
            return 0
    except Exception:
        return 0

    try:
        stall_min = int(get_setting("stall_preempt_minutes", "15") or "15")
    except (ValueError, TypeError):
        stall_min = 15
    stall_min = max(5, min(120, stall_min))  # clamp 5-120min 防误配
    cutoff = (datetime.now() - timedelta(minutes=stall_min)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    # 候选：RUNNING + 未完成 + 进度停滞（基准 COALESCE(last_progress_at, created_at)）
    rows = _fetchall(conn,
        "SELECT id, completed_queries, total_queries, "
        "COALESCE(last_progress_at, created_at) AS base_ts "
        "FROM search_task "
        "WHERE status='RUNNING' "
        "AND (total_queries IS NULL OR completed_queries < total_queries) "
        "AND COALESCE(last_progress_at, created_at) < %s",
        (cutoff,))
    n = 0
    for r in rows:
        tid = r["id"]
        try:
            # 走 update_search_task_status → counter -1 钩子真正释放槽位
            update_search_task_status(
                tid, "ERROR",
                "进度停滞 %dmin 疑似卡死，自动释放槽位（S3.2 头部阻塞抢占）" % stall_min)
            n += 1
        except Exception:
            import logging as _lg
            _lg.getLogger("db").exception("[s3.2] preempt task=%s failed", tid)
    return n


def update_quote_task(task_id: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields.keys())
    values = list(fields.values()) + [task_id]
    with transaction() as conn:
        _exec(conn, f"UPDATE quote_task SET {cols} WHERE id=%s", values)


def get_quote_task(task_id: str) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        """SELECT qt.*, a.company_name, a.company_brand
           FROM quote_task qt LEFT JOIN account a ON a.id = qt.account_id
           WHERE qt.id=%s""", (task_id,)
    )
    return _quote_task_to_dict(row) if row else None


def list_quote_tasks() -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT qt.*, a.company_name, a.company_brand
           FROM quote_task qt LEFT JOIN account a ON a.id = qt.account_id
           ORDER BY qt.created_at DESC""",
    )
    return [_quote_task_to_dict(r) for r in rows]


def delete_quote_task(task_id: str):
    with transaction() as conn:
        rows = _fetchall(conn,
            "SELECT id FROM quote_query_run WHERE quote_task_id=%s", (task_id,)
        )
        run_ids = [r["id"] for r in rows]
        if run_ids:
            placeholders = ",".join(["%s"] * len(run_ids))
            _exec(conn, f"DELETE FROM quote_result WHERE query_run_id IN ({placeholders})", tuple(run_ids))
        _exec(conn, "DELETE FROM quote_query_run WHERE quote_task_id=%s", (task_id,))
        _exec(conn, "DELETE FROM quote_task WHERE id=%s", (task_id,))


def _quote_task_to_dict(row) -> dict:
    if not row:
        return None
    d = dict(row)
    return {
        "id": d["id"],
        "accountId": d["account_id"],
        "companyName": d.get("company_name", ""),
        "companyBrand": d.get("company_brand", ""),
        "status": d["status"],
        "stage": d.get("stage", ""),
        "progressDone": d.get("progress_done", 0) or 0,
        "progressTotal": d.get("progress_total", 0) or 0,
        "basePrice": d.get("base_price", 2500000.0) or 2500000.0,
        "finalScore": d.get("final_score"),
        "finalPrice": d.get("final_price"),
        "errorMessage": d.get("error_message", "") or "",
        "createdAt": d.get("created_at", ""),
        "startedAt": d.get("started_at", ""),
        "completedAt": d.get("completed_at", ""),
    }


def create_quote_query_run(quote_task_id: str, keyword: str, model: str) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO quote_query_run (quote_task_id, keyword, model, status, created_at)
               VALUES (%s, %s, %s, 'pending', %s)""",
            (quote_task_id, keyword, model, now),
        )
        return cur.lastrowid


def update_quote_query_run(run_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields.keys())
    values = list(fields.values()) + [run_id]
    with transaction() as conn:
        _exec(conn, f"UPDATE quote_query_run SET {cols} WHERE id=%s", values)


def list_quote_query_runs(quote_task_id: str) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM quote_query_run WHERE quote_task_id=%s ORDER BY id",
        (quote_task_id,),
    )
    return [dict(r) for r in rows]


def save_quote_result(data: dict) -> int:
    now = _now()
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO quote_result (
                query_run_id, source_site, source_url, title,
                page_content, scrape_status, pub_date, content_type, website_type,
                clean_content, relevance_percent, relevance_level, relevance_reason,
                extract_status, d1, d2, d3, d4, d5, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data["query_run_id"],
                data.get("source_site", ""),
                data.get("source_url", ""),
                data.get("title", ""),
                data.get("page_content", ""),
                data.get("scrape_status", "pending"),
                data.get("pub_date", ""),
                data.get("content_type", ""),
                data.get("website_type", ""),
                data.get("clean_content", ""),
                data.get("relevance_percent"),
                data.get("relevance_level"),
                data.get("relevance_reason", ""),
                data.get("extract_status", "pending"),
                data.get("d1"), data.get("d2"), data.get("d3"),
                data.get("d4"), data.get("d5"),
                now,
            ),
        )
        return cur.lastrowid


def update_quote_result(result_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=%s" for k in fields.keys())
    values = list(fields.values()) + [result_id]
    with transaction() as conn:
        _exec(conn, f"UPDATE quote_result SET {cols} WHERE id=%s", values)


def list_quote_results(query_run_id: int) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM quote_result WHERE query_run_id=%s ORDER BY id",
        (query_run_id,),
    )
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
# Scheduled search task
# ═══════════════════════════════════════════

def _sched_to_dict(row, account: Optional[dict] = None) -> dict:
    if not row:
        return None
    d = dict(row)
    try:
        models = json.loads(d.get("models") or "[]")
    except Exception:
        models = []
    last_task_id = d.get("last_task_id") or ""
    execution_running = False
    if last_task_id:
        try:
            conn = get_conn()
            trow = _fetchone(conn, "SELECT status FROM search_task WHERE id=%s", (last_task_id,))
            if trow and str(trow.get("status") or "").upper() == "RUNNING":
                execution_running = True
        except Exception:
            pass
    return {
        "id": d["id"],
        "accountId": d["account_id"],
        "name": d.get("name") or "",
        "subType": d.get("sub_type") or "search",
        "taskType": "single",
        "models": models,
        "frequency": d.get("frequency", "daily"),
        "runTime": d.get("run_time", "00:01"),
        "dayOfWeek": d.get("day_of_week", 6),
        "dayOfMonth": d.get("day_of_month", -1),
        "enabled": bool(d.get("enabled", 1)),
        "nextRunAt": d.get("next_run_at") or "",
        "lastRunAt": d.get("last_run_at") or "",
        "lastTaskId": last_task_id,
        "lastStatus": d.get("last_status") or "",
        "lastFailCount": int(d.get("last_fail_count") or 0),
        "lastSuccessCount": int(d.get("last_success_count") or 0),
        "lastTotalCount": int(d.get("last_total_count") or 0),
        "manualTriggerPending": bool(d.get("manual_trigger_pending", 0)),
        "executionLock": d.get("execution_lock") or "",  # 【关键】执行锁字段
        "executionRunning": execution_running,
        "createdAt": d.get("created_at") or "",
        "companyName": (account or {}).get("companyName", d.get("company_name") or ""),
        "companyBrand": (account or {}).get("companyBrand", d.get("company_brand") or ""),
    }


def compute_next_run(frequency: str, run_time: str, day_of_week: int, day_of_month: int,
                     base: Optional[datetime] = None) -> str:
    base = base or datetime.now()
    try:
        hh, mm = [int(x) for x in (run_time or "00:01").split(":")]
    except Exception:
        hh, mm = 0, 1

    if frequency == "daily":
        candidate = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate.strftime("%Y-%m-%d %H:%M:%S")

    if frequency == "weekly":
        target_dow = int(day_of_week) if day_of_week is not None else 6
        today = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        delta = (target_dow - today.weekday()) % 7
        candidate = today + timedelta(days=delta)
        if candidate <= base:
            candidate += timedelta(days=7)
        return candidate.strftime("%Y-%m-%d %H:%M:%S")

    if frequency == "monthly":
        year = base.year
        month = base.month
        for _ in range(2):
            last_day = calendar.monthrange(year, month)[1]
            dom = day_of_month if day_of_month and day_of_month > 0 else last_day
            dom = min(dom, last_day)
            candidate = datetime(year, month, dom, hh, mm, 0)
            if candidate > base:
                return candidate.strftime("%Y-%m-%d %H:%M:%S")
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        return candidate.strftime("%Y-%m-%d %H:%M:%S")

    candidate = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= base:
        candidate += timedelta(days=1)
    return candidate.strftime("%Y-%m-%d %H:%M:%S")


def create_scheduled_search_task(data: dict) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    frequency = data.get("frequency") or "daily"
    run_time = data.get("runTime") or "00:01"
    day_of_week = int(data.get("dayOfWeek") if data.get("dayOfWeek") is not None else 6)
    day_of_month = int(data.get("dayOfMonth") if data.get("dayOfMonth") is not None else -1)
    sub_type = data.get("subType") or "search"
    next_run = compute_next_run(frequency, run_time, day_of_week, day_of_month)
    models_json = json.dumps(data.get("models") or [], ensure_ascii=False)
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO scheduled_search_task
               (account_id, name, sub_type, models, frequency, run_time, day_of_week, day_of_month,
                enabled, next_run_at, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (int(data["accountId"]), data.get("name") or "", sub_type, models_json, frequency,
             run_time, day_of_week, day_of_month, 1 if data.get("enabled", True) else 0,
             next_run, now),
        )
        new_id = cur.lastrowid
    return get_scheduled_search_task(new_id)


def update_scheduled_search_task(sched_id: int, data: dict) -> Optional[dict]:
    row = get_scheduled_search_task(sched_id)
    if not row:
        return None
    frequency = data.get("frequency", row["frequency"])
    run_time = data.get("runTime", row["runTime"])
    day_of_week = int(data.get("dayOfWeek", row["dayOfWeek"]))
    day_of_month = int(data.get("dayOfMonth", row["dayOfMonth"]))
    enabled = 1 if data.get("enabled", row["enabled"]) else 0
    models = data.get("models", row["models"])
    models_json = json.dumps(models or [], ensure_ascii=False)
    name = data.get("name", row["name"])
    sub_type = data.get("subType", row.get("subType", "search"))
    next_run = compute_next_run(frequency, run_time, day_of_week, day_of_month)
    with transaction() as conn:
        _exec(conn,
            """UPDATE scheduled_search_task
               SET name=%s, sub_type=%s, models=%s, frequency=%s, run_time=%s, day_of_week=%s, day_of_month=%s,
                   enabled=%s, next_run_at=%s
               WHERE id=%s""",
            (name, sub_type, models_json, frequency, run_time, day_of_week, day_of_month,
             enabled, next_run, sched_id),
        )
    return get_scheduled_search_task(sched_id)


def delete_scheduled_search_task(sched_id: int):
    with transaction() as conn:
        _exec(conn, "DELETE FROM scheduled_search_task WHERE id=%s", (sched_id,))


def get_scheduled_search_task(sched_id: int) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_search_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE s.id=%s""", (sched_id,)
    )
    return _sched_to_dict(row) if row else None


def list_scheduled_search_tasks(owner_id: int | None = None, team_id: int | None = None) -> list[dict]:
    conn = get_conn()
    select_extra = (
        ", (SELECT COUNT(*) FROM search_result WHERE task_id = s.last_task_id AND success = 0) AS last_fail_count"
        ", (SELECT COUNT(*) FROM search_result WHERE task_id = s.last_task_id AND success = 1) AS last_success_count"
        ", (SELECT COUNT(*) FROM search_result WHERE task_id = s.last_task_id) AS last_total_count"
    )
    base = (f"SELECT s.*, a.company_name, a.company_brand{select_extra} "
            "FROM scheduled_search_task s LEFT JOIN account a ON a.id = s.account_id")
    if team_id is not None:
        rows = _fetchall(conn, base + " WHERE a.team_id=%s ORDER BY s.id DESC", (team_id,))
    elif owner_id is not None:
        rows = _fetchall(conn, base + " WHERE (a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)) ORDER BY s.id DESC", (owner_id, owner_id))
    else:
        rows = _fetchall(conn, base + " ORDER BY s.id DESC")
    return [_sched_to_dict(r) for r in rows]


def list_due_scheduled_tasks(now: Optional[datetime] = None) -> list[dict]:
    now = now or datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_search_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE (s.enabled = 1 AND s.next_run_at IS NOT NULL AND s.next_run_at <= %s)
              OR s.manual_trigger_pending = 1
           ORDER BY s.manual_trigger_pending DESC, s.next_run_at ASC""",
        (now_str,)
    )
    return [_sched_to_dict(r) for r in rows]


def mark_scheduled_task_manual_trigger(sched_id: int) -> Optional[dict]:
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_search_task SET manual_trigger_pending=1 WHERE id=%s",
            (sched_id,),
        )
    return get_scheduled_search_task(sched_id)


def clear_scheduled_task_manual_trigger(sched_id: int):
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_search_task SET manual_trigger_pending=0 WHERE id=%s",
            (sched_id,),
        )


def update_scheduled_task_last_run(sched_id: int, task_id: str, status: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_search_task SET last_run_at=%s, last_task_id=%s, last_status=%s WHERE id=%s",
            (now, task_id, status, sched_id),
        )


def advance_scheduled_task_next_run(sched_id: int):
    row = get_scheduled_search_task(sched_id)
    if not row:
        return
    next_run = compute_next_run(
        row["frequency"], row["runTime"], row["dayOfWeek"], row["dayOfMonth"],
        base=datetime.now(),
    )
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_search_task SET next_run_at=%s WHERE id=%s",
            (next_run, sched_id),
        )


def add_scheduled_task_history(sched_id: int, account_id: int, task_id: str, status: str,
                                started_at: str, finished_at: str, duration: int,
                                trigger_type: str = "scheduled", detail: str = None) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 【标记】写入文件确认此函数被调用（使用绝对路径）
    import traceback
    log_path = r'C:\Users\Administrator\Desktop\geo-ops-system\_db_hist_log.txt'
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{now}] add_scheduled_task_history called: sched_id={sched_id}, type={trigger_type}, task_id={task_id[:12] if task_id else ''}\n")
            f.write(f"  CALLER: {''.join(traceback.format_stack()[-3:-1])}\n")
    except Exception as write_err:
        pass  # 静默失败
    
    # 【最终防重复】120秒内同一个 sched_id 只允许一条记录 - 强制删除旧记录
    conn_check = get_conn()
    recent = _fetchone(conn_check,
        """SELECT id, trigger_type FROM scheduled_task_history 
           WHERE sched_id=%s AND created_at >= DATE_SUB(%s, INTERVAL 120 SECOND)
           ORDER BY id DESC LIMIT 1""",
        (sched_id, now)
    )
    
    # 如果120秒内已有任何记录，先删除再插入新的
    if recent:
        old_id = recent.get('id')
        old_type = recent.get('trigger_type')
        try:
            _exec(conn_check,
                "DELETE FROM scheduled_task_history WHERE id=%s",
                (old_id,)
            )
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"  -> DELETE old id={old_id} type={old_type} (replacing with new type={trigger_type})\n")
        except Exception as del_err:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"  -> DELETE failed: {del_err}\n")
    
    # 正常插入
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO scheduled_task_history
               (sched_id, account_id, task_id, status, started_at, finished_at,
                duration_seconds, trigger_type, detail, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (sched_id, account_id, task_id, status, started_at, finished_at,
             duration, trigger_type, detail, now),
        )
        new_id = cur.lastrowid
        
        # 记录成功插入
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"  -> INSERT id={new_id} type={trigger_type}\n")
        except: pass
        
        return new_id


def list_scheduled_task_history(sched_id: int, limit: int = 50) -> list[dict]:
    """返回定时任务执行历史，包含关联的子任务（查词/排名）详情"""
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT h.*, s.name AS sched_name, a.company_name
           FROM scheduled_task_history h
           LEFT JOIN scheduled_search_task s ON s.id = h.sched_id
           LEFT JOIN account a ON a.id = h.account_id
           WHERE h.sched_id=%s
           ORDER BY h.started_at DESC
           LIMIT %s""",
        (sched_id, limit),
    )
    result = []
    for r in rows:
        d = dict(r) if isinstance(r, dict) else {k: r[i] for i, k in enumerate(r._fields)} if hasattr(r, '_fields') else dict(zip(r.keys(), r)) if hasattr(r, 'keys') else {}
        if not d:
            d = {"id": r[0], "schedId": r[1], "accountId": r[2], "taskId": r[3],
                  "status": r[4], "startedAt": r[5], "finishedAt": r[6],
                  "durationSeconds": r[7], "triggerType": r[8], "detail": r[9]}
        else:
            d = {
                "id": d.get("id"),
                "schedId": d.get("sched_id"),
                "accountId": d.get("account_id"),
                "taskId": d.get("task_id"),
                "status": d.get("status"),
                "startedAt": d.get("started_at"),
                "finishedAt": d.get("finished_at"),
                "durationSeconds": d.get("duration_seconds"),
                "triggerType": d.get("trigger_type"),
                "detail": d.get("detail"),
                "schedName": d.get("sched_name") or d.get("name"),
                "companyName": d.get("company_name"),
            }
        
        # 查找关联的子任务详情（search_task）
        task_id = d.get("taskId") or ""
        sub_tasks = []
        if task_id:
            try:
                # 查找主任务
                main_task = _fetchone(conn,
                    """SELECT id, status, created_at, completed_at,
                              total_queries, completed_queries, error_message
                       FROM search_task WHERE id=%s LIMIT 1""",
                    (task_id,)
                )
                if main_task:
                    sub_tasks.append({
                        "type": "keyword_search",
                        "name": "查词",
                        "taskId": main_task.get("id"),
                        "status": main_task.get("status"),
                        "startedAt": str(main_task.get("created_at") or ""),
                        "finishedAt": str(main_task.get("completed_at") or ""),
                        "totalQueries": main_task.get("total_queries") or 0,
                        "completedQueries": main_task.get("completed_queries") or 0,
                        "errorMessage": main_task.get("error_message") or "",
                    })
                    
                    # 获取模型级统计
                    model_rows = _fetchall(conn,
                        """SELECT model,
                                  COUNT(*) as total,
                                  SUM(success = 1) as success_count,
                                  SUM(success = 0) as fail_count
                           FROM search_result WHERE task_id=%s
                           GROUP BY model ORDER BY model""",
                        (task_id,),
                    )
                    sub_tasks[-1]["modelStats"] = [{
                        "model": mr["model"],
                        "total": int(mr["total"] or 0),
                        "success": int(mr["success_count"] or 0),
                        "fail": int(mr["fail_count"] or 0),
                    } for mr in model_rows]
            except Exception:
                pass
        
        d["subTasks"] = sub_tasks
        result.append(d)
    
    return {"items": result, "total": len(result)}




# ========== Scheduled Ranking Tasks ==========

def create_scheduled_ranking_task(data: dict) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    frequency = data.get("frequency") or "daily"
    run_time = data.get("runTime") or "02:00"
    day_of_week = int(data.get("dayOfWeek") if data.get("dayOfWeek") is not None else 6)
    day_of_month = int(data.get("dayOfMonth") if data.get("dayOfMonth") is not None else -1)
    next_run = compute_next_run(frequency, run_time, day_of_week, day_of_month)
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO scheduled_ranking_task
               (account_id, name, frequency, run_time, day_of_week, day_of_month,
                enabled, next_run_at, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (int(data["accountId"]), data.get("name") or "", frequency,
             run_time, day_of_week, day_of_month, 1 if data.get("enabled", True) else 0,
             next_run, now),
        )
        new_id = cur.lastrowid
    return get_scheduled_ranking_task(new_id)


def get_scheduled_ranking_task(sched_id: int):
    conn = get_conn()
    row = _fetchone(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_ranking_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE s.id=%s""", (sched_id,)
    )
    return _sched_ranking_to_dict(row) if row else None


def list_scheduled_ranking_tasks() -> list:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_ranking_task s LEFT JOIN account a ON a.id = s.account_id
           ORDER BY s.id DESC"""
    )
    return [_sched_ranking_to_dict(r) for r in rows]


def update_scheduled_ranking_task(sched_id: int, data: dict):
    row = get_scheduled_ranking_task(sched_id)
    if not row:
        return None
    frequency = data.get("frequency", row["frequency"])
    run_time = data.get("runTime", row["runTime"])
    day_of_week = int(data.get("dayOfWeek", row["dayOfWeek"]))
    day_of_month = int(data.get("dayOfMonth", row["dayOfMonth"]))
    enabled = 1 if data.get("enabled", row["enabled"]) else 0
    name = data.get("name", row.get("name", ""))
    next_run = compute_next_run(frequency, run_time, day_of_week, day_of_month)
    with transaction() as conn:
        _exec(conn,
            """UPDATE scheduled_ranking_task
               SET name=%s, frequency=%s, run_time=%s, day_of_week=%s, day_of_month=%s,
                   enabled=%s, next_run_at=%s
               WHERE id=%s""",
            (name, frequency, run_time, day_of_week, day_of_month,
             enabled, next_run, sched_id),
        )
    return get_scheduled_ranking_task(sched_id)


def delete_scheduled_ranking_task(sched_id: int):
    with transaction() as conn:
        _exec(conn, "DELETE FROM scheduled_ranking_task WHERE id=%s", (sched_id,))


def toggle_scheduled_ranking_task(sched_id: int):
    row = get_scheduled_ranking_task(sched_id)
    if not row:
        return None
    new_enabled = 0 if row["enabled"] else 1
    next_run = None
    if new_enabled:
        next_run = compute_next_run(row["frequency"], row["runTime"], row["dayOfWeek"], row["dayOfMonth"])
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_ranking_task SET enabled=%s, next_run_at=%s WHERE id=%s",
            (new_enabled, next_run, sched_id),
        )
    return get_scheduled_ranking_task(sched_id)


def mark_scheduled_ranking_manual_trigger(sched_id: int):
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_ranking_task SET manual_trigger_pending=1 WHERE id=%s",
            (sched_id,),
        )
    return get_scheduled_ranking_task(sched_id)


def clear_scheduled_ranking_manual_trigger(sched_id: int):
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_ranking_task SET manual_trigger_pending=0 WHERE id=%s",
            (sched_id,),
        )


def update_scheduled_ranking_last_run(sched_id: int, task_id: str, status: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_ranking_task SET last_run_at=%s, last_task_id=%s, last_status=%s WHERE id=%s",
            (now, task_id, status, sched_id),
        )


def advance_scheduled_ranking_next_run(sched_id: int):
    row = get_scheduled_ranking_task(sched_id)
    if not row:
        return
    next_run = compute_next_run(
        row["frequency"], row["runTime"], row["dayOfWeek"], row["dayOfMonth"],
        base=datetime.now(),
    )
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_ranking_task SET next_run_at=%s WHERE id=%s",
            (next_run, sched_id),
        )


def list_due_scheduled_ranking_tasks(now=None):
    now = now or datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_ranking_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE (s.enabled = 1 AND s.next_run_at IS NOT NULL AND s.next_run_at <= %s)
              OR s.manual_trigger_pending = 1
           ORDER BY s.manual_trigger_pending DESC, s.next_run_at ASC""",
        (now_str,)
    )
    return [_sched_ranking_to_dict(r) for r in rows]


def _sched_ranking_to_dict(row) -> dict:
    if not row:
        return {}
    last_task_id = row.get("last_task_id", "") or ""
    execution_running = False
    if last_task_id:
        try:
            conn = get_conn()
            trow = _fetchone(conn, "SELECT status FROM ranking_task WHERE id=%s", (last_task_id,))
            if trow and str(trow.get("status") or "").lower() == "running":
                execution_running = True
        except Exception:
            pass
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "name": row.get("name", ""),
        "companyName": row.get("company_name", ""),
        "companyBrand": row.get("company_brand", ""),
        "frequency": row.get("frequency", "daily"),
        "runTime": row.get("run_time", "02:00"),
        "dayOfWeek": row.get("day_of_week", 6),
        "dayOfMonth": row.get("day_of_month", -1),
        "enabled": bool(row.get("enabled", 0)),
        "nextRunAt": str(row["next_run_at"]) if row.get("next_run_at") else None,
        "lastRunAt": str(row["last_run_at"]) if row.get("last_run_at") else None,
        "lastTaskId": last_task_id,
        "lastStatus": row.get("last_status", ""),
        "manualTriggerPending": bool(row.get("manual_trigger_pending", 0)),
        "executionRunning": execution_running,
    }

def get_site_price_lookup() -> dict:
    conn = get_conn()
    rows = _fetchall(conn, "SELECT name, cost FROM site_price WHERE status=1 AND cost > 0")
    lookup = {}
    for r in rows:
        name = (r["name"] or "").strip().lower()
        if name and name not in lookup:
            lookup[name] = float(r["cost"])
    return lookup


def get_today_search_stats() -> dict:
    """当日各模型查词数量、成功率、平均耗时"""
    conn = get_conn()
    today = _now()[:10]
    rows = _fetchall(conn,
        "SELECT model, COUNT(*) AS cnt, SUM(success) AS ok, "
        "ROUND(AVG(duration),2) AS avg_dur "
        "FROM search_result WHERE search_date=%s GROUP BY model",
        (today,),
    )
    models = []
    total_cnt = total_ok = 0
    dur_sum = 0.0
    for r in rows:
        cnt = int(r["cnt"] or 0)
        ok = int(r["ok"] or 0)
        avg_d = float(r["avg_dur"] or 0)
        models.append({
            "model": r["model"],
            "count": cnt,
            "successCount": ok,
            "successRate": round(ok / cnt * 100, 1) if cnt else 0,
            "avgDuration": avg_d,
        })
        total_cnt += cnt
        total_ok += ok
        dur_sum += avg_d * cnt
    return {
        "date": today,
        "models": models,
        "totalCount": total_cnt,
        "totalSuccess": total_ok,
        "totalSuccessRate": round(total_ok / total_cnt * 100, 1) if total_cnt else 0,
        "totalAvgDuration": round(dur_sum / total_cnt, 2) if total_cnt else 0,
    }


def get_retry_stats(days: int = 7,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> dict:
    """P5 重试可观测：按平台聚合重试率/平均尝试/失败率/确定性失败占比，
    让"某上游平台开始抽风/不支持"能被及时发现（纯只读，零副作用）。
    优先级: (start_date, end_date) > days。
    - days: 统计窗口(search_date 近 N 天,clamp 1-90)
    - start_date/end_date: YYYY-MM-DD 自定义区间(含两端)
    """
    from datetime import datetime as _dt, timedelta as _td
    import re as _re
    _date_re = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
    use_range = bool(start_date and end_date and _date_re.match(start_date) and _date_re.match(end_date))
    if use_range:
        since = start_date
        until = end_date
    else:
        try:
            days = max(1, min(90, int(days)))
        except (TypeError, ValueError):
            days = 7
        since = (_dt.now() - _td(days=days - 1)).strftime("%Y-%m-%d")
        until = _dt.now().strftime("%Y-%m-%d")
    conn = get_conn()
    # 严格互斥分区:total = bk_true_one + bk_init_2 + bk_init_3 + bk_init_gt3 + bk_rescue + bk_final_fail
    # (五次以上 = bk_init_gt5 是 bk_init_gt3 的子集,仅用于额外标注严重度,不参与加和)
    rows = _fetchall(conn,
        "SELECT platform, model, "
        "COUNT(*) AS total, "
        "ROUND(AVG(attempt),2) AS avg_attempt, "
        "MAX(attempt) AS max_attempt, "
        "SUM(CASE WHEN INSTR(error_message, '确定性失败') > 0 THEN 1 ELSE 0 END) AS det_cnt, "
        # === 互斥 6 桶(全部 success=1 的 5 桶 + success=0 的 1 桶)===
        "SUM(rescue_round='initial' AND attempt=1  AND success=1) AS bk_true_one, "    # 真一次过
        "SUM(rescue_round='initial' AND attempt=2  AND success=1) AS bk_init_2, "     # 二次救
        "SUM(rescue_round='initial' AND attempt=3  AND success=1) AS bk_init_3, "     # 三次救
        "SUM(rescue_round='initial' AND attempt>=4 AND success=1) AS bk_init_gt3, "   # 三次以上救
        "SUM(rescue_round<>'initial' AND success=1) AS bk_rescue, "                    # 跨行救援(sweep/morning/manual)
        "SUM(success=0) AS bk_final_fail, "                                            # 终败(所有救援均失败)
        # === 子集/辅助 ===
        "SUM(rescue_round='initial' AND attempt>=5 AND success=1) AS bk_init_gt5, "   # 五次以上(⊂ 三次以上)
        "SUM(rescue_round='sweep'         AND success=1) AS bk_rescue_sweep, "
        "SUM(rescue_round='morning_retry' AND success=1) AS bk_rescue_morning, "
        "SUM(rescue_round='manual_retry'  AND success=1) AS bk_rescue_manual "
        "FROM search_result WHERE search_date >= %s AND search_date <= %s "
        "GROUP BY platform, model ORDER BY total DESC",
        (since, until))
    platforms = []
    for r in rows:
        total = int(r["total"] or 0)
        pct = lambda v: round(int(v or 0) / total * 100, 1) if total else 0
        # 6 个互斥桶
        bk_true_one    = int(r["bk_true_one"] or 0)
        bk_init_2      = int(r["bk_init_2"] or 0)
        bk_init_3      = int(r["bk_init_3"] or 0)
        bk_init_gt3    = int(r["bk_init_gt3"] or 0)
        bk_rescue      = int(r["bk_rescue"] or 0)
        bk_final_fail  = int(r["bk_final_fail"] or 0)
        bk_sum = bk_true_one + bk_init_2 + bk_init_3 + bk_init_gt3 + bk_rescue + bk_final_fail
        platforms.append({
            "platform": r["platform"],
            "model": r["model"],
            "total": total,
            "avgAttempt": float(r["avg_attempt"] or 0),
            "maxAttempt": int(r["max_attempt"] or 0),
            "deterministicFail": int(r["det_cnt"] or 0),
            # ── 互斥 6 桶,sum 严格等于 total ──
            "buckets": {
                "trueOneShot":  {"count": bk_true_one,    "pct": pct(bk_true_one)},     # 真一次过
                "initRetry2":   {"count": bk_init_2,      "pct": pct(bk_init_2)},       # 二次救
                "initRetry3":   {"count": bk_init_3,      "pct": pct(bk_init_3)},       # 三次救
                "initRetryGt3": {"count": bk_init_gt3,    "pct": pct(bk_init_gt3)},     # 三次以上救
                "rescue":       {"count": bk_rescue,      "pct": pct(bk_rescue)},       # 跨行救援
                "finalFail":    {"count": bk_final_fail,  "pct": pct(bk_final_fail)},   # 终败
            },
            # 互斥校验:bucketsSum == total 表示口径一致(用于前端校验显示)
            "bucketsSum": bk_sum,
            "bucketsValid": bk_sum == total,
            # 子集/辅助
            "initRetryGt5": {"count": int(r["bk_init_gt5"] or 0), "pct": pct(r["bk_init_gt5"])},  # ⊂ 三次以上
            # 跨行救援按来源拆分
            "rescueBreakdown": {
                "sweep":         {"count": int(r["bk_rescue_sweep"] or 0),   "pct": pct(r["bk_rescue_sweep"])},
                "morningRetry":  {"count": int(r["bk_rescue_morning"] or 0), "pct": pct(r["bk_rescue_morning"])},
                "manualRetry":   {"count": int(r["bk_rescue_manual"] or 0),  "pct": pct(r["bk_rescue_manual"])},
            },
        })
    return {"sinceDate": since, "untilDate": until,
            "days": (None if use_range else days),
            "rangeMode": "custom" if use_range else "days",
            "platforms": platforms}


def get_failed_results_for_task(task_id: str) -> list[dict]:
    """获取指定任务中失败的查询记录(按 keyword+model 去重,只取最新一条)。

    H2 修复:之前直接返回所有 success=0 行,如果并发竞态下同 (kw,model) 写了
    多行 fail(已实测发生过),sweep 会对同一 pair 发两次请求 → 浪费 + 升高
    上游 503 概率。这里用 MAX(id) 保留最新 fail 行,sweep 一次只处理一个 pair。
    """
    conn = get_conn()
    return _fetchall(conn,
        "SELECT r.id, r.keyword, r.model, r.platform, r.intent_category, "
        "r.core_intent_word, r.intent_prompt, r.keyword_id "
        "FROM search_result r "
        "INNER JOIN (SELECT MAX(id) AS max_id FROM search_result "
        "  WHERE task_id=%s AND success=0 GROUP BY keyword, model) t "
        "ON r.id = t.max_id ORDER BY r.id",
        (task_id,),
    )


def get_unsearched_pairs(account_id: int, date: str, models: list[str]) -> list[dict]:
    """获取指定账户在指定日期还未成功查询的 关键词×模型 对"""
    conn = get_conn()
    keywords = get_keywords(account_id)
    if not keywords:
        return []
    # 查已成功的 keyword+model 组合
    done_rows = _fetchall(conn,
        "SELECT keyword, model FROM search_result "
        "WHERE account_id=%s AND search_date=%s AND success=1",
        (account_id, date),
    )
    done_set = {(r["keyword"], r["model"]) for r in done_rows}

    missing = []
    for kw in keywords:
        prompt = kw.get("intentPrompt", "")
        if not prompt:
            continue
        for model in models:
            if (prompt, model) not in done_set:
                missing.append({
                    "keyword": prompt,
                    "model": model,
                    "keyword_id": kw.get("id"),
                    "intentCategory": kw.get("intentCategory", ""),
                    "coreIntentWord": kw.get("coreIntentWord", ""),
                    "intentPrompt": prompt,
                })
    return missing


def get_running_task_for_account(account_id: int) -> Optional[dict]:
    """获取指定账户进行中的查词任务（RUNNING/PENDING/ERROR）。
    worker-daemon 模式下 start 后任务先是 PENDING、由 worker 捞起才转 RUNNING;
    前端详情页据此立即 attach + 轮询,避免"刚点查词看不到日志、要重进才出现"。
    优先返回 RUNNING,其次 PENDING,最后返回最近的 ERROR(让用户看到失败状态)。
    如果没有运行中任务，还会查找最近1小时内完成的 retry 任务（供前端恢复重试状态）。
    """
    conn = get_conn()
    # 优先查找运行中的任务
    d = _fetchone(conn,
        "SELECT * FROM search_task WHERE account_id=%s AND status IN ('RUNNING','PENDING') "
        "ORDER BY (status='RUNNING') DESC, created_at DESC LIMIT 1",
        (account_id,),
    )
    # 如果没有运行中的任务，查找最近的错误任务（1小时内）
    if not d:
        d = _fetchone(conn,
            "SELECT * FROM search_task WHERE account_id=%s AND status='ERROR' "
            "AND created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR) "
            "ORDER BY created_at DESC LIMIT 1",
            (account_id,),
        )
    # 如果还没有，查找最近10分钟内完成的重试任务（用于恢复重试状态显示）
    # 注意：只返回COMPLETED状态，不返回CANCELLED（避免取消后重新显示）
    if not d:
        d = _fetchone(conn,
            "SELECT * FROM search_task WHERE account_id=%s "
            "AND status='COMPLETED' "
            "AND source IN ('retry_failed', 'retry_continue') "
            "AND created_at >= DATE_SUB(NOW(), INTERVAL 10 MINUTE) "
            "ORDER BY created_at DESC LIMIT 1",
            (account_id,),
        )
    if not d:
        return None
    total = d.get("total_queries") or 0
    completed = d.get("completed_queries") or 0
    source = d.get("source", "internal_manual")
    # 根据来源判断是否为重试任务
    retry_type = None
    if source == "retry_failed":
        retry_type = "failed"
    elif source == "retry_continue":
        retry_type = "continue"
    return {
        "taskId": d["id"],
        "status": d["status"],
        "total": total,
        "completed": completed,
        "currentKeyword": d.get("current_keyword", ""),
        "percentage": round(completed / total * 100) if total else 0,
        "errorMessage": d.get("error_message", ""),
        "createdAt": d.get("created_at", ""),
        "completedAt": d.get("completed_at", ""),
        "priority": d.get("priority", 7),
        "source": source,
        "retryType": retry_type,  # 新增：供前端恢复 retrySession
    }


def delete_failed_results_for_pairs(account_id: int, date: str, pairs: list[dict]):
    """删除指定 account+date 下失败的 keyword+model 记录，为重查腾出位置"""
    if not pairs:
        return
    conn = get_conn()
    for p in pairs:
        _exec(conn,
            "DELETE FROM search_result WHERE account_id=%s AND search_date=%s "
            "AND keyword=%s AND model=%s AND success=0",
            (account_id, date, p["keyword"], p["model"]),
        )
    conn.commit()


def get_today_platforms_for_account(account_id: int, date: str) -> set[str]:
    """返回当天某账户 search_result 中出现过的 platform 集合（用于"覆盖 vs 新建"判定）。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT DISTINCT platform FROM search_result WHERE account_id=%s AND search_date=%s",
        (account_id, date),
    )
    return {r["platform"] for r in rows if r.get("platform")}


def get_latest_today_task_id(account_id: int, date: str) -> Optional[str]:
    """找到当天某账户最近一条 search_task.id；没有则 None。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT id FROM search_task WHERE account_id=%s AND created_at LIKE %s "
        "ORDER BY created_at DESC LIMIT 1",
        (account_id, f"{date}%"),
    )
    return row["id"] if row else None


def delete_today_results_for_platforms(account_id: int, date: str, platforms: list[str]) -> int:
    """删除当天指定平台的所有查词结果，返回受影响行数。"""
    if not platforms:
        return 0
    conn = get_conn()
    placeholders = ",".join(["%s"] * len(platforms))
    sql = (
        f"DELETE FROM search_result WHERE account_id=%s AND search_date=%s "
        f"AND platform IN ({placeholders})"
    )
    with conn.cursor() as c:
        c.execute(sql, (account_id, date, *platforms))
        affected = c.rowcount
    conn.commit()
    return affected


def reset_search_task_for_rerun(task_id: str, new_total: int,
                                bump_counter: bool = True) -> None:
    """把已存在的 search_task 重置为 RUNNING，重跑同一 task_id。

    S3.1: bump_counter=False 用于调用方已通过 try_acquire_running_slot 预占槽位
    的场景（reuse 快速路径），避免 counter 双重 +2。
    """
    now = _now()
    conn = get_conn()
    # S2.3: 查 old_status，跨 RUNNING 边界时维护 Redis 计数器
    old_status = ""
    try:
        row = _fetchone(conn, "SELECT status FROM search_task WHERE id=%s", (task_id,))
        old_status = (row or {}).get("status") or ""
    except Exception:
        pass
    _exec(conn,
        "UPDATE search_task SET status=%s, total_queries=%s, completed_queries=%s, "
        "current_keyword=%s, error_message=%s, completed_at=%s, last_heartbeat=%s "
        "WHERE id=%s",
        ("RUNNING", new_total, 0, "", "", "", now, task_id),
    )
    conn.commit()
    if old_status != "RUNNING" and bump_counter:
        _redis_bump_running_counter(+1)


def get_accounts_search_summary(owner_id: int | None = None,
                                 include_external: bool = True) -> list[dict]:
    """获取账户查词汇总。
    owner_id: 按 owner 过滤（None=全部）
    include_external: 是否包含外部邀请生成的临时账号（False 时排除 [外部·...]）
    永远过滤已软删除（deleted_at IS NOT NULL）账号 — 回收站不在查词管理列表展示。
    """
    conn = get_conn()
    where, params = ["deleted_at IS NULL"], []
    if owner_id is not None:
        # 与 list_accounts 一致：主负责人(owner_id) 或 account_owner 多对多里的任一负责人都可见。
        # 修复前只匹配主 owner_id,导致仅被指派为「次负责人」的运营人看不到该客户查词结果。
        where.append("(owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao "
                     "WHERE ao.account_id=account.id AND ao.owner_user_id=%s))")
        params.append(owner_id); params.append(owner_id)
    if not include_external:
        where.append("NOT (is_temp=1 AND company_name LIKE %s)"); params.append("[外部·%")
    sql = "SELECT * FROM account WHERE " + " AND ".join(where) + " ORDER BY id DESC"
    accounts = _fetchall(conn, sql, tuple(params)) if params else _fetchall(conn, sql)
    if not accounts:
        return []

    # ── 批量聚合(修 N+1:原每账号 5 条查询、百余账号 5s+;现全列表共 5 条) ──
    aids = [a["id"] for a in accounts]
    ph = ",".join(["%s"] * len(aids))
    kw_map = {r["account_id"]: int(r["c"] or 0) for r in _fetchall(conn,
        f"SELECT account_id, COUNT(*) c FROM account_keyword "
        f"WHERE account_id IN ({ph}) GROUP BY account_id", tuple(aids))}
    dedup_map = {r["account_id"]: int(r["c"] or 0) for r in _fetchall(conn,
        f"SELECT account_id, COUNT(*) c FROM ("
        f" SELECT account_id FROM search_result WHERE account_id IN ({ph})"
        f" GROUP BY account_id, search_date, keyword, model) t GROUP BY account_id",
        tuple(aids))}
    last_search_map = {r["account_id"]: r.get("last_search") for r in _fetchall(conn,
        f"SELECT account_id, MAX(created_at) last_search FROM search_task "
        f"WHERE account_id IN ({ph}) GROUP BY account_id", tuple(aids))}
    last_task_map = {r["account_id"]: r for r in _fetchall(conn,
        f"SELECT account_id, status, total_queries, completed_queries, last_heartbeat FROM ("
        f" SELECT account_id, status, total_queries, completed_queries, last_heartbeat,"
        f"        ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY created_at DESC) rn"
        f" FROM search_task WHERE account_id IN ({ph})) t WHERE rn=1", tuple(aids))}
    today = _now()[:10]
    today_map = {r["account_id"]: r for r in _fetchall(conn,
        f"SELECT account_id, COUNT(*) cnt, SUM(ok) oks FROM ("
        f" SELECT account_id, MAX(success) ok FROM search_result"
        f" WHERE search_date=%s AND account_id IN ({ph})"
        f" GROUP BY account_id, keyword, model) t GROUP BY account_id",
        tuple([today] + aids))}

    result = []
    for acc in accounts:
        aid = acc["id"]
        kw_count = kw_map.get(aid, 0)
        total_searches = dedup_map.get(aid, 0)
        last_search = last_search_map.get(aid, "")

        # 最近一次任务状态。RUNNING 还要求心跳新鲜（≤5min），否则视为僵尸不算运行中，
        # 避免僵尸 RUNNING task 让账号永远显示"运行中/进度卡死"。
        last_task = last_task_map.get(aid)
        last_status = (last_task or {}).get("status", "")
        running = last_status == "RUNNING"
        if running:
            hb = (last_task or {}).get("last_heartbeat") or ""
            try:
                from datetime import datetime as _dt
                fresh = hb and (_dt.now() - _dt.strptime(str(hb)[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() <= 300
            except Exception:
                fresh = False
            if not fresh:
                running = False
                last_status = "STALE"
        running_total = int((last_task or {}).get("total_queries", 0) or 0)
        running_completed = int((last_task or {}).get("completed_queries", 0) or 0)
        running_progress = round(running_completed / running_total * 100) if running and running_total else 0

        # 今日查询统计：同样按 (keyword,model) 去重，任一次成功即记成功（MAX(success)）
        today_stats = today_map.get(aid)
        today_total = int((today_stats or {}).get("cnt", 0) or 0)
        today_success = int((today_stats or {}).get("oks", 0) or 0)

        platforms = acc.get("platforms") or "[]"
        if isinstance(platforms, str):
            import json as _json
            try:
                platforms = _json.loads(platforms)
            except Exception:
                platforms = [p.strip() for p in platforms.split(",") if p.strip()]

        cn = acc.get("company_name", "") or ""
        is_temp = bool(acc.get("is_temp"))
        is_external = bool(is_temp and cn.startswith("[外部·"))
        result.append({
            "id": aid,
            "accountId": aid,
            "ownerId": acc.get("owner_id"),
            "isTemp": is_temp,
            "isExternal": is_external,
            "companyName": cn,
            "companyBrand": acc.get("company_brand", ""),
            "platforms": platforms,
            "keywordCount": kw_count,
            "totalSearches": total_searches,
            "lastSearchTime": str(last_search) if last_search else "",
            "lastStatus": last_status,
            "running": running,
            "runningProgress": running_progress,
            "runningTotal": running_total if running else 0,
            "runningCompleted": running_completed if running else 0,
            "todayTotal": today_total,
            "todaySuccess": today_success,
        })
    return result


# ── 定时任务执行摘要 ──────────────────────────────────────────────────────

def get_scheduler_execution_summary(owner_id: int | None = None, team_id: int | None = None) -> list[dict]:
    """返回所有定时查词任务的最近一次执行摘要（含按模型分组统计）"""
    conn = get_conn()
    base = ("SELECT s.*, a.company_name, a.company_brand "
            "FROM scheduled_search_task s LEFT JOIN account a ON a.id = s.account_id")
    if team_id is not None:
        scheds = _fetchall(conn, base + " WHERE a.team_id=%s ORDER BY s.id", (team_id,))
    elif owner_id is not None:
        scheds = _fetchall(conn, base + " WHERE (a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao WHERE ao.account_id=a.id AND ao.owner_user_id=%s)) ORDER BY s.id", (owner_id, owner_id))
    else:
        scheds = _fetchall(conn, base + " ORDER BY s.id")

    result = []
    for s in scheds:
        sched_dict = _sched_to_dict(s)
        task_id = s.get("last_task_id")
        execution = None
        model_stats = []

        if task_id:
            # 获取查词任务信息
            task_row = _fetchone(conn,
                """SELECT id, status, created_at, completed_at,
                          total_queries, completed_queries, error_message
                   FROM search_task WHERE id=%s""",
                (task_id,),
            )
            if task_row:
                execution = {
                    "taskId": task_row["id"],
                    "status": task_row["status"],
                    "createdAt": task_row["created_at"] or "",
                    "completedAt": task_row["completed_at"] or "",
                    "totalQueries": task_row["total_queries"] or 0,
                    "completedQueries": task_row["completed_queries"] or 0,
                    "errorMessage": task_row["error_message"] or "",
                }
                # 按模型分组统计结果
                model_rows = _fetchall(conn,
                    """SELECT model,
                              COUNT(*) as total,
                              SUM(success = 1) as success_count,
                              SUM(success = 0) as fail_count
                       FROM search_result WHERE task_id=%s
                       GROUP BY model ORDER BY model""",
                    (task_id,),
                )
                for mr in model_rows:
                    model_stats.append({
                        "model": mr["model"],
                        "total": int(mr["total"] or 0),
                        "success": int(mr["success_count"] or 0),
                        "fail": int(mr["fail_count"] or 0),
                    })

        sched_dict["execution"] = execution
        sched_dict["modelStats"] = model_stats
        result.append(sched_dict)

    return result


def get_account_execution_history(account_id: int, limit: int = 10) -> list[dict]:
    """返回指定账号最近 N 次查词任务的执行记录（含模型分组统计）"""
    conn = get_conn()
    tasks = _fetchall(conn,
        """SELECT id, status, created_at, completed_at,
                  total_queries, completed_queries, error_message
           FROM search_task WHERE account_id=%s
           ORDER BY created_at DESC LIMIT %s""",
        (account_id, limit),
    )
    result = []
    for t in tasks:
        model_rows = _fetchall(conn,
            """SELECT model,
                      COUNT(*) as total,
                      SUM(success = 1) as success_count,
                      SUM(success = 0) as fail_count
               FROM search_result WHERE task_id=%s
               GROUP BY model ORDER BY model""",
            (t["id"],),
        )
        model_stats = [{
            "model": mr["model"],
            "total": int(mr["total"] or 0),
            "success": int(mr["success_count"] or 0),
            "fail": int(mr["fail_count"] or 0),
        } for mr in model_rows]

        # 入库总数
        total_in_db = sum(ms["total"] for ms in model_stats)

        result.append({
            "taskId": t["id"],
            "status": t["status"],
            "createdAt": t["created_at"] or "",
            "completedAt": t["completed_at"] or "",
            "totalQueries": t["total_queries"] or 0,
            "completedQueries": t["completed_queries"] or 0,
            "errorMessage": t["error_message"] or "",
            "modelStats": model_stats,
            "totalInDb": total_in_db,
        })

    return result


def get_account_execution_history_grouped(account_id: int, limit_dates: int = 20) -> list[dict]:
    """按 search_date 分组的执行历史。
    每个日期下的模型统计基于 search_result 去重 (keyword, model)：
      eventually_succeeded = MAX(success) — 同一天对同一关键词若任意一次成功即视为成功。
    避免"补查 / 重试"导致同关键词被多次累计。

    返回结构：
    [
      {
        "date": "2026-04-20",
        "totalQueries": 80,            # 去重后该日总查询数（按 keyword×model 计）
        "successQueries": 78,
        "failQueries": 2,
        "modelStats": [{model, total, success, fail}],
        "tasks": [                      # 当天发起的所有任务，用于下钻
          {taskId, status, createdAt, completedAt, totalQueries, completedQueries, errorMessage}
        ]
      }
    ]
    """
    conn = get_conn()

    # Step 1: 按 (date, model) 聚合去重统计
    rows = _fetchall(conn,
        """SELECT search_date, model,
                  COUNT(*) AS uniq_total,
                  SUM(eventually_succeeded) AS success_count
           FROM (
               SELECT search_date, keyword, model, MAX(success) AS eventually_succeeded
               FROM search_result
               WHERE account_id=%s
               GROUP BY search_date, keyword, model
           ) t
           GROUP BY search_date, model
           ORDER BY search_date DESC""",
        (account_id,),
    )

    by_date = {}
    for r in rows:
        d = r["search_date"]
        if not d:
            continue
        if d not in by_date:
            by_date[d] = {"date": d, "modelStats": []}
        total = int(r["uniq_total"] or 0)
        succ = int(r["success_count"] or 0)
        by_date[d]["modelStats"].append({
            "model": r["model"],
            "total": total,
            "success": succ,
            "fail": total - succ,
        })

    sorted_dates = sorted(by_date.keys(), reverse=True)[:limit_dates]

    # Step 2: 拉取每个日期下的任务列表（用于下钻 / 状态判定）
    result = []
    from geo_common import date_range as _dr
    for d in sorted_dates:
        d0, d1 = _dr(d)
        tasks = _fetchall(conn,
            """SELECT id, status, created_at, completed_at,
                      total_queries, completed_queries, error_message, last_heartbeat
               FROM search_task
               WHERE account_id=%s AND created_at >= %s AND created_at < %s
               ORDER BY created_at ASC""",
            (account_id, d0, d1),
        )
        # B4: RUNNING 但心跳过期(>5min)的视为僵尸，对外按 ERROR 呈现，
        # 与查词管理列表页 P5 判活口径一致，避免某天因僵尸 task 永远显示"进行中"。
        from datetime import datetime as _dt4
        def _eff_status(t):
            st = t["status"]
            if st != "RUNNING":
                return st
            hb = t.get("last_heartbeat") or ""
            try:
                if hb and (_dt4.now() - _dt4.strptime(str(hb)[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() <= 300:
                    return "RUNNING"
            except Exception:
                pass
            return "ERROR"
        # 过滤"零工作量幽灵任务":total=0 且 done=0 且非进行中。
        # 典型来源:enqueue 入队瞬间(total 还没算)被截图、或被取代的空任务。
        # 这类行在执行历史里没有任何信息量,只会把窗口撑长。
        def _is_ghost(t):
            tot = int(t.get("total_queries") or 0)
            done = int(t.get("completed_queries") or 0)
            st = _eff_status(t)
            return tot == 0 and done == 0 and st not in ("RUNNING", "PENDING")
        task_list = [{
            "taskId": t["id"],
            "status": _eff_status(t),
            "createdAt": t["created_at"] or "",
            "completedAt": t["completed_at"] or "",
            "totalQueries": t["total_queries"] or 0,
            "completedQueries": t["completed_queries"] or 0,
            "errorMessage": t["error_message"] or "",
        } for t in tasks if not _is_ghost(t)]

        d_entry = by_date[d]
        d_entry["modelStats"].sort(key=lambda m: m["model"])
        agg_total = sum(m["total"] for m in d_entry["modelStats"])
        agg_succ = sum(m["success"] for m in d_entry["modelStats"])
        agg_fail = sum(m["fail"] for m in d_entry["modelStats"])

        # 状态：当天有 RUNNING -> RUNNING；全部 CANCELLED -> CANCELLED；
        # 有 ERROR 但有 COMPLETED -> COMPLETED（最终成功）；否则按是否有 ERROR 判断
        statuses = [t["status"] for t in task_list]
        if any(s == "RUNNING" for s in statuses):
            day_status = "RUNNING"
        elif statuses and all(s == "CANCELLED" for s in statuses):
            day_status = "CANCELLED"
        elif any(s == "COMPLETED" for s in statuses):
            day_status = "COMPLETED"
        elif any(s == "ERROR" for s in statuses):
            day_status = "ERROR"
        else:
            day_status = statuses[0] if statuses else "COMPLETED"

        first_at = task_list[0]["createdAt"] if task_list else ""
        last_at = task_list[-1]["completedAt"] or task_list[-1]["createdAt"] if task_list else ""
        err_msg = next((t["errorMessage"] for t in task_list if t["errorMessage"]), "")

        # Step1 已按 (date,keyword,model) GROUP BY + MAX(success) 完成去重，
        # agg_total/agg_succ 即"当天去重后实查/成功条数"，本身稳定准确。
        # 旧 Step2 拿 task.total_queries 当 target 做 min/max/按比例砍 modelStats 的
        # 夹逼，反而引入随 task 状态跳变 + 篡改单模型真实成败。全部移除，直接用去重值。
        # 修复 2026-05-21:agg_total 只统计已写入 search_result 的 pair。如果某些
        # (kw,model) 因 worker 异常完全没 emit progress 就崩了,这部分被漏算 →
        # UI 出现 "74/74 全部成功"但实际 task.totalQueries=80 的怪相。
        # 改取 max(agg_total, max_task_total) 让 target 至少 ≥ task 应跑数。
        max_task_total = max((t["totalQueries"] for t in task_list), default=0)
        target_queries = max(agg_total, max_task_total)  # 应查 = 至少要跑这么多
        agg_total_disp = agg_total
        agg_succ_disp = agg_succ
        agg_fail_disp = max(0, agg_total - agg_succ)
        pending = max(0, agg_total - agg_succ)   # 未成功条数

        result.append({
            "date": d,
            "targetQueries": target_queries,
            "totalQueries": agg_total_disp,
            "successQueries": agg_succ_disp,
            "failQueries": agg_fail_disp,
            "pendingQueries": pending,
            "modelStats": d_entry["modelStats"],
            "tasks": task_list,
            "status": day_status,
            "firstAt": first_at,
            "lastAt": last_at,
            "errorMessage": err_msg,
        })

    return result


# ═══════════��═════════════��═════════════════
# Citation Scrape Task (持久化抓取任务)
# ═══════════════��═══════════════════════════

def _ensure_scrape_task_tables():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS citation_scrape_task (
            id VARCHAR(64) PRIMARY KEY,
            account_id BIGINT NOT NULL,
            search_date VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            total INT DEFAULT 0,
            done INT DEFAULT 0,
            success_count INT DEFAULT 0,
            fail_count INT DEFAULT 0,
            current_url VARCHAR(500) DEFAULT '',
            error_message TEXT,
            started_at VARCHAR(30),
            finished_at VARCHAR(30),
            last_heartbeat VARCHAR(30),
            INDEX idx_cst_account (account_id),
            INDEX idx_cst_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cur.execute("""CREATE TABLE IF NOT EXISTS citation_scrape_event (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL,
            url VARCHAR(1000),
            title VARCHAR(500),
            site_name VARCHAR(255),
            ok TINYINT(1) DEFAULT 1,
            duration_sec FLOAT,
            error_msg TEXT,
            created_at VARCHAR(30),
            INDEX idx_cse_task (task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    conn.commit()

try:
    _ensure_scrape_task_tables()
except Exception:
    pass


# ═══════════════════════════════════════════
# 客户已发布内容链接（用于"发布内容被 AI 引用"追踪）
# 本次手动录入(source=manual);后续接内容发布模块自动登记(source=system)
# ═══════════════════════════════════════════

def _ensure_published_url_table():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS client_published_url (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account_id BIGINT NOT NULL,
            url VARCHAR(1000) NOT NULL,
            url_norm VARCHAR(500) NOT NULL,
            title VARCHAR(500) DEFAULT '',
            publish_date VARCHAR(20) DEFAULT '',
            source VARCHAR(20) NOT NULL DEFAULT 'manual',
            created_at VARCHAR(30),
            UNIQUE KEY uq_cpu_acc_norm (account_id, url_norm),
            INDEX idx_cpu_account (account_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    conn.commit()

try:
    _ensure_published_url_table()
except Exception:
    pass


def _norm_published_url(u: str) -> str:
    """URL 严格归一化(去 scheme/www/query/fragment/末尾斜杠),作为发布链接的去重键 + 主匹配键。
    跨 http/https、www、query、末尾斜杠 已天然一致(只取 host+path)。"""
    s = (u or "").strip()
    try:
        p = urlsplit(s)
        host = (p.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = (p.path or "").rstrip("/")
        return f"{host}{path}" if host else s.lower()
    except Exception:
        return s.lower()


# 注册域提取用的二级公共后缀(.com.cn / .gov.cn 等取后三段)
_CN_SECOND_LEVEL = {"com", "net", "org", "gov", "edu", "ac"}


def _registrable_domain(host: str) -> str:
    """提取注册域(eTLD+1),把 www/m/news/page 等子域归并到同一站点。
    例: m.toutiao.com→toutiao.com, news.xnnews.com.cn→xnnews.com.cn。"""
    h = (host or "").lower().split(":")[0].strip(".")
    if not h:
        return ""
    labels = h.split(".")
    if len(labels) <= 2:
        return h
    if labels[-1] == "cn" and labels[-2] in _CN_SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _url_strong_id(path: str) -> str:
    """从路径里抽"强唯一 ID":末段(去扩展名)若是 ≥10 位的纯字母数字串则返回它,否则空。

    用于补匹配同一篇文章在不同子域(www/m)、不同路径别名下的情况——
    典型如今日头条 /article/<id> = /item/<id> = m.../group/<id>,唯一稳定的是这个长 ID。
    要求"整段 ≥10 位纯字母数字"是为了避免 552.htm 这类短名跨文章误配
    (长 ID 在同一注册域内事实上全局唯一)。"""
    segs = [s for s in (path or "").split("/") if s]
    if not segs:
        return ""
    base = segs[-1].rsplit(".", 1)[0]   # 去扩展名
    if re.fullmatch(r"[A-Za-z0-9]{10,}", base):
        return base
    return ""


def _url_match_keys(u: str) -> set:
    """一个 URL 的匹配键集合,任一键与对方相同即视为同一篇内容。
      key1 = 严格归一化(host去www + path)——精确,无误配。
      key2 = 'id|<注册域>|<强ID>'——补抓子域/路径别名变体,仅当能抽到强 ID 时生成。
    """
    keys = {_norm_published_url(u)}
    try:
        p = urlsplit((u or "").strip())
        regdom = _registrable_domain(p.netloc or "")
        sid = _url_strong_id(unquote(p.path or ""))
        if regdom and sid:
            keys.add(f"id|{regdom}|{sid}")
    except Exception:
        pass
    return keys


def add_client_published_urls(account_id: int, urls: list[str], source: str = "manual",
                              titles: Optional[dict] = None) -> dict:
    """批量登记客户已发布链接(归一化去重,UNIQUE 幂等)。返回 {added, skipped, total_input}。"""
    now = _now()
    added = 0
    skipped = 0
    titles = titles or {}
    with transaction() as conn:
        for u in urls:
            u = (u or "").strip()
            if not u.lower().startswith("http"):
                skipped += 1
                continue
            n = _norm_published_url(u)
            cur = _exec(conn,
                """INSERT INTO client_published_url
                   (account_id, url, url_norm, title, publish_date, source, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE url=VALUES(url),
                       title=IF(VALUES(title)<>'', VALUES(title), title)""",
                (account_id, u, n, titles.get(u, ""), "", source, now))
            if cur.rowcount == 1:   # 1=新插入, 2=命中重复更新
                added += 1
            else:
                skipped += 1
    return {"added": added, "skipped": skipped, "total_input": len(urls)}


def get_client_published_urls(account_id: int) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, url, url_norm, title, publish_date, source, created_at "
        "FROM client_published_url WHERE account_id=%s ORDER BY id DESC",
        (account_id,))
    return [dict(r) for r in rows]


def count_client_published_urls(account_id: int) -> int:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS c FROM client_published_url WHERE account_id=%s", (account_id,))
    return int((row or {}).get("c") or 0)


def get_published_citation_hits(account_id: int, dates: list[str],
                                pub_account_id: int | None = None) -> dict:
    """匹配某账号「已发布链接」与给定日期内查词的 AI 信源引用,返回命中明细。

    pub_account_id:已发布链接的来源账号(默认=account_id)。用于"发布集中在老账号、
    新账号查词"的拆分客户场景——URL 取 pub_account_id(老账号),查词引用仍取 account_id
    (新账号自己的查词),从而在新账号周报里体现"新账号查词引用到了老账号发布的内容"。

    归一化后匹配(去 scheme/www/query)。返回:
      {published_total, hit_count, citation_times, prompt_count,
       hits: [{url, title, times, model_counts:{model:n}, prompts:[..], prompt_count, date_count}]}
    平台标签映射交给调用方(weekly_reporter)做,这里只返回原始 model code。
    """
    pubs = get_client_published_urls(pub_account_id or account_id)
    # 每条发布链接以其 url_norm 作为命中桶 id;同时登记它的所有匹配键 → 桶 id
    pub_bucket: dict[str, dict] = {}   # url_norm -> {url,title}
    key_to_bucket: dict[str, str] = {}  # match_key -> url_norm
    for p in pubs:
        bucket_id = p["url_norm"]
        pub_bucket.setdefault(bucket_id, {"url": p["url"], "title": p.get("title") or ""})
        for k in _url_match_keys(p["url"]):
            key_to_bucket.setdefault(k, bucket_id)
    published_total = len(pub_bucket)

    hits: dict[str, dict] = {}
    citation_times = 0
    for d in (dates or []):
        for c in get_citation_urls(account_id, d):
            # 用引用 URL 的键集合去命中发布桶(主键严格 + 子域/路径别名补键)
            bucket_id = None
            for k in _url_match_keys(c["url"]):
                if k in key_to_bucket:
                    bucket_id = key_to_bucket[k]
                    break
            if bucket_id is None:
                continue
            h = hits.setdefault(bucket_id, {
                "url": pub_bucket[bucket_id]["url"], "title": pub_bucket[bucket_id]["title"],
                "times": 0, "model_counts": {}, "prompts": set(), "dates": set(),
            })
            h["times"] += 1
            citation_times += 1
            m = c.get("model") or ""
            if m:
                h["model_counts"][m] = h["model_counts"].get(m, 0) + 1
            if c.get("keyword"):
                h["prompts"].add(c["keyword"])
            h["dates"].add(d)

    all_prompts: set[str] = set()
    hit_list: list[dict] = []
    for h in hits.values():
        all_prompts |= h["prompts"]
        hdates = sorted(h["dates"])
        hit_list.append({
            "url": h["url"], "title": h["title"], "times": h["times"],
            "model_counts": h["model_counts"],
            "prompts": sorted(h["prompts"]),
            "prompt_count": len(h["prompts"]),
            "date_count": len(hdates),
            "first_cite_date": hdates[0] if hdates else "",
            "dates": hdates,
        })
    hit_list.sort(key=lambda x: (-x["times"], -x["prompt_count"]))
    return {
        "published_total": published_total,
        "hit_count": len(hit_list),
        "citation_times": citation_times,
        "prompt_count": len(all_prompts),
        "hits": hit_list,
    }


def create_citation_scrape_task(task_id, account_id, search_date, total):
    now = _now()
    conn = get_conn()
    _exec(conn,
        """INSERT INTO citation_scrape_task
           (id, account_id, search_date, status, total, done, success_count, fail_count,
            current_url, started_at, last_heartbeat)
           VALUES (%s,%s,%s,%s,%s,0,0,0,%s,%s,%s)""",
        (task_id, account_id, search_date, "running", total, "", now, now))
    conn.commit()


def update_citation_scrape_progress(task_id, done, success, failed, current_url=""):
    now = _now()
    conn = get_conn()
    _exec(conn,
        """UPDATE citation_scrape_task
           SET done=%s, success_count=%s, fail_count=%s, current_url=%s, last_heartbeat=%s
           WHERE id=%s""",
        (done, success, failed, current_url, now, task_id))
    conn.commit()


def finish_citation_scrape_task(task_id, status, success=0, failed=0, error_msg=""):
    now = _now()
    conn = get_conn()
    _exec(conn,
        """UPDATE citation_scrape_task
           SET status=%s, success_count=%s, fail_count=%s, finished_at=%s, last_heartbeat=%s,
               error_message=%s, current_url=%s
           WHERE id=%s""",
        (status, success, failed, now, now, error_msg, "", task_id))
    conn.commit()


def get_citation_scrape_task(task_id):
    conn = get_conn()
    row = _fetchone(conn, "SELECT * FROM citation_scrape_task WHERE id=%s", (task_id,))
    return _citation_task_to_dict(row) if row else None


def get_running_citation_scrape_tasks():
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM citation_scrape_task WHERE status=%s ORDER BY started_at DESC",
        ("running",))
    return [_citation_task_to_dict(r) for r in rows]


def get_running_citation_scrape_by_account(account_id):
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT * FROM citation_scrape_task WHERE account_id=%s AND status=%s ORDER BY started_at DESC LIMIT 1",
        (account_id, "running"))
    return _citation_task_to_dict(row) if row else None


def add_citation_scrape_event(task_id, url, title, site_name, ok, duration_sec=0, error_msg=""):
    now = _now()
    conn = get_conn()
    cur = _exec(conn,
        """INSERT INTO citation_scrape_event
           (task_id, url, title, site_name, ok, duration_sec, error_msg, created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (task_id, url, title or "", site_name or "", 1 if ok else 0, duration_sec, error_msg, now))
    conn.commit()
    return cur.lastrowid


def get_citation_scrape_events(task_id, after_id=0):
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT * FROM citation_scrape_event WHERE task_id=%s AND id>%s ORDER BY id",
        (task_id, after_id))
    return [_citation_event_to_dict(r) for r in rows]


def cleanup_stale_citation_tasks(max_age_seconds=300):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    cur = _exec(conn,
        """UPDATE citation_scrape_task SET status=%s, error_message=%s, finished_at=%s
           WHERE status=%s AND last_heartbeat < %s""",
        ("error", "task timeout", _now(), "running", cutoff))
    conn.commit()
    return cur.rowcount


def _citation_task_to_dict(row):
    if not row:
        return {}
    d = dict(row)
    return {
        "taskId": d["id"],
        "accountId": d["account_id"],
        "searchDate": d["search_date"],
        "status": d["status"],
        "total": d.get("total", 0),
        "done": d.get("done", 0),
        "success": d.get("success_count", 0),
        "failed": d.get("fail_count", 0),
        "currentUrl": d.get("current_url", ""),
        "errorMessage": d.get("error_message", ""),
        "startedAt": d.get("started_at", ""),
        "finishedAt": d.get("finished_at", ""),
        "lastHeartbeat": d.get("last_heartbeat", ""),
    }


def _citation_event_to_dict(row):
    d = dict(row)
    return {
        "id": d["id"],
        "taskId": d["task_id"],
        "url": d.get("url", ""),
        "title": d.get("title", ""),
        "siteName": d.get("site_name", ""),
        "ok": bool(d.get("ok", 1)),
        "durationSec": d.get("duration_sec", 0),
        "errorMsg": d.get("error_msg", ""),
        "createdAt": d.get("created_at", ""),
    }


def list_quote_tasks_paginated(
    page: int = 1,
    page_size: int = 20,
    account_id: int | None = None,
    status: str | None = None,
    stage: str | None = None,
    search: str | None = None,
    sort_by: str = 'created_at',
    sort_order: str = 'desc'
) -> dict:
    """分页、筛选、排序的任务列表"""
    conn = get_conn()
    cursor = conn.cursor()

    # 构建查询条件
    where_clauses = []
    params = []

    if account_id:
        where_clauses.append("account_id = %s")
        params.append(account_id)

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    if stage:
        where_clauses.append("stage = %s")
        params.append(stage)

    if search:
        where_clauses.append("(id LIKE %s OR error_message LIKE %s)")
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # 计算总数
    count_sql = f"SELECT COUNT(*) as total FROM quote_task WHERE {where_sql}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()["total"]

    # 排序字段验证
    allowed_sort_fields = ['id', 'created_at', 'status', 'stage', 'account_id']
    if sort_by not in allowed_sort_fields:
        sort_by = 'created_at'

    sort_order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'

    # 分页查询
    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT * FROM quote_task
        WHERE {where_sql}
        ORDER BY {sort_by} {sort_order}
        LIMIT %s OFFSET %s
    """
    cursor.execute(query_sql, params + [page_size, offset])
    tasks = cursor.fetchall()

    return {
        "tasks": tasks,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }


def list_quote_results_paginated(
    run_id: int,
    page: int = 1,
    page_size: int = 50,
    extract_status: str | None = None,
    scrape_status: str | None = None
) -> dict:
    """分页的查询结果列表"""
    conn = get_conn()
    cursor = conn.cursor()

    where_clauses = ["query_run_id = %s"]
    params = [run_id]

    if extract_status:
        where_clauses.append("extract_status = %s")
        params.append(extract_status)

    if scrape_status:
        where_clauses.append("scrape_status = %s")
        params.append(scrape_status)

    where_sql = " AND ".join(where_clauses)

    # 计算总数
    count_sql = f"SELECT COUNT(*) as total FROM quote_result WHERE {where_sql}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()["total"]

    # 分页查询
    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT * FROM quote_result
        WHERE {where_sql}
        ORDER BY id
        LIMIT %s OFFSET %s
    """
    cursor.execute(query_sql, params + [page_size, offset])
    results = cursor.fetchall()

    return {
        "results": results,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }



# 报价任务阶段信息
QUOTE_STAGE_INFO = {
    "pending": {
        "icon": "⏳",
        "title": "等待开始",
        "description": "任务已创建，等待执行",
        "color": "#9e9e9e"
    },
    "searching": {
        "icon": "🔍",
        "title": "查词搜索",
        "description": "正在使用AI搜索引擎查找相关内容",
        "tips": "搜索质量直接影响报价准确度",
        "avg_time": "2-3分钟",
        "color": "#2196f3"
    },
    "scraping": {
        "icon": "🌐",
        "title": "抓取网页",
        "description": "正在抓取搜索结果的完整网页内容",
        "tips": "抓取失败的网页会自动跳过",
        "avg_time": "3-5分钟",
        "color": "#ff9800"
    },
    "extracting": {
        "icon": "📝",
        "title": "提取分析",
        "description": "正在提取网页关键信息并评估相关性",
        "tips": "AI会自动过滤无关内容",
        "avg_time": "2-4分钟",
        "color": "#9c27b0"
    },
    "scoring": {
        "icon": "⭐",
        "title": "评分报价",
        "description": "正在计算五维评分并生成最终报价",
        "tips": "评分维度：D1-D5",
        "avg_time": "10-30秒",
        "color": "#4caf50"
    },
    "completed": {
        "icon": "✅",
        "title": "已完成",
        "description": "任务执行成功",
        "color": "#4caf50"
    },
    "error": {
        "icon": "❌",
        "title": "执行失败",
        "description": "任务执行过程中遇到错误",
        "color": "#f44336"
    },
    "cancelled": {
        "icon": "⏸",
        "title": "已取消",
        "description": "任务已被用户取消",
        "color": "#757575"
    }
}

def get_stage_info(stage: str) -> dict:
    """获取阶段详细信息"""
    return QUOTE_STAGE_INFO.get(stage, {
        "icon": "❓",
        "title": "未知阶段",
        "description": "",
        "color": "#9e9e9e"
    })


# ═══════════════════════════════════════════
# Weekly Report (周报)
# ═══════════════════════════════════════════

def create_weekly_report(account_id: int, period_start: str, period_end: str,
                         report_type: str = "weekly",
                         selected_modules: Optional[list] = None,
                         include_brand_words: bool = True) -> int:
    """创建一行 pending 状态的 weekly_report 并返回 id.
    selected_modules: None → 字段保留 NULL（语义为全选）；list → 存 JSON。
    include_brand_words: False → 生成时所有统计剔除品牌词(提示词含本品牌名)。
    """
    import json as _json
    from datetime import datetime as _dt_wr, timedelta as _td_wr
    now = _now()
    rt = (report_type or "weekly").strip() or "weekly"
    sel = _json.dumps(list(selected_modules), ensure_ascii=False) if selected_modules is not None else None
    # 报告默认 30 天有效期(外部 pipeline 设 share_token 时也用 30 天,与此对齐)
    default_exp = (_dt_wr.now() + _td_wr(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO weekly_report
               (account_id, period_start, period_end, status, report_type, selected_modules,
                include_brand_words, token_expires_at, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (account_id, period_start, period_end, "pending", rt, sel,
             1 if include_brand_words else 0, default_exp, now),
        )
        return cur.lastrowid


def update_weekly_report_status(report_id: int, **kwargs) -> None:
    allowed = ("status", "html_content", "data_snapshot_json",
               "ai_insights_json", "resource_checklist_json",
               "error_message", "completed_at",
               "progress_message", "progress_percent",
               "period_start", "period_end", "selected_modules")
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            # progress_message 是 VARCHAR(255):brand_reporter 偶发写超长进度文案会触发
            # 1406 Data too long,直接让报告生成抛异常卡在 running。防御性截断(与 5640 行同口径)。
            if k == "progress_message" and isinstance(v, str) and len(v) > 250:
                v = v[:247] + "..."
            sets.append(f"{k}=%s")
            vals.append(v)
    if kwargs.get("status") == "completed" and "completed_at" not in kwargs:
        sets.append("completed_at=%s")
        vals.append(_now())
    if not sets:
        return
    vals.append(report_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE weekly_report SET {', '.join(sets)} WHERE id=%s", tuple(vals))


def _weekly_report_to_dict(row, include_html: bool = False) -> dict:
    if not row:
        return {}
    out = {
        "id": row["id"],
        "accountId": row.get("account_id"),
        "periodStart": row.get("period_start"),
        "periodEnd": row.get("period_end"),
        "status": row.get("status"),
        "reportType": row.get("report_type") or "weekly",
        "errorMessage": row.get("error_message") or "",
        "progressMessage": row.get("progress_message") or "",
        "progressPercent": int(row.get("progress_percent") or 0),
        "createdAt": str(row["created_at"]) if row.get("created_at") else "",
        "completedAt": str(row["completed_at"]) if row.get("completed_at") else "",
    }
    if "include_brand_words" in row:
        out["includeBrandWords"] = bool(row.get("include_brand_words", 1))
    if "selected_modules" in row:
        sm = row.get("selected_modules")
        if sm:
            try:
                import json as _json
                out["selectedModules"] = _json.loads(sm) if isinstance(sm, str) else list(sm)
            except Exception:
                out["selectedModules"] = None
        else:
            out["selectedModules"] = None
    if "data_snapshot_json" in row:
        out["dataSnapshotJson"] = row.get("data_snapshot_json") or ""
    if "ai_insights_json" in row:
        out["aiInsightsJson"] = row.get("ai_insights_json") or ""
    if include_html:
        out["htmlContent"] = row.get("html_content") or ""
    return out


def get_weekly_report(report_id: int, include_html: bool = False) -> Optional[dict]:
    conn = get_conn()
    cols = "id, account_id, period_start, period_end, status, report_type, " \
           "selected_modules, include_brand_words, " \
           "data_snapshot_json, ai_insights_json, error_message, " \
           "progress_message, progress_percent, " \
           "created_at, completed_at"
    if include_html:
        cols += ", html_content"
    row = _fetchone(conn, f"SELECT {cols} FROM weekly_report WHERE id=%s", (report_id,))
    return _weekly_report_to_dict(row, include_html=include_html) if row else None


def list_weekly_reports_by_account(account_id: int, limit: int = 30) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT id, account_id, period_start, period_end, status, report_type,
                  selected_modules,
                  error_message, progress_message, progress_percent,
                  created_at, completed_at
           FROM weekly_report WHERE account_id=%s
           ORDER BY id DESC LIMIT %s""",
        (account_id, int(limit)),
    )
    return [_weekly_report_to_dict(r) for r in rows]


def delete_weekly_report(report_id: int) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM weekly_report WHERE id=%s", (report_id,))


# ── 分享密钥 ──────────────────────────────────────────────────────────────

def regenerate_share_token(account_id: int) -> str:
    """给账号生成新的 share_token（32 字节 hex）并写入，返回新 token."""
    import secrets
    token = secrets.token_hex(24)
    with transaction() as conn:
        _exec(conn, "UPDATE account SET share_token=%s WHERE id=%s", (token, account_id))
    return token


def get_share_token(account_id: int) -> str:
    conn = get_conn()
    row = _fetchone(conn, "SELECT share_token FROM account WHERE id=%s", (account_id,))
    return (row or {}).get("share_token") or ""


def verify_share_token(account_id: int, token: str) -> bool:
    if not token:
        return False
    conn = get_conn()
    row = _fetchone(conn, "SELECT 1 FROM account WHERE id=%s AND share_token=%s",
                    (account_id, token))
    return bool(row)


# ── 按报告分享密钥 ─────────────────────────────────────────────────────────

def regenerate_weekly_report_share_token(report_id: int) -> str:
    """给单个周报生成/重置 share_token，返回新 token."""
    import secrets
    token = secrets.token_hex(24)
    with transaction() as conn:
        _exec(conn, "UPDATE weekly_report SET share_token=%s WHERE id=%s", (token, report_id))
    return token


def get_weekly_report_share_token(report_id: int) -> str:
    conn = get_conn()
    row = _fetchone(conn, "SELECT share_token FROM weekly_report WHERE id=%s", (report_id,))
    return (row or {}).get("share_token") or ""


def verify_weekly_report_share_token(report_id: int, token: str) -> bool:
    if not token:
        return False
    conn = get_conn()
    row = _fetchone(conn, "SELECT 1 FROM weekly_report WHERE id=%s AND share_token=%s",
                    (report_id, token))
    return bool(row)


def get_weekly_report_brief(report_id: int) -> dict:
    """返回周报基本信息（含 account_id/period_start/period_end/status），用于分享页面."""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT id, account_id, period_start, period_end, status, report_type FROM weekly_report WHERE id=%s",
        (report_id,))
    return dict(row) if row else {}


# ── 周报定时调度 ──────────────────────────────────────────────────────────

def _sched_weekly_to_dict(row) -> dict:
    if not row:
        return {}
    last_task_id = row.get("last_task_id", "") or ""
    execution_running = False
    if last_task_id:
        try:
            conn = get_conn()
            trow = _fetchone(conn,
                "SELECT status FROM weekly_report WHERE id=%s", (int(last_task_id),))
            if trow and str(trow.get("status") or "").lower() in ("running", "pending"):
                execution_running = True
        except Exception:
            pass
    return {
        "id": row["id"],
        "accountId": row["account_id"],
        "name": row.get("name", "") or "",
        "companyName": row.get("company_name", "") or "",
        "companyBrand": row.get("company_brand", "") or "",
        "reportType": row.get("report_type") or "weekly",
        "frequency": row.get("frequency", "weekly"),
        "runTime": row.get("run_time", "01:00"),
        "dayOfWeek": row.get("day_of_week", 0),
        "dayOfMonth": row.get("day_of_month", -1),
        "enabled": bool(row.get("enabled", 0)),
        "nextRunAt": str(row["next_run_at"]) if row.get("next_run_at") else None,
        "lastRunAt": str(row["last_run_at"]) if row.get("last_run_at") else None,
        "lastTaskId": last_task_id,
        "lastStatus": row.get("last_status", "") or "",
        "manualTriggerPending": bool(row.get("manual_trigger_pending", 0)),
        "executionRunning": execution_running,
    }


def create_weekly_schedule(data: dict) -> dict:
    now = _now()
    frequency = data.get("frequency") or "weekly"
    run_time = data.get("runTime") or "01:00"
    day_of_week = int(data.get("dayOfWeek") if data.get("dayOfWeek") is not None else 0)
    day_of_month = int(data.get("dayOfMonth") if data.get("dayOfMonth") is not None else -1)
    report_type = (data.get("reportType") or data.get("report_type") or "weekly").strip() or "weekly"
    next_run = compute_next_run(frequency, run_time, day_of_week, day_of_month)
    with transaction() as conn:
        cur = _exec(conn,
            """INSERT INTO scheduled_weekly_report_task
               (account_id, name, report_type, frequency, run_time, day_of_week, day_of_month,
                enabled, next_run_at, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (int(data["accountId"]), data.get("name") or "", report_type, frequency, run_time,
             day_of_week, day_of_month, 1 if data.get("enabled", True) else 0,
             next_run, now),
        )
        new_id = cur.lastrowid
    return get_weekly_schedule(new_id)


def get_weekly_schedule(sched_id: int) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_weekly_report_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE s.id=%s""", (sched_id,)
    )
    return _sched_weekly_to_dict(row) if row else None


def list_weekly_schedules() -> list:
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_weekly_report_task s LEFT JOIN account a ON a.id = s.account_id
           ORDER BY s.id DESC"""
    )
    return [_sched_weekly_to_dict(r) for r in rows]


def get_weekly_schedule_by_account(account_id: int) -> Optional[dict]:
    conn = get_conn()
    row = _fetchone(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_weekly_report_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE s.account_id=%s ORDER BY s.id DESC LIMIT 1""", (account_id,)
    )
    return _sched_weekly_to_dict(row) if row else None


def update_weekly_schedule(sched_id: int, data: dict) -> dict:
    parts, vals = [], []
    if "name" in data: parts.append("name=%s"); vals.append(data["name"] or "")
    if "reportType" in data or "report_type" in data:
        rt_val = (data.get("reportType") or data.get("report_type") or "weekly").strip() or "weekly"
        parts.append("report_type=%s"); vals.append(rt_val)
    if "enabled" in data: parts.append("enabled=%s"); vals.append(1 if data["enabled"] else 0)
    freq = data.get("frequency")
    if freq: parts.append("frequency=%s"); vals.append(freq)
    rt = data.get("runTime")
    if rt: parts.append("run_time=%s"); vals.append(rt)
    if "dayOfWeek" in data: parts.append("day_of_week=%s"); vals.append(int(data["dayOfWeek"]))
    if "dayOfMonth" in data: parts.append("day_of_month=%s"); vals.append(int(data["dayOfMonth"]))
    # 任何配置变动都重算 next_run_at
    cur_row = _fetchone(get_conn(),
        "SELECT frequency, run_time, day_of_week, day_of_month FROM scheduled_weekly_report_task WHERE id=%s",
        (sched_id,))
    if cur_row:
        new_freq = freq or cur_row["frequency"]
        new_rt = rt or cur_row["run_time"]
        new_dow = int(data.get("dayOfWeek", cur_row["day_of_week"] or 0))
        new_dom = int(data.get("dayOfMonth", cur_row["day_of_month"] if cur_row["day_of_month"] is not None else -1))
        parts.append("next_run_at=%s")
        vals.append(compute_next_run(new_freq, new_rt, new_dow, new_dom))
    if parts:
        vals.append(sched_id)
        with transaction() as conn:
            _exec(conn, f"UPDATE scheduled_weekly_report_task SET {', '.join(parts)} WHERE id=%s", tuple(vals))
    return get_weekly_schedule(sched_id)


def delete_weekly_schedule(sched_id: int) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM scheduled_weekly_report_task WHERE id=%s", (sched_id,))


def trigger_weekly_schedule(sched_id: int) -> None:
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_weekly_report_task SET manual_trigger_pending=1 WHERE id=%s",
            (sched_id,))


def clear_weekly_schedule_trigger(sched_id: int) -> None:
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_weekly_report_task SET manual_trigger_pending=0 WHERE id=%s",
            (sched_id,))


def list_due_weekly_schedules() -> list[dict]:
    from datetime import datetime as _dt
    now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    rows = _fetchall(conn,
        """SELECT s.*, a.company_name, a.company_brand
           FROM scheduled_weekly_report_task s LEFT JOIN account a ON a.id = s.account_id
           WHERE (s.enabled = 1 AND s.next_run_at IS NOT NULL AND s.next_run_at <= %s)
              OR s.manual_trigger_pending = 1
           ORDER BY s.manual_trigger_pending DESC, s.next_run_at ASC""",
        (now_str,)
    )
    return [_sched_weekly_to_dict(r) for r in rows]


def advance_weekly_schedule_next_run(sched_id: int) -> None:
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT frequency, run_time, day_of_week, day_of_month FROM scheduled_weekly_report_task WHERE id=%s",
        (sched_id,))
    if not row:
        return
    next_run = compute_next_run(
        row["frequency"], row["run_time"],
        int(row["day_of_week"] or 0),
        int(row["day_of_month"] if row["day_of_month"] is not None else -1),
    )
    with transaction() as conn2:
        _exec(conn2,
            "UPDATE scheduled_weekly_report_task SET next_run_at=%s WHERE id=%s",
            (next_run, sched_id))


def update_weekly_schedule_last_run(sched_id: int, task_id: str, status: str) -> None:
    with transaction() as conn:
        _exec(conn,
            "UPDATE scheduled_weekly_report_task SET last_task_id=%s, last_status=%s, last_run_at=%s WHERE id=%s",
            (str(task_id or ""), (status or "")[:32], _now(), sched_id))


# ════════════════════════════════════════════════════════════
# content_analysis(生文分析结果,单客户单份覆盖式)
# ════════════════════════════════════════════════════════════

def get_content_analysis(account_id: int) -> Optional[dict]:
    """取该客户最新一份生文分析(单客户单份)。返回 dict 或 None。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT id, account_id, brand_name, source_search_date, source_kb_version, "
        "       status, progress_percent, progress_message, error_message, "
        "       analysis_json, prompt_brief_json, facts_json, analysis_md, "
        "       source_insight_json, source_insight_status, "
        "       report_json, ranking_task_id, "
        "       generated_at, updated_at "
        "FROM content_analysis WHERE account_id=%s",
        (account_id,))
    return dict(row) if row else None


def upsert_content_analysis(account_id: int, **fields) -> None:
    """插入或全量覆盖式更新该客户的生文分析。
    支持字段:brand_name, source_search_date, source_kb_version, status,
            progress_percent, progress_message, error_message,
            analysis_json, prompt_brief_json, facts_json, analysis_md。
    会自动更新 updated_at;status='completed' 时同步 generated_at。"""
    now = _now()
    fields = {k: v for k, v in fields.items() if v is not None}
    fields["updated_at"] = now
    if fields.get("status") == "completed":
        fields["generated_at"] = now
    cols = list(fields.keys())
    vals = [fields[c] for c in cols]

    with transaction() as conn:
        existing = _fetchone(conn, "SELECT id FROM content_analysis WHERE account_id=%s", (account_id,))
        if existing:
            set_clause = ", ".join(f"{c}=%s" for c in cols)
            _exec(conn,
                  f"UPDATE content_analysis SET {set_clause} WHERE account_id=%s",
                  tuple(vals + [account_id]))
        else:
            col_list = ", ".join(["account_id"] + cols)
            placeholders = ", ".join(["%s"] * (len(cols) + 1))
            _exec(conn,
                  f"INSERT INTO content_analysis ({col_list}) VALUES ({placeholders})",
                  tuple([account_id] + vals))


def update_content_analysis_status(account_id: int, status: str,
                                   progress_percent: int | None = None,
                                   progress_message: str | None = None,
                                   error_message: str | None = None) -> None:
    """只更新状态/进度,不动 JSON 字段(异步生成过程中频繁调用)。"""
    parts = ["status=%s", "updated_at=%s"]
    args: list = [status, _now()]
    if progress_percent is not None:
        parts.append("progress_percent=%s"); args.append(int(progress_percent))
    if progress_message is not None:
        parts.append("progress_message=%s"); args.append((progress_message or "")[:240])
    if error_message is not None:
        parts.append("error_message=%s"); args.append(error_message[:1500] if error_message else None)
    args.append(account_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE content_analysis SET {', '.join(parts)} WHERE account_id=%s", tuple(args))


def list_content_analyses_brief(account_ids: list[int]) -> dict:
    """批量取 N 个客户的分析摘要(列表页徽章渲染用,只返回轻量字段)。返回 {account_id: brief}。"""
    if not account_ids:
        return {}
    conn = get_conn()
    placeholders = ",".join(["%s"] * len(account_ids))
    rows = _fetchall(conn,
        f"SELECT account_id, status, source_search_date, generated_at, updated_at "
        f"FROM content_analysis WHERE account_id IN ({placeholders})",
        tuple(account_ids))
    return {int(r["account_id"]): dict(r) for r in rows}


# ════════════════════════════════════════════════════════════
# 信源深度分析:引用源原文 + 单篇分析缓存(content_analysis_article)
# ════════════════════════════════════════════════════════════

def _url_hash(url: str) -> str:
    import hashlib
    return hashlib.sha1((url or "").encode("utf-8")).hexdigest()


def upsert_article_stub(account_id: int, url: str, *, title: str = "", footer: str = "",
                        source_search_date: str = "", cite_count: int = 1,
                        cited_keywords_json: str | None = None) -> None:
    """登记一个待抓取的引用源(已存在则累加引用次数、更新元信息,不动已抓正文)。"""
    uh = _url_hash(url)
    with transaction() as conn:
        existing = _fetchone(conn,
            "SELECT id, cite_count FROM content_analysis_article WHERE account_id=%s AND url_hash=%s",
            (account_id, uh))
        if existing:
            _exec(conn,
                "UPDATE content_analysis_article SET cite_count=%s, title=COALESCE(NULLIF(title,''),%s), "
                "footer=COALESCE(NULLIF(footer,''),%s), source_search_date=%s, cited_keywords=%s "
                "WHERE id=%s",
                (int(cite_count), title, footer, source_search_date,
                 cited_keywords_json, existing["id"]))
        else:
            _exec(conn,
                "INSERT INTO content_analysis_article "
                "(account_id, url, url_hash, title, footer, source_search_date, cite_count, cited_keywords) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (account_id, url[:1000], uh, title, footer, source_search_date,
                 int(cite_count), cited_keywords_json))


def list_articles_to_scrape(account_id: int, max_age_days: int = 7, limit: int = 200) -> list[dict]:
    """取待抓取/过期需重抓的引用源(pending 或 fetched_at 超过 max_age_days)。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, url, url_hash, title, footer FROM content_analysis_article "
        "WHERE account_id=%s AND ("
        "  scrape_status='pending' "
        "  OR (scrape_status<>'ok' ) "
        "  OR fetched_at IS NULL "
        "  OR fetched_at < DATE_SUB(NOW(), INTERVAL %s DAY)"
        ") ORDER BY cite_count DESC, id ASC LIMIT %s",
        (account_id, int(max_age_days), int(limit)))
    return [dict(r) for r in rows]


def update_article_scrape(article_id: int, *, scrape_status: str,
                          markdown_content: str | None = None,
                          clean_content: str | None = None,
                          website_type: str | None = None,
                          content_type: str | None = None,
                          pub_date: str | None = None) -> None:
    parts = ["scrape_status=%s", "fetched_at=%s"]
    args: list = [scrape_status, _now()]
    for col, val in (("markdown_content", markdown_content), ("clean_content", clean_content),
                     ("website_type", website_type), ("content_type", content_type),
                     ("pub_date", pub_date)):
        if val is not None:
            parts.append(f"{col}=%s"); args.append(val)
    args.append(article_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE content_analysis_article SET {', '.join(parts)} WHERE id=%s", tuple(args))


def list_articles_for_analysis(account_id: int, limit: int = 200) -> list[dict]:
    """取已抓到正文、待单篇分析的文章。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, url, title, footer, clean_content, markdown_content, website_type "
        "FROM content_analysis_article "
        "WHERE account_id=%s AND scrape_status='ok' AND analysis_status='pending' "
        "AND (CHAR_LENGTH(COALESCE(clean_content,''))>120 OR CHAR_LENGTH(COALESCE(markdown_content,''))>120) "
        "ORDER BY cite_count DESC, id ASC LIMIT %s",
        (account_id, int(limit)))
    return [dict(r) for r in rows]


def update_article_analysis(article_id: int, *, analysis_status: str,
                            analysis_json: str | None = None) -> None:
    with transaction() as conn:
        _exec(conn,
            "UPDATE content_analysis_article SET analysis_status=%s, analysis_json=%s, analyzed_at=%s WHERE id=%s",
            (analysis_status, analysis_json, _now(), article_id))


def get_analyzed_articles(account_id: int, limit: int = 300) -> list[dict]:
    """取该客户已完成单篇分析的文章(供综合洞察 + 前端展示)。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, url, title, footer, website_type, analysis_json "
        "FROM content_analysis_article "
        "WHERE account_id=%s AND analysis_status='ok' ORDER BY cite_count DESC, id ASC LIMIT %s",
        (account_id, int(limit)))
    return [dict(r) for r in rows]


def article_scrape_stats(account_id: int) -> dict:
    """抓取/分析进度统计(前端进度条)。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT COUNT(*) AS total, "
        "SUM(scrape_status='ok') AS scraped, "
        "SUM(analysis_status='ok') AS analyzed "
        "FROM content_analysis_article WHERE account_id=%s",
        (account_id,))
    return {"total": int((row or {}).get("total") or 0),
            "scraped": int((row or {}).get("scraped") or 0),
            "analyzed": int((row or {}).get("analyzed") or 0)}


# ════════════════════════════════════════════════════════════
# 客户发稿要求 + 写作心得(供生文 prompt 注入)
# ════════════════════════════════════════════════════════════

def get_writing_requirements(account_id: int) -> Optional[str]:
    conn = get_conn()
    row = _fetchone(conn, "SELECT writing_requirements FROM account WHERE id=%s", (account_id,))
    return (row or {}).get("writingRequirements") or (row or {}).get("writing_requirements")


def update_writing_requirements(account_id: int, raw_json: str) -> None:
    with transaction() as conn:
        _exec(conn, "UPDATE account SET writing_requirements=%s, updated_at=%s WHERE id=%s",
              (raw_json, _now(), account_id))


def list_writing_lessons(account_id: int, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, account_id, scene, lesson_text, source_article_id, created_by, created_at, updated_at "
        "FROM account_writing_lesson WHERE account_id=%s ORDER BY id DESC LIMIT %s",
        (account_id, int(limit)))
    return [dict(r) for r in rows]


def create_writing_lesson(account_id: int, scene: str, lesson_text: str,
                          source_article_id: int | None = None,
                          created_by: int | None = None) -> int:
    now = _now()
    with transaction() as conn:
        _exec(conn,
            "INSERT INTO account_writing_lesson (account_id, scene, lesson_text, source_article_id, created_by, created_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (account_id, (scene or "")[:120], lesson_text, source_article_id, created_by, now, now))
        row = _fetchone(conn, "SELECT LAST_INSERT_ID() AS id")
        return int((row or {}).get("id") or 0)


def update_writing_lesson(lesson_id: int, *, scene: str | None = None,
                          lesson_text: str | None = None) -> None:
    parts, args = [], []
    if scene is not None:
        parts.append("scene=%s"); args.append((scene or "")[:120])
    if lesson_text is not None:
        parts.append("lesson_text=%s"); args.append(lesson_text)
    if not parts:
        return
    parts.append("updated_at=%s"); args.append(_now())
    args.append(lesson_id)
    with transaction() as conn:
        _exec(conn, f"UPDATE account_writing_lesson SET {', '.join(parts)} WHERE id=%s", tuple(args))


def delete_writing_lesson(lesson_id: int) -> None:
    with transaction() as conn:
        _exec(conn, "DELETE FROM account_writing_lesson WHERE id=%s", (lesson_id,))


# ════════════════════════════════════════════════════════════
# 排名分析(ranking_task / ranking_result)查询(供 V2 生文分析使用)
# ════════════════════════════════════════════════════════════

def get_ranking_task_by_search(search_task_id: str) -> Optional[dict]:
    """按 search_task_id (account_<id>_<date>) 取最新排名任务。"""
    conn = get_conn()
    row = _fetchone(conn,
        "SELECT * FROM ranking_task WHERE search_task_id=%s ORDER BY created_at DESC LIMIT 1",
        (search_task_id,))
    return dict(row) if row else None


def list_ranking_results(ranking_task_id: str) -> list[dict]:
    """取某次排名任务的全部 ranking_result(keyword × model)。"""
    conn = get_conn()
    rows = _fetchall(conn,
        "SELECT id, ranking_task_id, keyword, model, brand_rank, brand_frequency, "
        "       total_brands, all_brands_json, skipped "
        "FROM ranking_result WHERE ranking_task_id=%s ORDER BY id",
        (ranking_task_id,))
    return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════
# 排名分析聚合查询(供 rank-tool API 使用)
# ════════════════════════════════════════════════════════════

def get_ranking_task_list_with_stats(owner_id: int | None = None,
                                      team_id: int | None = None,
                                      include_temp: bool = False,
                                      limit: int = 500) -> list[dict]:
    """排名分析主列表：按 account 聚合，每行一个客户。

    返回前端期望的结构:
      [{id, customerName, type, brands[], analysisCount, resultCount,
        rankingRate, top3Rate, status, lastAnalysisTime}]
    """
    conn = get_conn()
    # 基础条件
    where_parts = ["a.deleted_at IS NULL"]
    params: list = []
    if not include_temp:
        where_parts.append("(a.is_temp IS NULL OR a.is_temp=0)")
    if team_id is not None:
        where_parts.append("a.team_id=%s")
        params.append(team_id)
    elif owner_id is not None:
        where_parts.append(
            "(a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao "
            "WHERE ao.account_id=a.id AND ao.owner_user_id=%s))")
        params.append(owner_id)
        params.append(owner_id)
    where_sql = " AND ".join(where_parts)

    # 查询每个 account 的排名任务汇总
    rows = _fetchall(conn,
        f"""SELECT a.id, a.company_name, a.company_brand, a.user_type, a.is_temp,
                  a.status AS account_status,
                  (SELECT COUNT(*) FROM ranking_task rt2 WHERE rt2.account_id=a.id) AS analysis_count,
                  (SELECT COUNT(*) FROM ranking_result rr2
                   JOIN ranking_task rt3 ON rr2.ranking_task_id=rt3.id
                   WHERE rt3.account_id=a.id) AS result_count,
                  (SELECT MAX(rt4.created_at) FROM ranking_task rt4 WHERE rt4.account_id=a.id) AS last_analysis_time,
                  (SELECT rt5.status FROM ranking_task rt5 WHERE rt5.account_id=a.id
                   ORDER BY rt5.created_at DESC LIMIT 1) AS last_status,
                  (SELECT rt6.brand_name FROM ranking_task rt6 WHERE rt6.account_id=a.id
                   ORDER BY rt6.created_at DESC LIMIT 1) AS last_brand_name,
                  (SELECT SUM(CASE WHEN rr.brand_rank IS NOT NULL AND rr.brand_rank>0 THEN 1 ELSE 0 END)
                   FROM ranking_result rr
                   JOIN ranking_task rt7 ON rr.ranking_task_id=rt7.id
                   WHERE rt7.account_id=a.id) AS ranked_count,
                  (SELECT SUM(CASE WHEN rr.brand_rank IS NOT NULL AND rr.brand_rank<=3 AND rr.brand_rank>0 THEN 1 ELSE 0 END)
                   FROM ranking_result rr
                   JOIN ranking_task rt8 ON rr.ranking_task_id=rt8.id
                   WHERE rt8.account_id=a.id) AS top3_count
           FROM account a
           WHERE {where_sql}
           HAVING analysis_count > 0 OR last_status IS NOT NULL
           ORDER BY last_analysis_time DESC
           LIMIT %s""",
        params + [limit])

    out = []
    for r in rows:
        result_count = int(r.get("result_count") or 0)
        ranked_count = int(r.get("ranked_count") or 0)
        top3_count = int(r.get("top3_count") or 0)
        ranking_rate = round(ranked_count * 100 / result_count) if result_count > 0 else 0
        top3_rate = round(top3_count * 100 / result_count) if result_count > 0 else 0
        last_status = r.get("last_status") or "done"
        # 映射状态: running→running, completed→done, failed→error, pending→pending
        status_map = {"running": "running", "completed": "done",
                      "failed": "error", "pending": "pending", "": "done"}
        status = status_map.get(last_status, "done")
        # 解析品牌名
        brands = _parse_brand_list(r.get("last_brand_name") or "")
        out.append({
            "id": r["id"],
            "customerName": r.get("company_name") or "",
            "type": "temp" if r.get("is_temp") else "paid",
            "brands": brands,
            "analysisCount": int(r.get("analysis_count") or 0),
            "resultCount": result_count,
            "rankingRate": ranking_rate,
            "top3Rate": top3_rate,
            "status": status,
            "lastAnalysisTime": r.get("last_analysis_time") or "",
        })
    return out


def get_ranking_keyword_data(account_id: int, date: str = "") -> list[dict]:
    """获取某客户的关键词排名明细，按 keyword 聚合多平台。

    返回前端期望的结构:
      [{id, keyword, type, model, bestRank, engines[{name, rank}], snippet}]
    """
    conn = get_conn()
    if date:
        rows = _fetchall(conn,
            """SELECT sr.id, sr.keyword, sr.platform, sr.model, sr.brand_rank,
                      sr.answer_text, sr.intent_prompt, sr.search_date
               FROM search_result sr
               INNER JOIN (SELECT MAX(id) as max_id FROM search_result
                           WHERE account_id=%s AND search_date=%s AND success=1
                           GROUP BY keyword, model) t
               ON sr.id = t.max_id
               ORDER BY sr.keyword""",
            (account_id, date))
    else:
        rows = _fetchall(conn,
            """SELECT sr.id, sr.keyword, sr.platform, sr.model, sr.brand_rank,
                      sr.answer_text, sr.intent_prompt, sr.search_date
               FROM search_result sr
               INNER JOIN (SELECT MAX(id) as max_id FROM search_result
                           WHERE account_id=%s AND success=1
                           GROUP BY keyword, model, search_date) t
               ON sr.id = t.max_id
               ORDER BY sr.keyword DESC LIMIT 500""",
            (account_id,))

    if not rows:
        return []

    # 获取该客户的品牌名用于判断通用词/品牌词
    acc = get_account(account_id)
    brand_name = (acc or {}).get("companyBrand") or ""
    brand_aliases = _brand_aliases_lower(_parse_brand_list(brand_name))

    # 按 keyword 聚合
    kw_map: dict = {}
    for r in rows:
        kw = r.get("keyword") or ""
        if kw not in kw_map:
            kw_lower = kw.lower()
            is_brand = any(a and a in kw_lower for a in brand_aliases)
            kw_map[kw] = {
                "id": r["id"],
                "keyword": kw,
                "type": "品牌词" if is_brand else "通用词",
                "model": r.get("platform") or r.get("model") or "",
                "bestRank": None,
                "engines": [],
                "snippet": "",
                "_ranks": [],
            }
        entry = kw_map[kw]
        rank = r.get("brand_rank")
        platform_name = r.get("platform") or r.get("model") or ""
        entry["engines"].append({"name": platform_name, "rank": rank})
        if rank and isinstance(rank, int) and rank > 0:
            entry["_ranks"].append(rank)

    # 计算 bestRank 和 snippet
    for entry in kw_map.values():
        ranks = entry.pop("_ranks", [])
        if ranks:
            entry["bestRank"] = min(ranks)
        # snippet: 从 answer_text 截取前 200 字
        # (实际应截取品牌上下文，但 answer_text 在 light 查询中未取)
        # 这里用 intent_prompt 作为 snippet 兜底
        entry["snippet"] = entry.get("snippet") or ""

    return list(kw_map.values())


def get_ranking_history_list(account_id: int | None = None,
                             owner_id: int | None = None,
                             team_id: int | None = None,
                             limit: int = 100) -> list[dict]:
    """排名分析历史列表。

    返回前端期望的结构:
      [{id, createdAt, queryTime, brands[], totalCount, progress, status}]
    """
    conn = get_conn()
    where_parts = []
    params: list = []
    if account_id is not None:
        where_parts.append("rt.account_id=%s")
        params.append(account_id)
    if team_id is not None:
        where_parts.append("a.team_id=%s")
        params.append(team_id)
    elif owner_id is not None:
        where_parts.append(
            "(a.owner_id=%s OR EXISTS (SELECT 1 FROM account_owner ao "
            "WHERE ao.account_id=a.id AND ao.owner_user_id=%s))")
        params.append(owner_id)
        params.append(owner_id)
    where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    rows = _fetchall(conn,
        f"""SELECT rt.id, rt.search_task_id, rt.account_id, rt.brand_name,
                  rt.status, rt.total, rt.done, rt.skipped, rt.hit,
                  rt.created_at, a.company_name
           FROM ranking_task rt
           LEFT JOIN account a ON rt.account_id=a.id
           {where_sql}
           ORDER BY rt.created_at DESC
           LIMIT %s""",
        params + [limit])

    out = []
    for r in rows:
        total = int(r.get("total") or 0)
        done = int(r.get("done") or 0)
        progress = round(done * 100 / total) if total > 0 else 0
        status_map = {"completed": "完成", "running": "进行中",
                      "failed": "异常", "pending": "等待中"}
        out.append({
            "id": r["id"],
            "createdAt": r.get("created_at") or "",
            "queryTime": _extract_search_date(r.get("search_task_id") or ""),
            "brands": _parse_brand_list(r.get("brand_name") or ""),
            "totalCount": total,
            "progress": progress,
            "status": status_map.get(r.get("status"), r.get("status") or ""),
            "customerName": r.get("company_name") or "",
            "accountId": r.get("account_id"),
        })
    return out


def get_ranking_detail_by_account(account_id: int) -> dict:
    """获取某客户的排名分析详情汇总。

    返回:
      {customerName, brands[], analysisCount, resultCount,
       rankingRate, top3Rate, status, lastAnalysisTime,
       keywordData[], historyData[]}
    """
    conn = get_conn()
    # 取客户信息
    acc = get_account(account_id)
    if not acc:
        return {}

    # 取最近一次排名任务
    rt = _fetchone(conn,
        "SELECT * FROM ranking_task WHERE account_id=%s ORDER BY created_at DESC LIMIT 1",
        (account_id,))

    # 统计
    stats = _fetchone(conn,
        """SELECT COUNT(*) as total_results,
                  SUM(CASE WHEN brand_rank IS NOT NULL AND brand_rank>0 THEN 1 ELSE 0 END) as ranked,
                  SUM(CASE WHEN brand_rank IS NOT NULL AND brand_rank<=3 AND brand_rank>0 THEN 1 ELSE 0 END) as top3
           FROM ranking_result rr
           JOIN ranking_task rt ON rr.ranking_task_id=rt.id
           WHERE rt.account_id=%s""",
        (account_id,))

    total_results = int((stats or {}).get("total_results") or 0)
    ranked = int((stats or {}).get("ranked") or 0)
    top3 = int((stats or {}).get("top3") or 0)

    # 关键词数据
    search_date = _extract_search_date((rt or {}).get("search_task_id") or "")
    keyword_data = get_ranking_keyword_data(account_id, search_date)

    # 历史数据
    history_data = get_ranking_history_list(account_id=account_id, limit=50)

    brands = _parse_brand_list((rt or {}).get("brand_name") or "")
    last_status = (rt or {}).get("status") or "completed"
    status_map = {"running": "running", "completed": "done",
                  "failed": "error", "pending": "pending"}
    analysis_count = _fetchone(conn,
        "SELECT COUNT(*) as cnt FROM ranking_task WHERE account_id=%s",
        (account_id,))
    analysis_count = int((analysis_count or {}).get("cnt") or 0)

    return {
        "id": account_id,
        "customerName": acc.get("companyName") or "",
        "type": "temp" if acc.get("isTemp") else "paid",
        "brands": brands,
        "analysisCount": analysis_count,
        "resultCount": total_results,
        "rankingRate": round(ranked * 100 / total_results) if total_results > 0 else 0,
        "top3Rate": round(top3 * 100 / total_results) if total_results > 0 else 0,
        "status": status_map.get(last_status, "done"),
        "lastAnalysisTime": (rt or {}).get("created_at") or "",
        "keywordData": keyword_data,
        "historyData": history_data,
    }


def get_ranking_account_summary(account_id: int) -> dict:
    """获取某客户的排名分析汇总（用于列表行）。"""
    conn = get_conn()
    acc = get_account(account_id)
    if not acc:
        return {}

    rt = _fetchone(conn,
        "SELECT * FROM ranking_task WHERE account_id=%s ORDER BY created_at DESC LIMIT 1",
        (account_id,))

    stats = _fetchone(conn,
        """SELECT COUNT(*) as total_results,
                  SUM(CASE WHEN brand_rank IS NOT NULL AND brand_rank>0 THEN 1 ELSE 0 END) as ranked,
                  SUM(CASE WHEN brand_rank IS NOT NULL AND brand_rank<=3 AND brand_rank>0 THEN 1 ELSE 0 END) as top3
           FROM ranking_result rr
           JOIN ranking_task rt ON rr.ranking_task_id=rt.id
           WHERE rt.account_id=%s""",
        (account_id,))

    total_results = int((stats or {}).get("total_results") or 0)
    ranked = int((stats or {}).get("ranked") or 0)
    top3 = int((stats or {}).get("top3") or 0)
    analysis_count = _fetchone(conn,
        "SELECT COUNT(*) as cnt FROM ranking_task WHERE account_id=%s",
        (account_id,))
    analysis_count = int((analysis_count or {}).get("cnt") or 0)

    brands = _parse_brand_list((rt or {}).get("brand_name") or "")
    last_status = (rt or {}).get("status") or "completed"
    status_map = {"running": "running", "completed": "done",
                  "failed": "error", "pending": "pending"}

    return {
        "id": account_id,
        "customerName": acc.get("companyName") or "",
        "type": "temp" if acc.get("isTemp") else "paid",
        "brands": brands,
        "analysisCount": analysis_count,
        "resultCount": total_results,
        "rankingRate": round(ranked * 100 / total_results) if total_results > 0 else 0,
        "top3Rate": round(top3 * 100 / total_results) if total_results > 0 else 0,
        "status": status_map.get(last_status, "done"),
        "lastAnalysisTime": (rt or {}).get("created_at") or "",
    }
