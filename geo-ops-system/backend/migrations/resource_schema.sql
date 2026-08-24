-- 资源站点表（WordPress 站点管理 + 发布）
CREATE TABLE IF NOT EXISTS `resource_site` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_type VARCHAR(20) NOT NULL DEFAULT 'blog' COMMENT 'blog/forum/b2b/qa',
    site_name VARCHAR(255) NOT NULL COMMENT '站点名称',
    site_url VARCHAR(512) NOT NULL COMMENT '站点地址（含 https://）',
    username VARCHAR(128) NOT NULL COMMENT 'WP 管理员用户名',
    application_password VARCHAR(255) NOT NULL COMMENT 'WP Application Password 令牌',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用 0=停用',
    last_test_at VARCHAR(30),
    last_test_result VARCHAR(20),
    last_test_error TEXT,
    created_at VARCHAR(30),
    updated_at VARCHAR(30),
    INDEX idx_type (site_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资源发布站点（WordPress）';

-- 发布记录表
CREATE TABLE IF NOT EXISTS `publish_record` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    article_id INT DEFAULT 0,
    site_id INT NOT NULL,
    post_id INT DEFAULT 0 COMMENT 'WP 返回的文章 ID',
    post_url VARCHAR(512) COMMENT '已发布文章 URL',
    title VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/published/failed',
    error_message TEXT,
    published_at VARCHAR(30),
    created_at VARCHAR(30),
    INDEX idx_account (account_id),
    INDEX idx_site (site_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='内容发布记录';
