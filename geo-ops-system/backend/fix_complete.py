# -*- coding: utf-8 -*-
"""一次性修复所有剩余问题"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 问题1: _REPORT_TYPE_LABELS 字典未闭合 (第2658行附近)
for i in range(len(lines)):
    if '_REPORT_TYPE_LABELS' in lines[i]:
        print(f"找到 _REPORT_TYPE_LABELS 在第{i+1}行")
        # 找到字典的结尾（最后一个逗号后添加}）
        # 查看接下来的几行找到字典结束位置
        for j in range(i, min(i+10, len(lines))):
            print(f"  {j+1}: {lines[j].rstrip()[:100]}")
            # 找到最后一个有内容的行
            if j > i and lines[j].strip().endswith(',') and 'GEO' in lines[j]:
                print(f"  -> 字典在第{j+1}行结束，需要添加 }}")
                # 在这行后面插入 }
                lines.insert(j+1, "}\n")
                break
        break

# 问题2: 修复乱码字符串中的括号问题
# 第2918行附近的乱码字符串
for i in range(len(lines)):
    if i < len(lines) and 'themed HTML' in lines[i] and 'chromium' in lines[i]:
        print(f"\n修复第{i+1}行的乱码字符串...")
        # 这行包含乱码和未闭合的括号，替换为正确的版本
        old_line = lines[i]
        # 提取缩进
        indent = len(lines[i]) - len(lines[i].lstrip())
        new_line = ' ' * indent + '"""themed HTML → chromium 渲染 PDF(子进程隔离) → 附件下载。"""\n'
        lines[i] = new_line
        print(f"  原始: {old_line.rstrip()[:80]}...")
        print(f"  新:   {new_line.rstrip()}")

# 第3097行附近的乱码
for i in range(len(lines)):
    if i < len(lines) and '[AI' in lines[i] and 'API Key' in lines[i]:
        print(f"\n修复第{i+1}行的乱码字符串...")
        indent = len(lines[i]) - len(lines[i].lstrip())
        new_line = ' ' * indent + 'print(f"[AI优化] 错误: API Key未配置")\n'
        lines[i] = new_line

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证语法
import ast
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
try:
    ast.parse(content)
    print("\n" + "="*50)
    print("✓✓✓ 语法完全正确! app.py 修复成功! ✓✓✓")
    print("="*50)
except SyntaxError as e:
    print(f"\n✗ 第 {e.lineno} 行: {e.msg}")
    content_lines = content.split('\n')
    for j in range(max(0, e.lineno-5), min(e.lineno+6, len(content_lines))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content_lines[j][:120]}")
