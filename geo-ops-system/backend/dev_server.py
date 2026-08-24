"""
GEO 运营系统 - 开发服务器启动脚本
双击运行或执行: python dev_server.py

功能:
- 自动检查依赖
- 加载环境配置
- 启动 Flask 开发服务器 (端口 7007)
- 处理常见启动错误
"""

import sys
import os
import subprocess

# 设置工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

def check_python_version():
    """检查 Python 版本"""
    if sys.version_info < (3, 9):
        print("[ERROR] 需要 Python 3.9 或更高版本")
        print(f"  当前版本: {sys.version}")
        return False
    print(f"[OK] Python 版本: {sys.version.split()[0]}")
    return True

def check_dependencies():
    """检查必要的依赖包"""
    required = ['flask', 'pymysql', 'werkzeug']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"[WARN] 缺少依赖: {', '.join(missing)}")
        print("  正在安装...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
        print("[OK] 依赖已安装")
    else:
        print("[OK] 所有依赖已满足")
    
    return True

def load_env():
    """加载环境变量"""
    env_file = os.path.join(SCRIPT_DIR, '.env')
    if os.path.exists(env_file):
        print(f"[OK] 加载环境配置: {env_file}")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())
    else:
        print(f"[INFO] 未找到 .env 文件，使用默认配置")
        # 设置默认值
        os.environ.setdefault('GEO_DB_HOST', '127.0.0.1')
        os.environ.setdefault('GEO_DB_PORT', '3306')
        os.environ.setdefault('GEO_DB_USER', 'geo_system')
        os.environ.setdefault('GEO_DB_PASSWORD', '')
        os.environ.setdefault('GEO_DB_NAME', 'geo_system')
        os.environ.setdefault('GEO_FLASK_SECRET', 'dev-secret-key-change-me')
        os.environ.setdefault('GEO_COOKIE_INSECURE', '1')

def start_server():
    """启动服务器"""
    print("\n" + "="*50)
    print("  GEO 运营系统 - 开发服务器")
    print("="*50)
    print(f"  地址: http://127.0.0.1:7007")
    print(f"  工作目录: {SCRIPT_DIR}")
    print("="*50 + "\n")
    
    # 导入并启动 Flask 应用
    try:
        from app import app
        
        # 测试数据库连接
        print("[INFO] 检查数据库连接...")
        try:
            from db import get_conn
            conn = get_conn()
            conn.close()
            print("[OK] 数据库连接成功")
        except Exception as e:
            print(f"[WARN] 数据库连接失败: {e}")
            print("  服务器将启动，但部分功能可能不可用")
        
        # 启动服务器
        print("\n[INFO] 启动服务器...")
        print("  按 Ctrl+C 停止服务器\n")
        
        # 启动定时任务调度器
        try:
            from scheduled_task_scheduler import start_scheduler
            start_scheduler()
            print("[OK] 定时任务调度器已启动")
        except Exception as e:
            print(f"[WARN] 定时任务调度器启动失败: {e}")
        
        app.run(
            host='0.0.0.0',
            port=7008,  # Changed from 7007 to avoid conflicts
            debug=True,
            use_reloader=False,  # 避免重载问题
            threaded=True
        )
        
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {e}")
        print("\n常见解决方案:")
        print("  1. 检查 MySQL 是否运行")
        print("  2. 检查 .env 中的数据库配置")
        print("  3. 执行: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """主函数"""
    print("\n正在初始化...\n")
    
    # 检查环境
    if not check_python_version():
        sys.exit(1)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 加载环境变量
    load_env()
    
    # 启动服务器
    if not start_server():
        sys.exit(1)

if __name__ == '__main__':
    main()
