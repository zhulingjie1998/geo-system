# -*- coding: utf-8 -*-
"""Fix line 67 indentation error in app.py"""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines: {len(lines)}')
print(f'Line 67: {repr(lines[66][:120])}')

# The problem is that comments are merged with code on same line
# Line 67 should be: if not db.get_role_by_code("super_admin"):
# But it has comment from previous line attached

# Fix line 67 area (0-indexed: 65-71)
if len(lines) > 70:
    # Replace lines 65-72 with corrected version
    new_lines = lines[:65]  # Keep everything before line 66
    
    # Add corrected lines
    new_lines.append('    import permissions as _perm\n')
    new_lines.append('    # 首次启动确保内置 super_admin 角色存在\n')
    new_lines.append('    if not db.get_role_by_code("super_admin"):\n')
    new_lines.append('        db.create_role("超级管理员", "super_admin", data_scope="all",\n')
    new_lines.append('                       description="系统内置超级管理员",\n')
    new_lines.append('                       page_keys=list(_perm.PAGE_KEYS), is_builtin=1)\n')
    new_lines.append('    init_pw = (os.environ.get("GEO_INIT_ADMIN_PW") or "").strip() or "admin123"\n')
    
    # Skip old lines 65-72 and add rest
    if len(lines) > 73:
        new_lines.extend(lines[73:])
    
    # Write back
    with open('app.py', 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(new_lines)
    
    print(f'Fixed! New total lines: {len(new_lines)}')
    
    # Verify
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            compile(f.read(), 'app.py', 'exec')
        print('Syntax OK!')
    except SyntaxError as e:
        print(f'Syntax Error: {e}')
else:
    print('File too short or unexpected format')
