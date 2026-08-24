-- 添加防重复的唯一索引
-- 确保同一个 sched_id 在120秒内只能有一条记录

-- 1. 首先清理现有的重复数据（保留最早的）
DELETE h1 FROM scheduled_task_history h1
INNER JOIN scheduled_task_history h2
WHERE h1.id > h2.id
AND h1.sched_id = h2.sched_id
AND TIMESTAMPDIFF(SECOND, h2.created_at, h1.created_at) < 120;

-- 2. 添加函数索引（MySQL 8.0+）或普通索引
-- 注意：MySQL 不支持在表达式上创建唯一约束，所以我们需要用触发器

-- 创建防重复触发器
DELIMITER //

CREATE TRIGGER prevent_duplicate_history
BEFORE INSERT ON scheduled_task_history
FOR EACH ROW
BEGIN
    DECLARE recent_count INT;
    
    -- 检查120秒内是否已有同 sched_id 的记录
    SELECT COUNT(*) INTO recent_count
    FROM scheduled_task_history
    WHERE sched_id = NEW.sched_id
    AND created_at >= DATE_SUB(NOW(), INTERVAL 120 SECOND);
    
    -- 如果已有记录，阻止插入
    IF recent_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Duplicate history record within 120 seconds';
    END IF;
END;
//

DELIMITER ;

-- 验证触发器已创建
SELECT * FROM information_schema.TRIGGERS 
WHERE TRIGGER_NAME = 'prevent_duplicate_history';
