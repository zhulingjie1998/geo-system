# -*- coding: utf-8 -*-
"""
终极方案：用正则找出所有包含非法字符的行，全部替换为英文
"""
import re

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed_count = 0

# 遍历所有行，查找并修复问题
for i, line in enumerate(lines):
    # 检查是否有非法字符（非打印字符、私有区字符等）
    has_invalid = False
    for ch in line:
        code = ord(ch)
        # 私有使用区字符 (U+E000-U+F8FF)
        if 0xE000 <= code <= 0xF8FF:
            has_invalid = True
            break
        # 兼容性字符区 (U+3200-U+32FF)
        if 0x3200 <= code <= 0x32FF:
            has_invalid = True
            break
    
    if has_invalid:
        print(f"第{i+1}行: 发现非法字符")
        print(f"  原始: {line[:80]}...")
        
        # 判断是docstring还是代码
        stripped = line.strip()
        
        # 如果是docstring开头或结尾，或者注释
        if '"""' in line or "'''" in line or stripped.startswith('#'):
            # 提取缩进
            indent = len(line) - len(line.lstrip())
            
            # 根据上下文生成合适的英文替代
            if '"""' in line:
                new_line = ' ' * indent + '"""TODO: fix docstring"""\n'
                # 保持原始换行状态
                if not line.endswith('\n'):
                    new_line = new_line.rstrip('\n')
            else:
                new_line = '\n'
            
            lines[i] = new_line
            fixed_count += 1
            print(f"  -> 替换")

print(f"\n共修复 {fixed_count} 行")

# 写回
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines))

# 验证
print("\n验证语法...")
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content2 = f.read()
try:
    ast.parse(content2)
    print("✓✓✓ 语法正确! ✓✓✓")
except SyntaxError as e:
    print(f"✗ 第 {e.lineno} 行: {e.msg}")
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content2.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content2.split(chr(10))[j][:100]}")
