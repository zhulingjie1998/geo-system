CREATE TABLE IF NOT EXISTS `customer_knowledge` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` int DEFAULT NULL COMMENT 'NULL 表示系统级模板库',
  `kb_type` varchar(32) NOT NULL DEFAULT 'basic' COMMENT 'basic/product/case/news/faq/competitor/brand_story/custom',
  `title` varchar(512) NOT NULL,
  `content` longtext NOT NULL,
  `summary` varchar(1024) DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual/url/import/generated',
  `source_url` varchar(1024) DEFAULT NULL,
  `source_ref` varchar(255) DEFAULT NULL COMMENT '来源引用(例:查词任务ID、引用源ID等)',
  `priority` int NOT NULL DEFAULT '0' COMMENT '越大越优先',
  `status` varchar(16) NOT NULL DEFAULT 'active' COMMENT 'active/archived/draft',
  `created_by` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `module` varchar(255) DEFAULT NULL,
  `import_batch_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_kb_account` (`account_id`,`status`),
  KEY `idx_kb_type` (`kb_type`),
  KEY `idx_kb_created` (`created_at`),
  FULLTEXT KEY `ft_kb_title_content` (`title`,`content`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `customer_knowledge_kb` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL,
  `version` int NOT NULL DEFAULT '1',
  `content` longtext NOT NULL COMMENT 'markdown 知识库正文',
  `instruction` text COMMENT '本次用户输入的指令',
  `source_ids` json DEFAULT NULL COMMENT '本次用了哪些资料 id 数组',
  `parent_id` bigint DEFAULT NULL COMMENT '前一版 id',
  `is_current` tinyint(1) NOT NULL DEFAULT '0',
  `created_by` varchar(20) NOT NULL DEFAULT 'ai' COMMENT 'ai / human',
  `llm_model` varchar(50) DEFAULT NULL,
  `llm_used_tokens` int DEFAULT NULL,
  `created_at` varchar(30) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_acct_version` (`account_id`,`version`),
  KEY `idx_current` (`account_id`,`is_current`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `customer_knowledge_source` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL,
  `kb_version_id` bigint DEFAULT NULL COMMENT 'NULL=基础资料 / 非NULL=某版的补充资料',
  `file_name` varchar(255) NOT NULL,
  `file_type` varchar(20) NOT NULL,
  `file_size` int NOT NULL DEFAULT '0',
  `parsed_text` longtext,
  `parser_status` varchar(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/parsing/done/failed',
  `parser_error` varchar(500) DEFAULT NULL,
  `raw_file_path` varchar(500) DEFAULT NULL,
  `created_at` varchar(30) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_acct` (`account_id`,`kb_version_id`),
  KEY `idx_status` (`parser_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `kb_gen_task` (
  `id` varchar(36) NOT NULL COMMENT 'uuid task_id',
  `account_id` int NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'running' COMMENT 'running/done/failed',
  `hint` text,
  `kb_id` bigint DEFAULT NULL,
  `version` int DEFAULT NULL,
  `error` text,
  `created_at` varchar(30) DEFAULT NULL,
  `updated_at` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_acct` (`account_id`,`status`),
  KEY `idx_status_updated` (`status`,`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='KB 生成任务及 worker 共享状态';

CREATE TABLE IF NOT EXISTS `kb_import_batch` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` bigint NOT NULL,
  `version_no` int NOT NULL,
  `row_count` int DEFAULT '0',
  `note` varchar(500) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'active',
  `created_by` int DEFAULT NULL,
  `created_at` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_kib_acc` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `kb_review` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `account_id` int NOT NULL,
  `kb_version_id` bigint NOT NULL COMMENT '审核针对的知识库版本 customer_knowledge_kb.id',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/finalized',
  `reviewer_id` int DEFAULT NULL,
  `material_suggestions` json DEFAULT NULL COMMENT '建议客户提供资料清单[{name,note}]',
  `share_token` varchar(64) DEFAULT NULL COMMENT 'secrets.token_hex(24)',
  `created_at` varchar(30) NOT NULL,
  `updated_at` varchar(30) DEFAULT NULL,
  `finalized_at` varchar(30) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_review_version` (`account_id`,`kb_version_id`),
  UNIQUE KEY `uniq_review_share_token` (`share_token`),
  KEY `idx_review_account` (`account_id`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `kb_review_annotation` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `review_id` bigint NOT NULL,
  `category` varchar(16) NOT NULL COMMENT 'numeric/discrepancy/promotion',
  `quote` text NOT NULL COMMENT '选中的正文原文片段',
  `occurrence` int NOT NULL DEFAULT '0' COMMENT '该片段在正文第几次出现(从0开始)',
  `reason` text COMMENT '该事项理由',
  `order_index` int NOT NULL DEFAULT '0',
  `created_at` varchar(30) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_anno_review` (`review_id`,`order_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
