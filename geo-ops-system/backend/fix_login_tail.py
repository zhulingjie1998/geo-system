# -*- coding: utf-8 -*-
"""修复login函数的整个尾部结构"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 查看问题区域
print("\n=== 修复前 第235-275行 ===")
for i in range(234, 275):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 问题：
# 1. 第240行: }) 和 except Exception: 混在一起
# 2. 第241-242行: except块内容（也有乱码）
# 3. 第245-270行: 大量无用的pass
#
# 正确的结构应该是：
#     return jsonify({...})
# except Exception:
#     logger.exception(...)
#     return jsonify(...), 500
#
# 然后直接是 @app.post("/api/auth/logout")

# 方案：替换第235-270行为正确的结构
new_lines = [
    '                         "isSuperAdmin": session["role"] == "super_admin",\n',
    '                         "role": session["role"],\n',
    '                         "roleName": session.get("role_name", ""),\n',
    '                         "dataScope": session.get("data_scope", "self"),\n',
    '                         "pages": session.get("pages", []),\n',
    '                         "permissions": session.get("pages", [])\n',
    '                     })\n',
    '    except Exception:\n',
    '        logger.exception("api_auth_login failed")\n',
    '        return jsonify({"error": "Internal error"}), 500\n',
    '\n',
    '\n',
]

print(f"\n替换第235-270行 ({len(new_lines)} 行)")
lines[234:270] = new_lines

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\n=== 修复后 ===")
for i in range(234, 255):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n✓✓✓ 语法正确! ✓✓✓")
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
