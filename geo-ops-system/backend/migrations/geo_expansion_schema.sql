-- GEO 拓词任务表
CREATE TABLE IF NOT EXISTS `geo_expansion_task` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL COMMENT '客户ID',
    brand_name VARCHAR(255) NOT NULL COMMENT '品牌名称',
    prompt_count INT NOT NULL DEFAULT 100 COMMENT '提示词条数(1-500)',
    include_brand TINYINT NOT NULL DEFAULT 0 COMMENT '是否包含品牌词 0=否 1=是',
    include_comparison TINYINT NOT NULL DEFAULT 0 COMMENT '是否包含对比词 0=否 1=是',
    extra_requirements TEXT COMMENT '补充要求(最多2000字符)',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
    error_message TEXT COMMENT '错误信息',
    total_prompts INT DEFAULT 0 COMMENT '实际生成的提示词总数',
    created_at VARCHAR(30),
    updated_at VARCHAR(30),
    completed_at VARCHAR(30),
    INDEX idx_account (account_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GEO 拓词任务';

-- GEO 拓词结果表（生成的提示词）
CREATE TABLE IF NOT EXISTS `geo_expansion_prompt` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL COMMENT '关联任务ID',
    intent_category VARCHAR(100) NOT NULL COMMENT '意图分类',
    core_intent_word VARCHAR(255) NOT NULL COMMENT '核心意图词',
    prompt_text TEXT NOT NULL COMMENT '提示词内容',
    sort_order INT DEFAULT 0 COMMENT '排序序号',
    created_at VARCHAR(30),
    INDEX idx_task (task_id),
    INDEX idx_category (intent_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GEO 拓词结果（提示词）';

-- 系统设置：GEO 拓词指令配置
-- 使用已有的 system_settings 表，key 为 geo_expansion_instruction
