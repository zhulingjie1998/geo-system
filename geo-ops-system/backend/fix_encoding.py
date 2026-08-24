# -*- coding: utf-8 -*-
"""Comprehensive encoding fix for app.py"""

# Read the file
with open('app.py', 'rb') as f:
    raw = f.read()

# Remove BOM if present
if raw[:3] == b'\xef\xbb\xbf':
    raw = raw[3:]
    print('Removed UTF-8 BOM')

# Decode as utf-8, ignore errors
text = raw.decode('utf-8', errors='ignore')

# Comprehensive fixes for mojibake patterns (GBK->UTF-8 double-encoding)
fixes = {
    '瓒呯骇绠＄悊鍛?': '超级管理员',
    '绯荤粺鍐呯疆瓒呯骇绠＄悊鍛?': '系统内置超级管理员',
    '鎷ユ湁鍏ㄩ儴椤甸潰涓庡叏閮ㄦ暟鎹寖鍥?': '拥有全部页面与全部数据范围',
}

fixed_count = 0
for wrong, right in fixes.items():
    count = text.count(wrong)
    if count > 0:
        text = text.replace(wrong, right)
        print(f'Fixed: {wrong} -> {right} ({count})')
        fixed_count += count

# Fix line endings
text = text.replace('\r\n', '\n')

# Write back
with open('app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)

print(f'Done! Fixed {fixed_count} issues. Size: {len(text)} chars')

# Verify syntax
try:
    compile(text, 'app.py', 'exec')
    print('Syntax OK')
except SyntaxError as e:
    print(f'Syntax Error line {e.lineno}: {e.msg}')
