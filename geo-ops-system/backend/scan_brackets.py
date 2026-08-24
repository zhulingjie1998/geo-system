# -*- coding: utf-8 -*-
"""扫描文件查找未闭合的括号/字符串"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 扫描每一行，跟踪括号/引号状态
paren_stack = []
bracket_stack = []
brace_stack = []
in_string = None  # None, '"', "'", '"""', "'''"
triple_quote_start = None
line_errors = []

for i, line in enumerate(lines):
    line_num = i + 1
    stripped = line.strip()
    
    # 跳过注释行（但要注意字符串内的注释）
    j = 0
    while j < len(line):
        char = line[j]
        
        # 处理字符串
        if in_string:
            if char == '\\':
                j += 2  # 跳过转义字符
                continue
            if (char == '"' and ('"' in in_string)) or (char == "'" and ("'" in in_string)):
                if in_string.startswith('"""') or in_string.startswith("'''"):
                    if line[j:j+3] == in_string[:3]:
                        in_string = None
                        j += 3
                        continue
                else:
                    in_string = None
            j += 1
            continue
        
        # 检查三引号
        if line[j:j+3] in ['"""', "'''"]:
            in_string = line[j:j+3]
            triple_quote_start = line_num
            j += 3
            continue
            
        # 检查单引号
        if char in ['"', "'"]:
            in_string = char
            j += 1
            continue
            
        # 括号计数
        if char == '(':
            paren_stack.append((line_num, j))
        elif char == ')':
            if paren_stack:
                paren_stack.pop()
            else:
                if line_num not in [e[0] for e in line_errors]:
                    line_errors.append((line_num, f"多余的 )"))
                    
        elif char == '[':
            bracket_stack.append((line_num, j))
        elif char == ']':
            if bracket_stack:
                bracket_stack.pop()
                
        elif char == '{':
            brace_stack.append((line_num, j))
        elif char == '}':
            if brace_stack:
                brace_stack.pop()
                
        j += 1

print(f"\n=== 未闭合的括号 ===")
if paren_stack:
    print(f"未闭合的 (: {len(paren_stack)} 个:")
    for ln, col in paren_stack[-5:]:
        print(f"  第{ln}行第{col}列: {lines[ln-1].rstrip()[:80]}")
else:
    print("() - 全部闭合 ✓")

if bracket_stack:
    print(f"\n未闭合的 [: {len(bracket_stack)} 个:")
    for ln, col in bracket_stack[-5:]:
        print(f"  第{ln}行第{col}列: {lines[ln-1].rstrip()[:80]}")
else:
    print("\n[] - 全部闭合 ✓")

if brace_stack:
    print(f"\n未闭合的 {{: {len(brace_stack)} 个:")
    for ln, col in brace_stack[-5:]:
        print(f"  第{ln}行第{col}列: {lines[ln-1].rstrip()[:80]}")
else:
    print("\n{} - 全部闭合 ✓")

if in_string:
    print(f"\n⚠ 未闭合的字符串! 类型: {in_string}, 开始于第 {triple_quote_start} 行附近")
    # 显示开始位置附近的代码
    start = max(0, triple_quote_start - 3) if triple_quote_start else 2650
    for k in range(start, min(start + 10, len(lines))):
        marker = ">>>" if k == triple_quote_start - 1 else "   "
        print(f"{marker} {k+1}: {lines[k].rstrip()[:100]}")

if line_errors:
    print(f"\n其他错误: {line_errors}")
