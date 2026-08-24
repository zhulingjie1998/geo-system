# -*- coding: utf-8 -*-
"""扫描未闭合的三引号"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 扫描三引号
in_triple = False
triple_start = None

for i in range(len(lines)):
    line = lines[i]
    
    # 检查三引号出现次数（简化处理）
    count_triple_double = line.count('"""')
    count_triple_single = line.count("'''")
    
    if in_triple:
        if '"""' in line and triple_start[0] == '"':
            # 可能闭合了
            idx = line.index('"""')
            after = line[idx+3:]
            if '"""' not in after:  # 确保没有更多
                print(f"第{i+1}行: 闭合三引号 (从第{triple_start[1]}行开始)")
                in_triple = False
                triple_start = None
    else:
        if '"""' in line:
            # 检查这行是否有配对的三引号
            first = line.index('"""')
            rest = line[first+3:]
            if '"""' not in rest:  # 未闭合
                in_triple = True
                triple_start = ('"', i+1)
                print(f"\n第{i+1}行: 开始未闭合的三引号")
                print(f"  内容: {line.rstrip()[:100]}")

if in_triple:
    print(f"\n⚠ 文件结束时仍有未闭合的三引号! 开始于第{triple_start[1]}行")

# 也检查单引号三引号
in_triple = False
for i in range(len(lines)):
    line = lines[i]
    if "'''" in line:
        first = line.index("'''")
        rest = line[first+3:]
        if "'''" not in rest:
            if not in_triple:
                in_triple = True
                print(f"\n第{i+1}行: 开始未闭合的 ''' ")
            else:
                in_triple = False
                print(f"第{i+1}行: 闭合 '''")
