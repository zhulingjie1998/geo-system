# -*- coding: utf-8 -*-
"""修复login函数的整个代码块缩进"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到185-210行，修复整个登录逻辑的缩进
# 正确的结构应该是：
#         raw_body = ...
#         logger.info(...)
#         username = ...
#         password = ...
#         if not username and not password:
#             pass
#         if raw_body:
#             try:
#                 parsed = ...
#             except Exception:
#                 pass
#         if not username and not password:
#             username = ...
#             password = ...

# 直接替换整个问题区域（185-210行）
new_block = [
    '            data = {}\n',
    '        raw_body = request.get_data(as_text=True)\n',
    "        logger.info('login request content_type=%s raw_body=%s', request.content_type, raw_body[:50])\n",
    '        username = (data.get("username") or "").strip()\n',
    '        password = data.get("password") or ""\n',
    '        if not username and not password:\n',
    '            pass\n',
    '        if raw_body:\n',
    '            try:\n',
    '                from urllib.parse import parse_qsl\n',
    '                parsed = dict(parse_qsl(raw_body, keep_blank_values=True))\n',
    '                username = (parsed.get("username") or "").strip()\n',
    '                password = (parsed.get("password") or "").strip()\n',
    '            except Exception:\n',
    '                pass\n',
    '        if not username and not password:\n',
    '            username = (request.form.get("username") or request.args.get("username") or "").strip()\n',
    '            password = (request.form.get("password") or request.args.get("password") or "")\n',
]

print(f"替换第185-201行 ({len(new_block)} 行)")
lines[184:201] = new_block

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("已替换!")

# 验证
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("✓ 语法正确!")
except SyntaxError as e:
    print(f"✗ 第 {e.lineno} 行错误: {e.msg}")
    for j in range(max(0, e.lineno-2), min(e.lineno+3, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:90]}")
