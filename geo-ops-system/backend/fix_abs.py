# -*- coding: utf-8 -*-
import os

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
print(f"File exists: {os.path.exists(filepath)}")
print(f"File size: {os.path.getsize(filepath)} bytes")

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"\nLine 66 (index 65):")
print(repr(lines[65][:120]))
print(f"\nLine 67 (index 66):")
print(repr(lines[66][:120]))

# Replace lines 65-72 (0-indexed) with correct code
new_lines = [
    '    import permissions as _perm\n',
    '    # 首次启动确保内置 super_admin 角色存在\n',
    '    if not db.get_role_by_code("super_admin"):\n',
    '        db.create_role("超级管理员", "super_admin", data_scope="all",\n',
    '                       description="系统内置超级管理员",\n',
    '                       page_keys=list(_perm.PAGE_KEYS), is_builtin=1)\n',
    '    init_pw = (os.environ.get("GEO_INIT_ADMIN_PW") or "").strip() or "admin123"\n',
]

print(f"\nReplacing lines 65-72 with {len(new_lines)} new lines...")
lines[65:73] = new_lines

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("Write complete!")

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    check = f.readlines()
print(f"\nVerification - Line 66: {check[65].rstrip()}")
print(f"Verification - Line 67: {check[66].rstrip()}")

# Syntax check
import ast
try:
    ast.parse(''.join(check))
    print("\n✓ SYNTAX OK!")
except SyntaxError as e:
    print(f"\n✗ Syntax Error at line {e.lineno}: {e.msg}")
