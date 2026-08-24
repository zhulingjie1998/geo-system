# GEO 运营系统

> 面向全球市场的生成式引擎优化运营中枢 — 查词监测 · 排名洞察 · 内容生产与发布一体化

---

## 目录

1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [目录结构](#目录结构)
4. [快速启动](#快速启动)
5. [数据库设计](#数据库设计)
6. [API 接口规范](#api-接口规范)
7. [前端路由与页面](#前端路由与页面)
8. [权限系统 (RBAC)](#权限系统-rbac)
9. [平台定义](#平台定义)
10. [环境变量配置](#环境变量配置)
11. [部署指南](#部署指南)
12. [架构设计决策](#架构设计决策)

---

## 项目概述

GEO 运营系统是一个面向全球市场的 **AI 驱动 SEO/SEM 运营管理平台**，核心能力包括：

| 模块 | 功能描述 |
|------|----------|
| **查词引擎** | 跨 6 大 AI 搜索引擎（ChatGPT/Gemini/Google AIO/Google AIM/Perplexity/Copilot）执行品牌排名追踪 |
| **知识库** | 客户级知识库管理，支持 AI 生成、人工编辑、多版本审核 |
| **周报系统** | 自动化周报生成，支持 HTML 导出、分享链接、模块化组合 |
| **排名分析** | 批量品牌排名分析任务，支持定时调度、趋势图表 |
| **引用源分析** | 抓取并分析搜索结果中的引用来源 |
| **报价工具** | 基于搜索数据的智能报价计算 |
| **外部入口** | 无需登录的邀请码机制，支持客户自助提交查词需求 |
| **内容分析** | AI 驱动的内容质量分析与生文建议 |

---

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 运行时 |
| Flask | 3.0+ | Web 框架 |
| PyMySQL | 1.1+ | MySQL 驱动（纯 Python） |
| Gunicorn | 22.0+ | 生产 WSGI 服务器 |
| Redis | 5.0+ | 缓存 / 任务队列 / 会话 |
| httpx | 0.27+ | 异步 HTTP 客户端（搜索引擎调用） |
| OpenAI SDK | 1.40+ | LLM 网关（Claude 等） |
| BeautifulSoup4 | 4.12+ | HTML 解析（爬虫） |
| Pandas | 2.0+ | 数据处理 |
| Pillow | 10.0+ | 图片处理 |
| openpyxl | 3.1+ | Excel 处理 |
| python-docx | 1.1+ | Word 文档处理 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue.js | 3.5+ | UI 框架（Composition API） |
| Vue Router | 4.6+ | SPA 路由 |
| Pinia | 2.3+ | 状态管理 |
| Element Plus | 2.14+ | UI 组件库 |
| Vite | 5.4+ | 构建工具 / 开发服务器 |
| Axios | 1.6+ | HTTP 客户端 |
| Day.js | 1.11+ | 日期处理 |
| Markdown-it | 14.2+ | Markdown 渲染 |
| xlsx | 0.18+ | Excel 导入导出 |
| WangEditor | 5.1+ | 富文本编辑器 |

### 数据库

| 组件 | 说明 |
|------|------|
| MySQL / MariaDB | 主数据库（InnoDB 引擎，utf8mb4 字符集） |
| Redis | 缓存层（可选） |

### 开发工具

| 工具 | 用途 |
|------|------|
| uv (Astral) | Python 包管理与虚拟环境 |
| pnpm (Corepack) | Node.js 包管理 |
| Playwright | E2E 测试 |

---

## 目录结构

```
geo-ops-system/
├── backend/                      # Python Flask 后端
│   ├── app.py                    # 应用入口：Flask 工厂、中间件、全局错误处理
│   ├── db.py                     # 数据库操作层：连接池、Schema 初始化、CRUD
│   ├── permissions.py            # 权限注册表：PAGE_REGISTRY 单一真相源
│   ├── platforms.py              # 平台常量：展示名↔模型代码映射、别名归一
│   ├── geo_common.py             # 共享工具：路径、时间戳、.env 加载
│   ├── redis_helper.py           # Redis 操作封装
│   ├── access_scope.py           # 数据范围校验（all/self）
│   ├── scraper.py                # 网页抓取引擎
│   ├── overseas_search_adapter.py # 海外搜索引擎适配器
│   ├── llm_claude.py             # LLM 调用封装（Claude/OpenAI 兼容）
│   ├── email_notify_service.py   # 邮件通知服务
│   │
│   ├── 路由模块:
│   ├── email_account_routes.py   # 邮件账号 CRUD
│   ├── kb_routes.py              # 知识库 API
│   ├── knowledge_routes.py       # 知识资料 API
│   │
│   ├── 服务模块:
│   ├── kb_service.py             # 知识库业务逻辑
│   ├── knowledge_service.py      # 知识资料业务逻辑
│   └── knowledge_review_service.py # 知识库审核流程
│   │
│   ├── migrations/               # 数据库迁移脚本
│   │   ├── kb_schema.sql         # 知识库 7 张表 DDL
│   │   └── extra_schema.sql      # 邮件/内容草稿/周报等扩展表
│   │
│   ├── report_templates/         # 报告模板（Jinja2）
│   │   └── email_daily_report.html.j2
│   │
│   ├── gunicorn_conf.py          # Gunicorn 生产配置
│   ├── requirements.txt          # Python 依赖
│   └── .env.example              # 环境变量模板
│
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── App.vue               # 根组件
│   │   ├── main.js               # 入口文件
│   │   │
│   │   ├── api/
│   │   │   └── index.js          # Axios 封装 + 全部 API 方法
│   │   │
│   │   ├── router/
│   │   │   └── index.js          # 路由定义 + 权限守卫
│   │   │
│   │   ├── views/                # 页面组件
│   │   │   ├── LoginPage.vue
│   │   │   ├── HomePage.vue
│   │   │   ├── AccountManagementPage.vue
│   │   │   ├── KeywordSearchPage.vue
│   │   │   ├── KeywordSearchDetailPage.vue
│   │   │   ├── KnowledgeBasePage.vue
│   │   │   ├── AdminUsersPage.vue
│   │   │   ├── SystemSettingsPage.vue
│   │   │   └── RetryStatsPanel.vue
│   │   │
│   │   ├── layouts/
│   │   │   └── DashboardLayout.vue # 仪表盘布局（侧栏+顶栏+主区）
│   │   │
│   │   ├── components/          # 公共组件
│   │   │   ├── GlobalSearch.vue
│   │   │   ├── PlatformIcon.vue
│   │   │   ├── PlatformSelector.vue
│   │   │   ├── RankStatusBadge.vue
│   │   │   ├── PromoteAccountDialog.vue
│   │   │   ├── KbExcelImportDialog.vue
│   │   │   ├── KbExpandDialog.vue
│   │   │   └── common/
│   │   │       ├── MarkdownRenderer.vue
│   │   │       └── PlatformSelector.vue
│   │   │
│   │   ├── composables/         # 组合式函数
│   │   │   └── useGlobalSearch.js
│   │   │
│   │   ├── config/
│   │   │   └── searchIndex.js    # 全局搜索索引配置
│   │   │
│   │   ├── utils/               # 工具函数
│   │   │   ├── brands.js
│   │   │   ├── platformIcon.js
│   │   │   ├── statusMap.js
│   │   │   └── time.js
│   │   │
│   │   └── assets/styles/       # 样式
│   │       ├── main.css
│   │       └── mobile.css
│   │
│   ├── public/                  # 静态资源
│   │   └── ai-icons/            # AI 平台图标（chatgpt/gemini/google_aio/google_aim/perplexity/copilot.svg）
│   │
│   ├── index.html               # SPA 入口 HTML
│   ├── vite.config.js           # Vite 配置（代理/构建/分包）
│   ├── package.json
│   ├── pnpm-lock.yaml
│   └── pnpm-workspace.yaml
│
├── .tools/                       # 本地开发工具（不提交）
│   ├── node/                    # 便携式 Node.js
│   └── mariadb-11.4.5-winx64/   # 便携式 MariaDB
│
└── README.md                     # 本文档
```

---

## 快速启动

### 前置条件

- **Node.js** 18+ 或使用项目内置便携版
- **Python** 3.12+ 或通过 `uv` 安装
- **MySQL** 8.0+ / **MariaDB** 11.4+
- **Redis** 6.0+（可选）

### 一键启动（开发环境）

```bash
# 1. 启动 MariaDB（本地开发）
cd .tools/mariadb-11.4.5-winx64
bin/mariadbd.exe --defaults-file=data/my.ini --bind-address=127.0.0.1 --port=3307 --console

# 2. 启动后端（新终端）
cd backend
# 创建 .env（参考 .env.example）
.venv\Scripts\python.exe -m flask --app app:app run --host 127.0.0.1 --port 7106

# 3. 启动前端（新终端）
cd frontend
node_modules\.bin\vite.cmd --host 127.0.0.1
```

### 默认账号

首次启动后端会自动创建管理员：

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `admin123`（可通过 `GEO_INIT_ADMIN_PW` 环境变量自定义） |
| 角色 | super_admin（拥有全部权限） |

### 访问地址

| 服务 | 地址 |
|------|------|
| 开发服务器（前后端合一） | http://127.0.0.1:3106（`GEO_DEV_PORT` 可改） |
| 生产 Gunicorn | 127.0.0.1:7106（`GEO_GUNICORN_BIND` 可改） |
| 生产对外 | http://80 / https://443（Nginx 反向代理） |
| 数据库 | 127.0.0.1:3307（开发）/ 3306（生产） |

---

## 数据库设计

### 核心业务表

#### account — 客户账号

```sql
CREATE TABLE account (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,        -- 公司名称
    company_brand VARCHAR(255) NOT NULL,        -- 品牌
    user_type VARCHAR(20) DEFAULT 'paid',       -- paid/trial/temp/draft
    current_status TEXT,                         -- 当前状态
    optimize_start_date VARCHAR(255),            -- 优化开始日期
    platforms TEXT,                              -- 覆盖平台 JSON 数组
    insight_bullets TEXT,                        -- 洞察要点
    next_week_bullets TEXT,                       -- 下周计划
    owner_id INT,                                -- 业务负责人
    created_at VARCHAR(255),
    updated_at VARCHAR(255)
);
```

#### account_keyword — 查词关键词

```sql
CREATE TABLE account_keyword (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT NOT NULL,
    intent_category VARCHAR(255) NOT NULL,     -- 意图分类
    core_intent_word VARCHAR(255) NOT NULL,     -- 核心意图词
    intent_prompt VARCHAR(500) NOT NULL,        -- 查询提示词
    sort_order INT,
    created_at VARCHAR(255)
);
```

#### search_task — 查词任务

```sql
CREATE TABLE search_task (
    id VARCHAR(36) PRIMARY KEY,                 -- UUID
    account_id BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'RUNNING',       -- RUNNING/DONE/FAILED/CANCELLED
    total_queries INT,
    completed_queries INT DEFAULT 0,
    current_keyword VARCHAR(255),
    error_message TEXT,
    priority TINYINT DEFAULT 7,                 -- 优先级（越小越高）
    source VARCHAR(30) DEFAULT 'internal_manual', -- internal_manual/scheduled/external
    created_at VARCHAR(255),
    completed_at VARCHAR(255),
    last_heartbeat VARCHAR(30),                 -- 心跳（僵尸检测）
    INDEX idx_st_status_priority (status, priority, created_at)
);
```

#### search_result — 查词结果

```sql
CREATE TABLE search_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    account_id BIGINT NOT NULL,
    keyword_id BIGINT,
    platform VARCHAR(255) NOT NULL,             -- ChatGPT/Perplexity/Gemini...
    model VARCHAR(255) NOT NULL,
    keyword VARCHAR(500) NOT NULL,
    intent_category VARCHAR(255),
    core_intent_word VARCHAR(255),
    intent_prompt VARCHAR(500),
    success TINYINT(1),
    response_json LONGTEXT,                     -- 原始响应
    answer_text LONGTEXT,                        -- 提取文本
    answer_html LONGTEXT,                        -- 提取 HTML
    summarys_json LONGTEXT,                      -- 结构化摘要
    screenshot_url VARCHAR(1000),
    brand_rank INT,                              -- 品牌排名
    brand_analysis_json LONGTEXT,                -- 品牌分析
    duration FLOAT,
    attempt INT,
    search_date VARCHAR(255) NOT NULL,
    created_at VARCHAR(255),
    INDEX idx_sr_task (task_id),
    INDEX idx_sr_account_date (account_id, search_date)
);
```

### 系统管理表

#### admin_user — 管理员用户

```sql
CREATE TABLE admin_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,         -- werkzeug hash
    role VARCHAR(20) DEFAULT 'operator',         -- super_admin/admin/operator
    role_id INT,                                 -- 关联 role 表
    permissions TEXT,                            -- 兼容旧版权限列表
    created_at VARCHAR(30),
    last_login_at VARCHAR(30)
);
```

#### role — 角色 (RBAC)

```sql
CREATE TABLE role (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,            -- 显示名称
    code VARCHAR(50) NOT NULL UNIQUE,            -- 代码标识
    data_scope ENUM('all','self') DEFAULT 'self',-- 数据范围
    is_builtin TINYINT(1) DEFAULT 0,             -- 内置角色不可删除
    description VARCHAR(200),
    created_at VARCHAR(30),
    updated_at VARCHAR(30)
);

-- 内置角色：super_admin / admin / operator
```

#### role_page — 角色页面权限

```sql
CREATE TABLE role_page (
    role_id INT NOT NULL,
    page_key VARCHAR(50) NOT NULL,               -- 对应 permissions.PAGE_REGISTRY
    PRIMARY KEY (role_id, page_key)
);
```

#### team / account_owner — 团队与负责人

```sql
CREATE TABLE team (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    leader_user_id INT,
    ...
);

CREATE TABLE account_owner (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    owner_user_id INT NOT NULL,
    UNIQUE KEY uq_ao (account_id, owner_user_id)
);
```

### 报告与分享表

#### weekly_report — 周报

```sql
CREATE TABLE weekly_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    period_start VARCHAR(10) NOT NULL,
    period_end VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',         -- pending/generating/done/failed
    html_content LONGTEXT,
    data_snapshot_json LONGTEXT,
    ai_insights_json TEXT,
    resource_checklist_json LONGTEXT,            -- GEO 12 类资料清单
    share_token VARCHAR(64),                      -- 分享令牌
    report_type VARCHAR(20) DEFAULT 'weekly',     -- weekly/monthly/custom
    selected_modules JSON,                        -- 选中模块
    token_expires_at VARCHAR(30),                 -- 分享过期时间
    access_count INT DEFAULT 0,
    access_limit INT DEFAULT 0,                   -- 0=不限
    ...
);
```

#### report_info / overview_bullet / ranking_record / question_record — 分享报告数据

```sql
-- report_info: 分享元信息（share_code → brand/platforms/date）
-- overview_bullet: 概览要点（section: strengths/opportunities/threats/recommendations）
-- ranking_record: 排名记录（platform/intent/rank_status/remark）
-- question_record: 用户问题记录（question/answer/rank/screenshot）
-- cite_item: 引用来源（title/url/snippet/site_name）
```

### 知识库表（kb_schema.sql）

| 表名 | 用途 |
|------|------|
| `customer_knowledge` | 知识条目（标题/内容/标签/状态/全文检索） |
| `customer_knowledge_kb` | 知识库版本（markdown 正文/AI 生成记录） |
| `customer_knowledge_source` | 知识库附件（文件上传/解析状态） |
| `kb_gen_task` | KB 生成任务（跨 worker 状态共享） |
| `kb_import_batch` | Excel 导入批次 |
| `kb_review` | 知识库审核（draft/finalized + 分享 token） |
| `kb_review_annotation` | 审核批注（numeric/discrepancy/promotion） |

### 扩展表（extra_schema.sql）

| 表名 | 用途 |
|------|------|
| `email_account` | 邮件发送账号（SMTP 多账号切换） |
| `content_draft` | 内容草稿（LLM 生文中间态） |
| `content_draft_batch` | 草稿批次（批量生文任务） |
| `content_analysis` | 内容分析结果（AI 分析报告） |

### 任务与调度表

| 表名 | 用途 |
|------|------|
| `ranking_task` / `ranking_result` | 品牌排名分析任务与结果 |
| `quote_task` / `quote_query_run` / `quote_result` | 报价任务 |
| `scheduled_search_task` | 定时查词调度（daily/weekly/monthly） |
| `cancel_signal` | 任务取消信号 |
| `result_scrape` | 引用源抓取任务 |
| `site_price` | 参考价格数据 |

### 外部入口表

| 表名 | 用途 |
|------|------|
| `external_invite` | 外部邀请码（max_uses/expires_at/IP 限制） |
| `external_use` | 外部使用记录（客户提交的任务） |
| `external_brute_lock` | IP 暴力破解防护 |
| `login_attempt` / `login_lockout` | 登录安全审计 |

### 系统配置表

| 表名 | 用途 |
|------|------|
| `system_setting` | KV 配置存储（flask_secret_key 等） |
| `account_keyword_audit` | 关键词变更审计日志 |
| `account_webhook_config` | 客户官网 webhook 对接配置（URL、OAuth2 token、启用状态） |

---

## API 接口规范

### 基础约定

- **Base URL**: `/api`
- **认证方式**: Session Cookie（Flask session）
- **响应格式**: 
  - 成功: `{ code: 200, message: "ok", data: {...} }`
  - 错误: `{ code: 4xx/5xx, message: "错误信息" }` 或 `{ error: "错误信息" }`
- **日期格式**: `YYYY-MM-DD HH:MM:SS`（中文环境统一）
- **CORS**: 仅同源（前后端同一域或代理）

### 公开接口（无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户信息 |
| GET | `/api/share-info/:code` | 分享信息查询 |
| GET | `/api/overview/:code` | 概览数据 |
| GET | `/api/ranking/:code` | 排名数据 |
| GET | `/api/questions/:code` | 问题记录 |
| POST | `/api/external/verify` | 邀请码验证 |
| POST | `/api/external/submit` | 提交查词任务 |
| ... | `/api/share/*` | 所有分享相关接口 |
| ... | `/api/external/*` | 所有外部入口接口 |

### 鉴权接口（需登录）

#### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/logout` | 登出 |
| POST | `/api/auth/change-password` | 修改密码 |

#### 账号管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/accounts` | 账号列表 |
| POST | `/api/accounts` | 创建账号 |
| GET | `/api/accounts/:id` | 账号详情 |
| PUT | `/api/accounts/:id` | 更新账号 |
| PATCH | `/api/accounts/:id` | 局部更新 |
| DELETE | `/api/accounts/:id` | 删除（软删除） |
| POST | `/api/accounts/:id/promote` | 转正 |
| GET | `/api/accounts/:id/keywords` | 获取关键词 |
| PUT | `/api/accounts/:id/keywords` | 更新关键词 |
| POST | `/api/accounts/:id/transfer` | 改派负责人 |
| POST | `/api/accounts/:id/owners` | 设置多负责人 |
| POST | `/api/accounts/:id/team` | 设置团队 |
| GET | `/api/accounts/recycle-bin` | 回收站 |
| POST | `/api/accounts/:id/restore` | 恢复 |
| DELETE | `/api/accounts/:id/purge` | 永久删除 |
| GET | `/api/accounts/:id/share-token` | 获取分享 Token |
| POST | `/api/accounts/:id/share-token/reset` | 重置分享 Token |

#### 查词功能

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/search/start/:accountId` | 开始查词 |
| POST | `/api/search/start-temp` | 临时查词 |
| GET | `/api/search/progress/:taskId` | 进度查询 |
| GET | `/api/search/progress-log/:taskId` | 进度日志 |
| POST | `/api/search/cancel/:taskId` | 取消任务 |
| GET | `/api/search/results/:accountId` | 结果查询 |
| GET | `/api/search/history/:accountId` | 历史记录 |
| DELETE | `/api/search/history/:accountId/all` | 清空历史 |
| DELETE | `/api/search/task/:taskId` | 删除单次任务 |
| GET | `/api/search/today-stats` | 今日统计 |
| GET | `/api/search/account-summary` | 账号汇总 |
| POST | `/api/search/retry-failed/:taskId` | 重试失败项 |
| POST | `/api/search/continue/:accountId` | 继续未完成 |
| GET | `/api/search/unsearched-count/:accountId` | 未查数量 |
| GET | `/api/search/running/:accountId` | 运行中任务 |
| GET | `/api/search/export/:accountId` | 导出 Excel |
| GET | `/api/search/brand-ranking/:accountId` | 品牌排名 |
| POST | `/api/search/reanalyze/:accountId` | 重新分析 |

#### 排名分析工具

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/rank-tool/tasks` | 任务列表 |
| POST | `/api/rank-tool/submit` | 提交分析 |
| POST | `/api/ranking/submit-upload` | 上传分析 |
| GET | `/api/rank-tool/progress/:taskId` | 进度 |
| GET | `/api/rank-tool/results/:taskId` | 结果 |
| POST | `/api/rank-tool/retry/:taskId` | 重试 |
| GET | `/api/rank-tool/history` | 历史 |
| GET | `/api/rank-tool/trends` | 趋势 |
| GET | `/api/rank-tool/brands` | 品牌列表 |
| GET | `/api/rank-tool/export/:taskId` | 导出 CSV |
| POST | `/api/rank-tool/delete/:taskId` | 删除 |
| POST | `/api/rank-tool/cancel/:taskId` | 取消 |
| POST | `/api/rank-tool/continue/:taskId` | 继续 |
| POST | `/api/rank-tool/rerun/:taskId` | 重跑 |
| GET | `/api/rank-tool/running` | 运行中 |
| GET/POST/PUT/DELETE | `/api/rank-tool/schedule/*` | 定时调度 CRUD |

#### 引用源分析

| 方法 | 路径前缀 | 说明 |
|------|----------|------|
| GET/POST/DELETE | `/api/citation/*` | 引用源抓取/结果/调度 |

#### 报价工具

| 方法 | 路径前缀 | 说明 |
|------|----------|------|
| GET/POST/DELETE | `/api/quote/*` | 报价任务/调度 |

#### 周报管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/accounts/:id/weekly-reports` | 周报列表 |
| POST | `/api/accounts/:id/weekly-reports/generate` | 生成周报 |
| GET | `/api/weekly-reports/:id` | 周报详情 |
| PUT | `/api/.../weekly-reports/:id/expiry` | 设置过期 |
| DELETE | `/api/weekly-reports/:id` | 删除 |
| GET | `/api/weekly-reports/:id/html` | HTML 视图 |
| GET | `/api/weekly-reports/:id/download` | 下载 |
| GET/POST/PUT/DELETE | `/api/weekly-schedules/*` | 定时周报调度 |

#### 知识库

| 方法 | 路径前缀 | 说明 |
|------|----------|------|
| CRUD | `/api/kb/*` | 知识条目 CRUD |
| CRUD | `/api/knowledge/*` | 知识资料 CRUD |
| POST | `/api/kb/:id/generate` | AI 生成知识库 |
| GET/POST | `/api/kb-review/*` | 审核流程 |

#### 管理员 & RBAC

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/PUT/DELETE | `/api/admin/users` | 管理员 CRUD |
| POST | `/api/admin/users/:id/reset-password` | 重置密码 |
| GET/POST/PUT/DELETE | `/api/admin/roles` | 角色 CRUD |
| GET | `/api/permissions/registry` | 权限注册表 |
| CRUD | `/api/admin/invites` | 邀请码管理 |
| CRUD | `/api/teams` | 团队管理 |

#### 系统设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取设置 |
| PUT | `/api/settings` | 更新设置 |

#### 首页

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/home/overview` | 首页概览数据 |

#### 内容分析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/content-analysis/generate` | 生成分析 |
| GET | `/api/content-analysis/:accountId` | 获取分析 |
| GET | `/api/content-analysis/batch` | 批量获取 |
| GET | `/api/content-analysis/:id/download/:type` | 下载文档 |

#### 写作辅助

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/api/account/:id/writing-requirements` | 发稿要求 |
| CRUD | `/api/account/:id/writing-lessons` | 写作心得 |
| POST | `/api/content/preview-prompt` | Prompt 预览 |
| POST | `/api/account/:id/refine-rules` | 规则提炼 |

#### 内容发布（官网配置 / Webhook）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/publish/official-configs` | 获取客户官网配置列表 |
| GET | `/api/publish/official-config/:accountId` | 获取单个客户官网配置 |
| PUT | `/api/publish/official-config/:accountId` | 保存/更新官网 webhook 配置 |
| DELETE | `/api/publish/official-config/:accountId` | 取消并清空官网配置 |
| POST | `/api/publish/webhook/publish` | 官网即时发布（转发到客户 webhook） |

---

## 前端路由与页面

### 路由结构

```
/login                          → LoginPage（公开）
/dashboard                      → DashboardLayout（需登录 + 权限）
├── /dashboard/home             → HomePage（首页概览）
├── /dashboard/accounts         → AccountManagementPage（客户管理）
├── /dashboard/keyword-search   → KeywordSearchPage（查词管理）
├── /dashboard/keyword-search/:accountId → KeywordSearchDetailPage（查词详情）
├── /dashboard/knowledge        → KnowledgeBasePage（知识库）
├── /dashboard/admin-users      → AdminUsersPage（账号/角色管理）
├── /dashboard/roles            → → redirect to admin-users?tab=roles
├── /dashboard/settings         → SystemSettingsPage（系统设置）
/publish                        → PublishLayout（需登录）
├── /publish/home               → PublishHome（发布首页）
├── /publish/customers          → PublishCustomersPage（客户管理）
├── /publish/customer-kb        → PublishKnowledgePage（客户知识库）
├── /publish/customer-kb/:id    → PublishKbDetailPage（客户知识库详情）
├── /publish/content-library    → PublishContentLibraryPage（内容库）
├── /publish/content-library/:accountId → PublishContentLibraryDetailPage（内容库详情）
├── /publish/content-publish/:accountId → PublishContentPublishPage（内容发布）
├── /publish/releases           → PublishReleaseManagementPage（发布管理）
├── /publish/releases/:accountId → PublishReleaseRecordsPage（发布记录）
├── /publish/resources          → PublishResourceManagementPage（资源管理）
├── /publish/official-config    → PublishOfficialConfigPage（官网配置）
/                               → redirect to /dashboard/home
```

### 页面组件清单

| 路由名称 | 组件文件 | 权限 key | 分组 |
|----------|----------|----------|------|
| Login | `LoginPage.vue` | - | 公开 |
| DashboardHome | `HomePage.vue` | home | 业务功能 |
| DashboardAccounts | `AccountManagementPage.vue` | accounts | 业务功能 |
| KeywordSearch | `KeywordSearchPage.vue` | keyword-search | 业务功能 |
| KeywordSearchDetail | `KeywordSearchDetailPage.vue` | keyword-search | 业务功能 |
| DashboardKnowledge | `KnowledgeBasePage.vue` | knowledge | 业务功能 |
| AdminUsers | `AdminUsersPage.vue` | admin-users | 系统管理 |
| Roles | （redirect） | roles | 系统管理 |
| SystemSettings | `SystemSettingsPage.vue` | settings | 系统管理 |
| PublishHome | `PublishHome.vue` | publish | 内容发布 |
| PublishCustomers | `PublishCustomersPage.vue` | publish | 内容发布 |
| PublishCustomerKb | `PublishKnowledgePage.vue` | publish-article | 内容发布 |
| PublishKbDetail | `PublishKbDetailPage.vue` | publish-article | 内容发布 |
| PublishContentLibrary | `PublishContentLibraryPage.vue` | publish-article | 内容发布 |
| PublishContentLibraryDetail | `PublishContentLibraryDetailPage.vue` | publish-article | 内容发布 |
| PublishContentPublish | `PublishContentPublishPage.vue` | publish-article | 内容发布 |
| PublishReleaseManagement | `PublishReleaseManagementPage.vue` | publish-orders | 内容发布 |
| PublishReleaseRecords | `PublishReleaseRecordsPage.vue` | publish-orders | 内容发布 |
| PublishResourceManagement | `PublishResourceManagementPage.vue` | publish-batch | 内容发布 |
| PublishOfficialConfig | `PublishOfficialConfigPage.vue` | publish-orders | 内容发布 |

### 全局公共组件

| 组件 | 用途 |
|------|------|
| `GlobalSearch.vue` | 全局搜索弹窗（⌘K） |
| `PlatformIcon.vue` | AI 平台图标（ChatGPT/Gemini/Google AIO/Google AIM/Perplexity/Copilot） |
| `PlatformSelector.vue` | 平台多选器 |
| `RankStatusBadge.vue` | 排名状态标签 |
| `PromoteAccountDialog.vue` | 客户转正对话框 |
| `KbExcelImportDialog.vue` | 知识库 Excel 导入 |
| `KbExpandDialog.vue` | 知识库扩写对话框 |
| `MarkdownRenderer.vue` | Markdown 渲染器 |
| `RetryStatsPanel.vue` | 重试统计面板 |

---

## 权限系统 (RBAC)

### 设计原则

权限注册表 (`permissions.py`) 是**单一真相源**。新增页面只需在此添加一行：

```python
("page_key", "页面中文名", "分组"),
```

### 内置角色

| 角色 Code | 名称 | 数据范围 | 说明 |
|-----------|------|----------|------|
| `super_admin` | 超级管理员 | all | 拥有全部页面和数据，不可删除 |
| `admin` | 管理员 | self/all | 可管理用户和角色 |
| `operator` | 运营人员 | self | 仅查看自己负责的数据 |

### 页面注册表

```python
PAGE_REGISTRY = [
    ("home",            "首页",            "业务功能"),
    ("accounts",        "客户管理",        "业务功能"),
    ("keyword-search",  "查词管理",        "业务功能"),
    ("knowledge",       "客户知识库",      "业务功能"),
    ("admin-users",     "账号管理",        "系统管理"),
    ("roles",           "角色管理",        "系统管理"),
    ("settings",        "系统设置",        "系统管理"),
]
```

### 数据范围

| Scope | 含义 |
|-------|------|
| `all` | 可查看团队全部数据 |
| `self` | 仅可查看自己 `owner_id` 的数据 |

### 前端权限守卫

路由跳转时自动检查：
1. 未登录 → 跳转 `/login`
2. 已登录但无该页面权限 → 跳转 `/dashboard/home`
3. `super_admin` → 自动放行所有页面

---

## 平台定义

### 支持的 AI 搜索引擎

| 展示名 | 模型代码 | 别名 |
|--------|----------|------|
| ChatGPT | chatgpt | GPT, OpenAI, gpt, openai |
| Gemini | gemini | Google Gemini, Bard |
| Google AIO | google_aio | AIO, AI Overview, Google AI Overview |
| Google AIM | google_aim | AIM, AI Mode, Google AI Mode |
| Perplexity | perplexity | PPLX, pplx |
| Copilot | copilot | Bing, Bing Copilot, Microsoft Copilot |

### 归一化函数

`platforms.normalize_platforms()` 将别名/简写统一为标准展示名，保持顺序、去重。

---

## 环境变量配置

### 必需配置

```env
# ===== MySQL =====
GEO_DB_HOST=127.0.0.1
GEO_DB_PORT=3306
GEO_DB_USER=geo_system
GEO_DB_PASSWORD=your_password_here
GEO_DB_NAME=waimao_geo

# ===== Flask =====
GEO_FLASK_SECRET=your_random_secret_here    # python -c "import secrets;print(secrets.token_hex(32))"
```

### 可选配置

```env
# ===== 首次启动 =====
GEO_INIT_ADMIN=admin123                     # 初始管理员密码

# ===== 安全 =====
GEO_COOKIE_INSECURE=1                       # 本地 dev 设 1（HTTP 下启用 cookie）
GEO_EXTERNAL_TOKEN_SECRET=xxx               # 外部入口 token 密钥

# ===== 开发服务器（dev_server.py）=====
GEO_DEV_HOST=0.0.0.0
GEO_DEV_PORT=3106

# ===== Gunicorn（生产）=====
GEO_GUNICORN_BIND=127.0.0.1:7106
GEO_GUNICORN_WORKERS=1
GEO_GUNICORN_THREADS=4
GEO_GUNICORN_TIMEOUT=600
GEO_LOG_DIR=./logs

# ===== 查词服务 =====
GEO_SEARCH_API_URL=                          # 查词 API 网关

# ===== LLM =====
GEO_LLM_BASE_URL=                            # LLM API 地址

# ===== Redis =====
GEO_REDIS_HOST=127.0.0.1
GEO_REDIS_PORT=6379
GEO_REDIS_DB=0
```

### `.env` 加载规则

- 位置：`backend/.env`（相对于 `geo_common.py` 所在目录）
- 方式：仅注入未设置的环境变量（不覆盖系统已有值）
- 格式：每行 `KEY=VALUE`，忽略空行和 `#` 注释
- 安全：`.env` 已加入 `.gitignore`，不会提交到版本库

---

## 部署指南

### 生产部署架构

```
[ Nginx / 反向代理 ]
    ↓ (HTTPS, 静态资源)
[ Gunicorn (WSGI) ] ← :7106
    ↓
[ Flask App ]
    ↓
[ MySQL/MariaDB ] ← :3306
[ Redis ] ← :6379 (可选)
```

### 生产部署步骤（Git 拉取方式）

> **推荐**：使用 `deploy.sh` 一键部署，无需手动上传文件。

#### 首次部署

1. **克隆代码到服务器**
   ```bash
   cd /www/wwwroot
   git clone https://github.com/zhulingjie1998/geo-system.git GEO
   cd GEO
   ```

2. **配置环境变量**
   ```bash
   cp backend/.env.example backend/.env
   # 编辑 .env 填入生产配置（数据库密码、密钥等）
   vi backend/.env
   ```

3. **安装后端依赖**
   ```bash
   cd backend
   /www/server/pyporject_evn/GEO/bin/pip install -r requirements.txt
   ```

4. **安装前端依赖并构建**
   ```bash
   cd ../frontend
   npm install -g pnpm   # 如果没有 pnpm
   pnpm install
   pnpm build
   ```

5. **部署前端到后端 static**
   ```bash
   cp -r dist ../backend/static
   ```

6. **启动 Gunicorn**
   ```bash
   cd ../backend
   /www/server/pyporject_evn/GEO/bin/gunicorn -c gunicorn_conf.py app:app --daemon
   ```

7. **配置 Nginx**（见下方配置示例）

#### 后续更新（一键部署）

每次代码推送到 GitHub 后，在服务器上执行：

```bash
cd /www/wwwroot/GEO
bash deploy.sh
```

`deploy.sh` 会自动完成：
1. `git pull` 拉取最新代码
2. 安装后端依赖（如有更新）
3. 重新构建前端
4. 复制 dist 到 backend/static
5. 重启 Gunicorn
6. 验证服务是否正常

### Nginx 配置示例
   ```nginx
   # HTTP → HTTPS 跳转
   server {
       listen 80;
       server_name your-domain.com;
       return 301 https://$host$request_uri;
   }

   # HTTPS 主站
   server {
       listen 443 ssl;
       server_name your-domain.com;

       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;

       # 前端静态文件
       location / {
           root /path/to/frontend/dist;
           try_files $uri $uri/ /index.html;
       }

       # API 反向代理到 Gunicorn
       location /api {
           proxy_pass http://127.0.0.1:7106;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

### Docker 部署（可选）

```dockerfile
# Dockerfile.backend
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 7106
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
```

```dockerfile
# Dockerfile.frontend
FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

---

## 架构设计决策

### 为什么选择 Flask 而非 Django/FastAPI？

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 框架 | Flask | 项目以 REST API 为主，不需要 ORM/Admin；Flask 轻量灵活 |
| 数据库驱动 | PyMySQL 直连 | 避免 SQLAlchemy 抽象层，SQL 可控性更强 |
| Schema 管理 | 代码内 `_init_schema()` | 首次启动自动建表，无需额外迁移工具 |
| 认证 | Flask Session | 简单够用；后续可升级 JWT |

### 为什么前端用 Vue 3 + Vite？

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 框架 | Vue 3 | 团队技术栈一致；Composition API 适合复杂交互 |
| 构建 | Vite | 极速 HMR；原生 ESM 支持 |
| UI 库 | Element Plus | 企业级后台组件生态完善 |
| 状态 | Pinia | Vue 3 官方推荐；TypeScript 友好 |

### 安全设计

| 措施 | 实现 |
|------|------|
| 登录限流 | 5 次/5 分钟失败触发锁定；渐进式冷却（5→10→15 分钟） |
| CSRF 保护 | SameSite=Lax + HttpOnly Cookie |
| SQL 注入防护 | 参数化查询（PyMySQL cursor.execute） |
| XSS 防护 | 响应头 Content-Type: nosniff; X-Frame-Options |
| 密码存储 | werkzeug security generate_password_hash（PBKDF2） |
| 敏感接口白名单 | `_PUBLIC_API_PREFIXES` 元组控制 |
| 外部入口防护 | 邀请码 + IP 速率限制 + 使用次数限制 |

### 性能优化策略

| 策略 | 实现 |
|------|------|
| 前端分包 | Vite manualChunks：vendor / vendor-element / vendor-md / vendor-vue / vendor-xlsx |
| Console 移除 | esbuild drop: console/debugger（生产构建） |
| Source Map 关闭 | sourcemap: false（避免泄露源码） |
| 资源指纹 | chunkFileNames: assets/[name]-[hash].js |
| 数据库连接池 | 线程局部连接 + ping(reconnect=True) |
| Schema 幂等初始化 | 进程级一次（非线程级），避免远程库重复建表 |
| 心跳超时检测 | 启动时回收上次崩溃留下的僵尸 RUNNING 任务 |

---

## 常见问题

### Q: 登录后一直转圈？
**A**: 检查后端是否正常运行（`http://127.0.0.1:7106/api/auth/me` 应返回 JSON）。常见原因：
- MySQL 未启动或连接参数错误
- `GEO_COOKIE_INSECURE=1` 未设置（HTTP 下浏览器拒绝 Session Cookie）

### Q: 如何重置管理员密码？
**A**: 直接修改数据库或设置 `GEO_INIT_ADMIN_PW` 环境变量后重启（仅在无 admin 用户时生效）。已有用户需通过 API 或数据库直接更新 `password_hash`。

### Q: 如何新增一个页面？
**A**: 三步即可：
1. `permissions.py` 的 `PAGE_REGISTRY` 添加一行
2. `frontend/src/router/index.js` 添加路由
3. 创建对应的 View 组件

### Q: 如何添加新的 AI 搜索平台？
**A**: 在 `platforms.py` 的 `PLATFORM_MODEL_MAP` 和 `PLATFORM_ALIASES` 中添加映射，然后在 `overseas_search_adapter.py` 实现对应平台的搜索逻辑。同时需要在 `frontend/src/utils/platformIcon.js` 添加图标映射，并在 `public/ai-icons/` 添加对应的 SVG 图标文件。

---

## 更新日志

详见各模块 Git 提交记录。

---

*本文档由 AI 自动生成，最后更新于 2026-07-23*
