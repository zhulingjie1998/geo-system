# -*- coding: utf-8 -*-
"""
Fix app.py encoding issues by reading lines and replacing the problematic section.
"""

import sys

filepath = 'app.py'

# Read with utf-8
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Line 66 (index 65): {repr(lines[65][:80])}")
print(f"Line 67 (index 66): {repr(lines[66][:80])}")

# The fix: Replace lines 65-72 (0-indexed) with correct code
# Lines to replace: from "# 棣栨..." (line 66) to "init_pw = ..." (line 73)
new_lines_65_to_72 = [
    '    import permissions as _perm\n',
    '    # 首次启动确保内置 super_admin 角色存在\n',
    '    if not db.get_role_by_code("super_admin"):\n',
    '        db.create_role("超级管理员", "super_admin", data_scope="all",\n',
    '                       description="系统内置超级管理员",\n',
    '                       page_keys=list(_perm.PAGE_KEYS), is_builtin=1)\n',
    '    init_pw = (os.environ.get("GEO_INIT_ADMIN_PW") or "").strip() or "admin123"\n',
]

# Replace lines 65-72 (0-indexed)
lines[65:73] = new_lines_65_to_72

# Write back
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

print("\nFile fixed! Verifying...")

# Verify by reading back
with open(filepath, 'r', encoding='utf-8') as f:
    verify_lines = f.readlines()

print(f"New line 66: {verify_lines[65].rstrip()}")
print(f"New line 67: {verify_lines[66].rstrip()}")
print(f"New line 68: {verify_lines[67].rstrip()}")

# Syntax check
import ast
try:
    ast.parse(''.join(verify_lines))
    print("\n✓ Python syntax OK!")
except SyntaxError as e:
    print(f"\n✗ Syntax error: {e}")
