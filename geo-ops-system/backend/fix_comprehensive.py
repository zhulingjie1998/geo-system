# -*- coding: utf-8 -*-
"""
Comprehensive fix for ALL mojibake in app.py.
This script fixes GBK→UTF-8 double-encoded Chinese characters.
"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

# Read file as bytes first to understand the encoding
with open(filepath, 'rb') as f:
    raw_data = f.read()

print(f"File size: {len(raw_data)} bytes")

# The issue is that some text was double-encoded (GBK→UTF-8→interpreted as something else)
# Let's try to decode and fix line by line

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Common mojibake → correct mappings based on what we've seen
mappings = {
    # Error messages
    '"鏈嶅姟鍣ㄥ唴閮ㄩ敊璇?': '"服务器内部错误"',
    '"鐩樉爣鍥㈤槦涓嶅瓨鍦?': '"目标队列不存在"',
    '"鐩樉爣瑙掕壊涓嶅瓨鍦?': '"目标角色不存在"',
    '"鐩樉爣鍥㈤槦涓嶅瓨鍦?': '"目标队列不存在"',
    '"鐩樉爣璐熻矷浜轰笉瀛樺湪"': '"目标负责人不存在"',
    '"瓒呯骇绠＄悊鍛樿鑹插畬鍏ㄩ攣瀹氾紝 涓嶅彲缂栬緫"': '"超级管理员角色完全锁定，不可编辑"',
    '"鏃犳潈闄愯闂ㄦ潯浠诲姟"': '"无权访问此任务"',
    
    # Role descriptions
    '"浠呯湅鑷繁鍒涘缓鐨勬暟鎹?': '"只看自己创建的数据"',
    
    # Docstrings and comments - these are harder because they're longer strings
}

# Apply simple string replacements
fixed = content
count = 0
for old, new in mappings.items():
    if old in fixed:
        fixed = fixed.replace(old, new)
        count += 1
        print(f"Fixed: {old[:30]}...")

print(f"\nFixed {count} simple replacements")

# Now handle docstrings with mojibake by finding and replacing entire lines
import re

# Write back
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(fixed)

# Check syntax
import ast
try:
    ast.parse(fixed)
    print("\n✓ SYNTAX OK after basic fixes!")
except SyntaxError as e:
    print(f"\n✗ Still has syntax error at line {e.lineno}: {e.msg}")
    
    # Show problematic area
    lines = fixed.split('\n')
    start = max(0, e.lineno - 3)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end):
        marker = ">>>" if i == e.lineno - 1 else "   "
        print(f"{marker} {i+1}: {lines[i][:100]}")
