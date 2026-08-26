#!/bin/bash
#=============================================================================
# GEO 运营系统 — Git 拉取部署脚本
# 用法: bash deploy.sh
# 功能: 从 GitHub 拉取最新代码 → 构建前端 → 重启 Gunicorn
#=============================================================================

set -e

# ===== 配置（按实际环境修改）=====
PROJECT_DIR="/www/wwwroot/GEO"                    # Git 仓库根目录
SOURCE_DIR="$PROJECT_DIR/geo-ops-system"           # Git 拉取的代码在此子目录
BACKEND_DIR="$SOURCE_DIR/backend"
FRONTEND_DIR="$SOURCE_DIR/frontend"
GIT_REMOTE="origin"
GIT_BRANCH="main"
GUNICORN_BIN="/www/server/pyporject_evn/GEO/bin/gunicorn"
PYTHON_BIN="/www/server/pyporject_evn/GEO/bin/python3"
# =================================

cd "$PROJECT_DIR"

echo ""
echo "============================================"
echo "  GEO 运营系统 — Git 部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ----- 1. 拉取最新代码 -----
echo "[1/6] 拉取最新代码..."
git fetch "$GIT_REMOTE" "$GIT_BRANCH"
git reset --hard "$GIT_REMOTE/$GIT_BRANCH"
echo "  ✅ 代码已更新到最新版本"
git log --oneline -1
echo ""

# ----- 2. 确保 .env 存在 -----
echo "[2/6] 检查后端 .env 配置..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    # 尝试从旧目录复制
    if [ -f "$PROJECT_DIR/backend/.env" ]; then
        cp "$PROJECT_DIR/backend/.env" "$BACKEND_DIR/.env"
        echo "  ✅ 已从旧目录复制 .env"
    else
        echo "  ❌ 未找到 .env，请手动创建 $BACKEND_DIR/.env"
        exit 1
    fi
else
    echo "  ✅ .env 已存在"
fi
echo ""

# ----- 3. 安装后端依赖 -----
echo "[3/6] 检查后端依赖..."
cd "$BACKEND_DIR"
if [ -f "requirements.txt" ]; then
    "$PYTHON_BIN" -m pip install -r requirements.txt -q 2>/dev/null || true
    echo "  ✅ 后端依赖已安装"
else
    echo "  ⚠️  未找到 requirements.txt，跳过"
fi
echo ""

# ----- 4. 构建前端 -----
echo "[4/6] 构建前端..."
cd "$FRONTEND_DIR"

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    if command -v pnpm &>/dev/null; then
        pnpm install
    elif [ -f "pnpm-lock.yaml" ]; then
        npm install -g pnpm 2>/dev/null || true
        pnpm install
    else
        npm install
    fi
fi

# 构建
if command -v pnpm &>/dev/null; then
    pnpm build
else
    npx vite build
fi
echo "  ✅ 前端构建完成"
echo ""

# ----- 5. 复制 dist 到 backend/static -----
echo "[5/6] 部署前端静态文件..."
rm -rf "$BACKEND_DIR/static"
cp -r "$FRONTEND_DIR/dist" "$BACKEND_DIR/static"
echo "  ✅ 静态文件已部署到 backend/static"
echo ""

# ----- 6. 重启 Gunicorn -----
echo "[6/6] 重启 Gunicorn..."
cd "$BACKEND_DIR"

# 杀掉旧的 gunicorn 进程
OLD_PIDS=$(ps aux | grep gunicorn | grep "gunicorn_conf.py" | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PIDS" ]; then
    echo "  停止旧进程: $OLD_PIDS"
    echo "$OLD_PIDS" | xargs kill 2>/dev/null || true
    sleep 2
fi

# 启动新的 gunicorn
"$GUNICORN_BIN" -c gunicorn_conf.py app:app --daemon
sleep 3

# 验证启动
NEW_PID=$(ps aux | grep gunicorn | grep "gunicorn_conf.py" | grep -v grep | head -1 | awk '{print $2}')
if [ -n "$NEW_PID" ]; then
    echo "  ✅ Gunicorn 已启动 (PID: $NEW_PID)"
else
    echo "  ❌ Gunicorn 启动失败！检查日志: tail -50 logs/gunicorn_error.log"
    exit 1
fi
echo ""

# ----- 验证 -----
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "验证接口:"
curl -s http://127.0.0.1:7006/api/auth/me || echo "  (接口未响应)"
echo ""
