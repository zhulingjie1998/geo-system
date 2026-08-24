# -*- coding: utf-8 -*-
"""一次性修复所有剩余问题"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 问题1: 第3127行的 """TODO: fix docstring""" 导致后面代码被吞掉
for i in range(len(lines)):
    if '"""TODO: fix docstring"""' in lines[i]:
        print(f"删除第{i+1}行: {lines[i].rstrip()}")
        del lines[i]
        break

# 问题2: 第2659行 _REPORT_TYPE_LABELS 字典未闭合
# 需要查看这行附近的内容
print("\n=== 查看第2655-2665行 ===")
for i in range(2654, min(2665, len(lines))):
    print(f"{i+1}: {lines[i].rstrip()[:120]}")
