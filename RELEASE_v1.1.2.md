# GEO 运营系统 v1.1.2 更新日志

**发布日期**: 2026-09-02  
**版本类型**: 功能更新

---

## 一、功能更新

### 1. 新增 - 智能生文输出语言选择
- 新增"输出语言"选择卡片，支持 **47 种**全球主流语言
- 语言按区域分组显示：
  - 常用语言：中文（简体/繁体）、英语（美国/英国）
  - 亚洲语言：日语、韩语、越南语、泰语、印尼语等 10 种
  - 欧洲语言：法语、德语、西班牙语、俄语等 19 种
  - 中东/非洲语言：阿拉伯语、希伯来语、印地语等 11 种
  - 美洲语言：拉丁美西班牙语、巴西葡萄牙语
- 所有语言选项使用**中文描述**
- 默认值：中文（简体）zh-CN

### 2. 新增 - 指令库 {language} 变量支持
- 变量插入工具栏新增 `{language}` 按钮
- 占位符说明文档更新
- 支持在指令模板中使用语言变量控制输出语言

### 3. 优化 - 后端生成逻辑
- `content_routes.py`: API 接收 `language` 参数（默认 zh-CN）
- `content_service.py`:
  - `_get_language_name()`: 语言代码→名称映射
  - `_get_language_instruction()`: 20+ 种语言专属输出指令
  - System/User Prompt 均包含语言要求

### 4. 修复 - 内容库显示问题
- 修复内容库详情页不显示 AI 生成文章的问题
- 合并数据库文章与本地存储文章

---

## 二、修改文件清单

### 后端文件 (9个)
| 文件路径 | 说明 |
|----------|------|
| `backend/app.py` | 应用主入口 |
| `backend/content_routes.py` | 内容生成路由（新增language参数） |
| `backend/content_service.py` | 内容生成服务（新增语言处理） |
| `backend/db.py` | 数据库操作 |
| `backend/kb_routes.py` | 知识库路由 |
| `backend/kb_service.py` | 知识库服务 |
| `backend/overseas_search_adapter.py` | 海外搜索适配器 |
| `backend/scraper.py` | 爬虫服务 |

### 前端源码文件 (11个)
| 文件路径 | 说明 |
|----------|------|
| `src/api/index.js` | API 接口定义 |
| `src/components/KbCreateKnowledgeDialog.vue` | 创建知识库弹窗 |
| `src/components/KbTaskFloat.vue` | 知识库任务浮窗 |
| `src/views/KeywordSearchDetailPage.vue` | 查词详情页 |
| `src/views/KeywordSearchPage.vue` | 查词管理页 |
| `src/views/PublishAiWritePage.vue` | 智能生文页（**新增语言选择**） |
| `src/views/PublishContentLibraryDetailPage.vue` | 内容库详情页（**修复显示问题**） |
| `src/views/PublishInstructionPage.vue` | 指令库页（**新增{language}变量**） |
| `src/views/PublishKbDetailPage.vue` | 知识库详情页 |
| `src/views/RankingAnalysisPage.vue` | 排名分析页 |
| `src/views/SystemSettingsPage.vue` | 系统设置页 |
| `vite.config.js` | Vite 构建配置 |

### 前端构建产物 (dist目录 - 22个文件)
```
frontend/dist/
├── index.html
├── index-BsOCcwvy.js          # 主JS（含语言功能）
├── index-DQ1cusZP.css         # 主CSS
├── vendor-CtYndc5-.js         # Vue等依赖
├── vendor-element-Bx7HApdq.js # Element Plus JS
├── vendor-element-CMeMdHGs.css # Element Plus CSS
├── vendor-nHDhGvq6.css        # 其他样式
├── vendor-vue-DwUgstKA.js     # Vue Runtime
├── vendor-xlsx-D6ZulrnP.js    # Excel导出
└── assets/                    # 图标等静态资源
```

---

## 三、部署步骤

```bash
# 1. 备份现有版本（可选但推荐）
cp -r /path/to/backend /path/to/backend_backup_v1.1.1
cp -r /path/to/frontend/dist /path/to/frontend_dist_backup_v1.1.1

# 2. 上传后端文件
scp backend/*.py <服务器>:<后端路径>/

# 3. 上传前端构建产物
scp -r frontend/dist/* <服务器>:<前端静态目录>/

# 4. 重启后端服务
systemctl restart geo-backend
# 或
supervisorctl restart geo-backend

# 5. 清除浏览器缓存（如需）
# 用户按 Ctrl+Shift+R 强制刷新
```

---

## 四、验证检查项

- [ ] 智能生文页面显示"输出语言"选择卡片
- [ ] 语言下拉列表显示47种中文描述的语言选项
- [ ] 指令库新建指令时显示 `{language}` 变量按钮
- [ ] 选择非中文语言后生成的文章使用对应语言
- [ ] 内容库详情页正常显示AI生成的文章
- [ ] 后端日志无报错

---

## 五、回滚方案

如需回滚到 v1.1.1：
1. 恢复备份的后端文件
2. 恢复备份的前端 dist 目录
3. 重启后端服务
