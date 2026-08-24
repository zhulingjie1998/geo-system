"""
scheduled_task_scheduler.py — 定时任务调度守护进程

职责：
  - 后台线程每分钟检查一次是否有到期的定时任务
  - 到期任务自动触发查词操作
  - 更新任务的 next_run_at 和 last_run_at

入口：
  - start_scheduler() : 启动后台调度线程（在 dev_server.py 或 app.py 中调用）
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import db

logger = logging.getLogger("scheduler")

# 全局控制标志
_scheduler_running = False
_scheduler_thread = None

# 调度间隔（秒）
TICK_INTERVAL = 30  # 每30秒检查一次


def _should_run_task(task: dict) -> bool:
    """判断任务是否应该执行"""
    if not task.get("enabled"):
        return False
    
    next_run = task.get("next_run_at")
    if not next_run:
        return False
    
    try:
        # 解析 next_run_at (格式: "MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM:SS")
        if len(next_run) > 12:
            # 完整时间格式
            next_time = datetime.strptime(next_run, "%Y-%m-%d %H:%M:%S")
        else:
            # 短格式，需要加上年份
            year = datetime.now().year
            next_time = datetime.strptime(f"{year}-{next_run}", "%Y-%m-%d %H:%M")
        
        return datetime.now() >= next_time
    except Exception as e:
        logger.warning("解析 next_run_at 失败: %s, error: %s", next_run, e)
        return False


def _execute_scheduled_search(task: dict) -> bool:
    """执行定时查词任务"""
    # _sched_to_dict 返回 camelCase 字段
    account_id = task.get("accountId") or task.get("account_id")
    task_id = task.get("id")
    
    if not account_id:
        logger.error("任务 %s 缺少 account_id (accountId)", task_id)
        return False
    
    try:
        # 解析 models
        models = task.get("models", [])
        if isinstance(models, str):
            import json
            try:
                models = json.loads(models)
            except:
                models = []
        
        if not models:
            logger.warning("任务 %s 没有配置平台模型", task_id)
            return False
        
        # 获取客户的关键词
        conn = db.get_conn()
        keywords_row = db._fetchall(
            conn,
            "SELECT intent_prompt, id, intent_category, core_intent_word FROM account_keyword WHERE account_id=%s ORDER BY sort_order ASC",
            (account_id,)
        )
        
        keywords = []
        if keywords_row:
            for kw in keywords_row:
                prompt = kw.get("intent_prompt") or ""
                if prompt:
                    keywords.append({
                        "id": kw.get("id"),
                        "prompt": prompt,
                        "category": kw.get("intent_category", ""),
                        "core": kw.get("core_intent_word", ""),
                    })
        
        if not keywords:
            logger.warning("客户 %s 没有关键词，跳过定时查词", account_id)
            return False
        
        # 导入并调用搜索适配器
        from overseas_search_adapter import start_search_for_account_async
        
        logger.info("[定时任务] 执行任务 #%s: 客户=%s, 平台=%s, 关键词数=%d",
                     task_id, account_id, models, len(keywords))
        
        task_info = start_search_for_account_async(
            account_id,
            override_models=models,
            override_keywords=keywords,
        )
        
        # 保存taskId到任务记录
        actual_task_id = task_info.get("taskId", "")
        if actual_task_id:
            db._exec(
                db.get_conn(),
                "UPDATE scheduled_search_task SET last_task_id=%s WHERE id=%s",
                (actual_task_id, task_id)
            )
            logger.info("[定时任务] 任务 #%s 已提交: taskId=%s", task_id, actual_task_id)
        
        return True
        
    except Exception as e:
        logger.error("[定时任务] 任务 #%s 执行失败: %s", task_id, e, exc_info=True)
        return False


def _update_task_after_run(task_id: int, success: bool):
    """任务执行后更新状态"""
    import os
    try:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        status = "COMPLETED" if success else "FAILED"
        
        log_msg = f"[定时任务] _update_task_after_run 开始: task_id={task_id}, status={status}, time={now_str}"
        print(log_msg)
        with open(os.path.join(os.path.dirname(__file__), '_debug.log'), 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
        
        # 获取任务信息用于记录历史
        task = db.get_scheduled_search_task(task_id)
        if not task:
            return
        
        logger.info("[定时任务] _update_task_after_run 开始: task_id=%s, status=%s, time=%s", task_id, status, now_str)
            
        # 【防重复】检查最近60秒内是否已有手动触发的历史记录
        recent_manual = db._fetchone(
            db.get_conn(),
            """SELECT id, trigger_type, created_at FROM scheduled_task_history 
               WHERE sched_id=%s 
               AND created_at >= DATE_SUB(%s, INTERVAL 120 SECOND)
               ORDER BY id DESC LIMIT 3""",
            (task_id, now_str)
        )
        log_msg2 = f"[定时任务] 防重复查询结果: {recent_manual}"
        print(log_msg2)
        with open(os.path.join(os.path.dirname(__file__), '_debug.log'), 'a', encoding='utf-8') as f:
            f.write(log_msg2 + '\n')
        logger.info("[定时任务] 防重复查询结果: %s", recent_manual)
        
        # 【关键修复】如果最近120秒内有**任何**记录，直接返回不执行
        if recent_manual:
            skip_msg = f"[定时任务] 任务 #{task_id} 最近有记录(#{recent_manual.get('id')} type={recent_manual.get('trigger_type')})，完全跳过"
            print(skip_msg)
            logger.info(skip_msg)
            return  # 直接返回，不做任何事情
            
        account_id = task.get("accountId") or 0
        is_manual = bool(task.get("manualTriggerPending") or task.get("manual_trigger_pending"))
        trigger_type = "manual" if is_manual else "scheduled"
        
        # 使用已保存的taskId
        actual_task_id = task.get("lastTaskId", "") or task.get("last_task_id", "") or ""
        
        # 【修复】获取任务的开始时间用于计算真实耗时
        started_at_str = now_str  # 默认使用当前时间
        duration = 0
        
        if actual_task_id:
            # 从 search_task 表获取实际开始和结束时间
            search_task = db._fetchone(
                db.get_conn(),
                """SELECT created_at, completed_at, status FROM search_task WHERE id=%s LIMIT 1""",
                (actual_task_id,)
            )
            if search_task:
                created = search_task.get("created_at") or ""
                completed = search_task.get("completed_at") or ""
                if created:
                    started_at_str = str(created)[:19]  # 截取日期时间部分
                if created and completed:
                    try:
                        start_dt = datetime.strptime(str(created)[:19], "%Y-%m-%d %H:%M:%S")
                        end_dt = datetime.strptime(str(completed)[:19], "%Y-%m-%d %H:%M:%S")
                        duration = int((end_dt - start_dt).total_seconds())
                    except:
                        duration = 0
        
        # 更新 last_run_at, last_status
        db._exec(
            db.get_conn(),
            "UPDATE scheduled_search_task SET last_run_at=%s, last_status=%s, manual_trigger_pending=0 WHERE id=%s",
            (now_str, status, task_id)
        )
        
        # 记录执行历史（统一入口，避免重复）
        try:
            detail = None
            if is_manual:
                detail = f"用户手动触发，已创建查词任务 {actual_task_id}" if actual_task_id else "用户手动触发"
            
            # 【最终防重复】直接执行INSERT前先检查
            _sched_recent = db._fetchone(
                db.get_conn(),
                """SELECT id, trigger_type FROM scheduled_task_history 
                   WHERE sched_id=%s AND created_at >= DATE_SUB(%s, INTERVAL 120 SECOND)
                   ORDER BY id DESC LIMIT 1""",
                (task_id, now_str)
            )
            
            skip_insert = False
            if _sched_recent:
                _skip_log = f"[定时任务-最终防重复] 命中! 已有id={_sched_recent.get('id')} type={_sched_recent.get('trigger_type')}, 当前type={trigger_type}"
                print(_skip_log)
                logger.info(_skip_log)
                
                # 如果已有manual记录，跳过scheduled
                if _sched_recent.get('trigger_type') == 'manual' and trigger_type == 'scheduled':
                    skip_insert = True
                    logger.info("[定时任务] 跳过scheduled插入(已有manual记录)")
                # 如果类型完全相同，也跳过
                elif _sched_recent.get('trigger_type') == trigger_type:
                    skip_insert = True
                    logger.info("[定时任务] 跳过插入(同类型记录已存在)")
            
            # 【关键修复】调度器不再创建历史记录，只由 API 创建
            # 这样可以彻底避免重复
            logger.info("[定时任务] 任务 #%s 跳过历史创建(由API负责)", task_id)
        except Exception as hist_err:
            logger.warning("[定时任务] 记录历史失败: %s", hist_err)
        
        # 计算下一次执行时间
        task = db.get_scheduled_search_task(task_id)
        if task:
            # 【防重复】如果 next_run_at 已经是明天（API设置的），不要重置
            current_next = task.get("nextRunAt") or task.get("next_run_at") or ""
            if current_next:
                try:
                    from datetime import timedelta
                    now_dt = datetime.now()
                    next_dt = datetime.strptime(str(current_next)[:19], "%Y-%m-%d %H:%M:%S")
                    # 如果 next_run_at 是今天之后（至少6小时后），说明是API设置的，不重置
                    if (next_dt - now_dt) > timedelta(hours=6):
                        logger.info("[定时任务] 任务 #%s next_run_at=%s (API设置的)，保持不变", 
                                   task_id, current_next)
                        return  # 提前返回，不重置 next_run_at
                except Exception:
                    pass
            
            # _sched_to_dict 返回 camelCase 字段
            frequency = task.get("frequency", "daily")
            run_time = task.get("runTime") or task.get("run_time", "02:00")
            day_of_week = task.get("dayOfWeek") or task.get("day_of_week", 6)
            day_of_month = task.get("dayOfMonth") or task.get("day_of_month", 1)
            
            next_run = db.compute_next_run(frequency, run_time, day_of_week, day_of_month)
            
            db._exec(
                db.get_conn(),
                "UPDATE scheduled_search_task SET next_run_at=%s WHERE id=%s",
                (next_run, task_id)
            )
            
            logger.info("[定时任务] 任务 #%s 下次执行: %s", task_id, next_run)
            
    except Exception as e:
        logger.error("[定时任务] 更新任务 #%s 状态失败: %s", task_id, e)


def _scheduler_loop():
    """调度主循环"""
    global _scheduler_running
    logger.info("[调度器] 启动，间隔=%d秒", TICK_INTERVAL)
    
    while _scheduler_running:
        try:
            _tick()
        except Exception as e:
            logger.error("[调度器] tick 异常: %s", e, exc_info=True)
        
        # 分段 sleep，便于快速退出
        for _ in range(TICK_INTERVAL):
            if not _scheduler_running:
                break
            time.sleep(1)
    
    logger.info("[调度器] 已停止")


def _tick():
    """每 tick 执行一次：检查并执行到期任务"""
    try:
        # 使用 db 模块已有的函数获取到期任务
        due_tasks = db.list_due_scheduled_tasks()
        
        if not due_tasks:
            return
        
        # 【调试】打印所有到期任务的详细信息
        for dt in due_tasks:
            logger.info("[调度器-tick] 到期任务: id=%s name=%s nextRunAt=%s manualPending=%s execLock=%s",
                       dt.get("id"), 
                       dt.get("name") or dt.get("company_name"),
                       dt.get("nextRunAt"),
                       dt.get("manualTriggerPending"),
                       dt.get("executionLock"))
        
        for task in due_tasks:
            if not _scheduler_running:
                break
                
            task_id = task.get("id")
            
            # 【防重复0】二次验证：重新从数据库读取最新状态
            fresh_task = db._fetchone(db.get_conn(),
                """SELECT id, execution_lock, next_run_at, manual_trigger_pending 
                   FROM scheduled_search_task WHERE id=%s""",
                (task_id,))
            
            if not fresh_task:
                continue
                
            # 【关键】检查 next_run_at 是否真的到期（防止读到过期缓存）
            fresh_next_run = fresh_task.get("next_run_at") or ""
            if fresh_next_run:
                try:
                    from datetime import timedelta
                    next_dt = datetime.strptime(str(fresh_next_run)[:19], "%Y-%m-%d %H:%M:%S")
                    if next_dt > datetime.now() + timedelta(minutes=5):
                        logger.info("[调度器] 任务 #%s next_run_at=%s 未到期(二次验证)，跳过", 
                                   task_id, fresh_next_run)
                        continue
                except Exception:
                    pass
            
            # 【防重复1】检查 execution_lock（使用最新数据）
            existing_lock = fresh_task.get("execution_lock") or ""
            if existing_lock:
                # 【关键】检查锁的年龄 - 如果锁超过5分钟，视为已过期
                # 锁格式: api_HHMMSS 或 sched_HHMMSS
                try:
                    lock_time_str = existing_lock.split("_", 1)[1] if "_" in existing_lock else ""
                    if lock_time_str and len(lock_time_str) == 6:
                        lock_hour = int(lock_time_str[0:2])
                        lock_min = int(lock_time_str[2:4])
                        lock_sec = int(lock_time_str[4:6])
                        now_dt = datetime.now()
                        lock_dt = now_dt.replace(hour=lock_hour, minute=lock_min, second=lock_sec, microsecond=0)
                        
                        # 如果锁时间是未来的（跨天情况），减去一天
                        if lock_dt > now_dt:
                            from datetime import timedelta
                            lock_dt -= timedelta(days=1)
                        
                        lock_age = (now_dt - lock_dt).total_seconds()
                        if lock_age < 300:  # 5分钟内有效
                            logger.info("[调度器] 任务 #%s 已被锁定(%s, %.0f秒前)，跳过", 
                                       task_id, existing_lock, lock_age)
                            continue
                        else:
                            logger.info("[调度器] 任务 #%s 锁已过期(%.0f秒)，继续执行", 
                                       task_id, lock_age)
                    else:
                        logger.info("[调度器] 任务 #%s 有未知格式的锁(%s)，跳过", 
                                   task_id, existing_lock)
                        continue
                except Exception as parse_err:
                    logger.warning("[调度器] 解析锁时间失败: %s, 跳过任务", parse_err)
                    continue
            
            # 【最终防线】检查最近120秒内是否有手动触发的历史记录
            recent_manual = db._fetchone(db.get_conn(),
                """SELECT id, trigger_type, created_at FROM scheduled_task_history 
                   WHERE sched_id=%s AND trigger_type='manual'
                   AND created_at >= DATE_SUB(NOW(), INTERVAL 120 SECOND)
                   ORDER BY id DESC LIMIT 1""",
                (task_id,))
            
            logger.info("[调度器] 最终防线检查: task_id=%s recent_manual=%s", task_id, recent_manual)
            
            if recent_manual:
                logger.info("[调度器] 任务 #%s 最近有手动记录(#%s at %s)，跳过(最终防线)", 
                           task_id, recent_manual.get('id'), recent_manual.get('created_at'))
                continue
            
            # 【防重复2】尝试获取执行锁（防止与API并发）
            scheduler_lock = f"sched_{datetime.now().strftime('%H%M%S')}"
            db._exec(db.get_conn(),
                """UPDATE scheduled_search_task 
                   SET execution_lock=%s 
                   WHERE id=%s AND (execution_lock IS NULL OR execution_lock='')""",
                (scheduler_lock, task_id))
            
            # 验证是否获取到锁
            verify = db._fetchone(db.get_conn(),
                "SELECT execution_lock FROM scheduled_search_task WHERE id=%s",
                (task_id,))
            if not verify or verify.get('execution_lock') != scheduler_lock:
                logger.info("[调度器] 任务 #%s 获取锁失败(可能被API抢占)，跳过", task_id)
                continue
            
            logger.info("[调度器] 任务 #%s (%s) 已到期，开始执行...",
                       task_id, task.get("name") or task.get("company_name"))
            
            # 执行查词
            success = _execute_scheduled_search(task)
            
            # 清除手动触发标记（如果有）
            if task.get("manualTriggerPending") or task.get("manual_trigger_pending"):
                db.clear_scheduled_task_manual_trigger(task_id)
            
            # 更新任务状态和下次执行时间
            _update_task_after_run(task_id, success)
            
            # 【释放执行锁】
            try:
                db._exec(db.get_conn(),
                    "UPDATE scheduled_search_task SET execution_lock=NULL WHERE id=%s",
                    (task_id,))
                logger.info("[调度器] 已释放任务 #%s 的执行锁", task_id)
            except Exception as rel_err:
                logger.warning("[调度器] 释放锁失败: %s", rel_err)
                
    except Exception as e:
        logger.error("[调度器] tick 错误: %s", e, exc_info=True)

    # ─── 邮件通知：检查是否到点发送日报 ───
    try:
        import email_notify_service
        result = email_notify_service.check_and_send_if_due()
        if result is not None:
            if result.get("ok"):
                logger.info("[调度器] 邮件日报已发送: %s", result.get("sent_to", []))
            else:
                logger.warning("[调度器] 邮件日报发送失败: %s", result.get("error") or result.get("skipped", ""))
    except Exception as e:
        logger.error("[调度器] 邮件通知检查异常: %s", e, exc_info=True)

    # ─── 资源站点定时连通性测试（每天 0 点执行一次） ───
    try:
        _check_resource_sites_health()
    except Exception as e:
        logger.error("[调度器] 资源站点测试异常: %s", e, exc_info=True)


def _check_resource_sites_health():
    """每天 0:00 ~ 0:59 期间对所有启用站点执行一次连通性测试（每天只测一次）。
    通过 system_setting.resource_health_last_date 防当日重复。"""
    now = datetime.now()
    # 只在 0 点档（00:00 ~ 00:59）触发
    if now.hour != 0:
        return

    today = now.strftime("%Y-%m-%d")
    settings = db.get_all_settings()
    last_date = settings.get("resource_health_last_date") or ""
    if last_date == today:
        return  # 今天已测过

    logger.info("[调度器] 开始资源站点连通性测试（每日定时）...")
    try:
        import wp_publisher
    except Exception:
        logger.error("[调度器] wp_publisher 模块不可用，跳过资源测试")
        return

    conn = db.get_conn()
    try:
        sites = db._fetchall(conn,
            "SELECT id, site_url, username, application_password "
            "FROM resource_site WHERE status=1")
    except Exception:
        logger.error("[调度器] 查询 resource_site 失败，表可能不存在")
        return

    if not sites:
        db.save_settings({"resource_health_last_date": today})
        return

    ok_count = 0
    fail_count = 0
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    for site in sites:
        try:
            result = wp_publisher.test_connection(
                site["site_url"], site["username"], site["application_password"])
            test_result = "ok" if result["ok"] else "fail"
            test_error = result.get("error") or ""
            if result["ok"]:
                ok_count += 1
            else:
                fail_count += 1
                logger.warning("[调度器] 站点 #%s (%s) 测试失败: %s",
                               site["id"], site["site_url"], test_error)
        except Exception as exc:
            test_result = "fail"
            test_error = str(exc)
            fail_count += 1
            logger.exception("[调度器] 站点 #%s 测试异常", site["id"])

        try:
            db._exec(conn,
                "UPDATE resource_site SET last_test_at=%s, last_test_result=%s, "
                "last_test_error=%s, updated_at=%s WHERE id=%s",
                (now_str, test_result, test_error, now_str, site["id"]))
        except Exception:
            logger.exception("[调度器] 更新站点 #%s 测试结果失败", site["id"])

    # 标记今天已测
    try:
        db.save_settings({"resource_health_last_date": today})
    except Exception:
        logger.exception("[调度器] 保存 resource_health_last_date 失败")

    logger.info("[调度器] 资源站点测试完成：共 %d 个，成功 %d，失败 %d",
                len(sites), ok_count, fail_count)


def start_scheduler():
    """启动调度器后台线程"""
    global _scheduler_running, _scheduler_thread
    
    if _scheduler_running:
        logger.warning("[调度器] 已在运行中")
        return
    
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="ScheduledTaskScheduler")
    _scheduler_thread.start()
    logger.info("[调度器] 后台线程已启动")


def stop_scheduler():
    """停止调度器"""
    global _scheduler_running
    _scheduler_running = False
    logger.info("[调度器] 已请求停止")


def is_scheduler_running() -> bool:
    """返回调度器是否在运行"""
    return _scheduler_running
