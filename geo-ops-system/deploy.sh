#!/bin/bash
#=============================================================================
# GEO 运营系统 — Git 拉取部署脚本
# 用法: bash deploy.sh
# 功能: 从 GitHub 拉取最新代码 → 构建前端 → 重启 Gunicorn
#=============================================================================

set -e

# ===== 配置（按实际环境修改）=====
PROJECT_DIR="/www/wwwroot/GEO"                    # 项目根目录
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
GIT_REMOTE="origin"
GIT_BRANCH="main"
GUNICORN_BIN="/www/server/pyporject_evn/GEO/bin/gunicorn"
PYTHON_BIN="/www/server/pyporject_evn/GEO/bin/python3"
NODE_BIN="/usr/bin/node"                           # 如果 node 不在默认 PATH
PNPM_BIN=""                                        # 如果 pnpm 不在默认 PATH，填完整路径
# =================================

cd "$PROJECT_DIR"

echo ""
echo "============================================"
echo "  GEO 运营系统 — Git 部署"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ----- 1. 拉取最新代码 -----
echo "[1/5] 拉取最新代码..."
git fetch "$GIT_REMOTE" "$GIT_BRANCH"
git reset --hard "$GIT_REMOTE/$GIT_BRANCH"
echo "  ✅ 代码已更新到最新版本"
git log --oneline -1
echo ""

# ----- 2. 安装后端依赖 -----
echo "[2/5] 检查后端依赖..."
cd "$BACKEND_DIR"
if [ -f "requirements.txt" ]; then
    "$PYTHON_BIN" -m pip install -r requirements.txt -q 2>/dev/null || true
    echo "  ✅ 后端依赖已安装"
else
    echo "  ⚠️  未找到 requirements.txt，跳过"
fi
echo ""

# ----- 3. 构建前端 -----
echo "[3/5] 构建前端..."
cd "$FRONTEND_DIR"

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    if [ -n "$PNPM_BIN" ]; then
        "$PNPM_BIN" install
    elif command -v pnpm &>/dev/null; then
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
elif [ -n "$PNPM_BIN" ]; then
    "$PNPM_BIN" build
else
    npx vite build
fi
echo "  ✅ 前端构建完成"
echo ""

# ----- 4. 复制 dist 到 backend/static -----
echo "[4/5] 部署前端静态文件..."
rm -rf "$BACKEND_DIR/static"
cp -r "$FRONTEND_DIR/dist" "$BACKEND_DIR/static"
echo "  ✅ 静态文件已部署到 backend/static"
echo ""

# ----- 5. 重启 Gunicorn -----
echo "[5/5] 重启 Gunicorn..."
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
echo "当前版本:"
git log --oneline -1
git describe --tags 2>/dev/null || echo "  (无标签)"
echo ""
