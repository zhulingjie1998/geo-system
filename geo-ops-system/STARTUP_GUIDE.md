# GEO 运营系统 - 启动指南

## 🚀 快速启动

### 方法一：双击启动（推荐）
```
双击 backend\start.bat
```
浏览器访问: http://127.0.0.1:7007

### 方法二：命令行启动
```bash
cd backend
python dev_server.py
```

### 方法三：使用根目录脚本
```bash
python _run_server.py
```

---

## ⚙️ 首次配置

### 1. 配置数据库
编辑 `backend/.env` 文件：
```ini
GEO_DB_HOST=127.0.0.1      # MySQL 地址
GEO_DB_PORT=3306            # MySQL 端口
GEO_DB_USER=root            # MySQL 用户名
GEO_DB_PASSWORD=your_password  # MySQL 密码
GEO_DB_NAME=waimao_geo      # 数据库名称
```

### 2. 默认登录信息
- 用户名: `admin`
- 密码: `admin123`（首次启动时设置）

> ⚠️ 登录后请立即修改密码！

---

## 🔧 常见问题解决

### 问题 1: 端口被占用
```bash
# 查找占用端口的进程
netstat -ano | findstr :7007

# 结束进程（替换 PID）
taskkill /PID <进程ID> /F
```

### 问题 2: 数据库连接失败
- 确认 MySQL 已启动
- 检查 .env 中的数据库配置是否正确
- 确认数据库已创建: `CREATE DATABASE waimao_geo CHARACTER SET utf8mb4;`

### 问题 3: 缺少依赖
```bash
cd backend
pip install -r requirements.txt
```

### 问题 4: Python 版本过低
需要 Python 3.9 或更高版本:
```bash
python --version
```

---

## 📁 文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `backend/start.bat` | Windows 双击启动脚本 |
| `backend/dev_server.py` | 开发服务器启动脚本 |
| `backend/auto_start.vbs` | 开机自启脚本（可选） |
| `_run_server.py` | 根目录启动脚本 |
| `backend/.env` | 环境配置文件 |
| `backend/.env.example` | 配置模板 |

---

## 💡 开发建议

1. **修改代码后**: 开发服务器会自动重载（debug模式）
2. **查看日志**: 控制台输出 + `logs/` 目录
3. **调试问题**: 使用 debug=True 可看到详细错误信息

---

## 🔒 安全提醒

- 生产环境务必修改 `GEO_FLASK_SECRET`
- 删除或注释 `GEO_COOKIE_INSECURE=1`
- 使用强密码替代默认的 admin123
