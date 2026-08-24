# -*- coding: utf-8 -*-
"""清理第2680-2762行的孤儿代码和空行"""

filepath = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}")

# 问题区域：2680-2762
# - 第2703行: 孤儿代码 **_gate_ctx_for_account(account_id),
# - 第2718行: 孤儿代码 **_gate_ctx_for_account(account_id),
# - 第2760行: pass（导致函数体提前结束）
# - 大量空行

# 方案：删除2680-2757行（空行和孤儿代码），保留从@app.get开始的内容

# 先查看要保留的起始位置
print("\n查找 @app.get 位置...")
start_idx = None
for i in range(2750, 2762):
    if i < len(lines) and '@app.get' in lines[i]:
        start_idx = i
        print(f"找到 @app.get 在第 {i+1} 行")
        break

if start_idx:
    # 删除2680到start_idx之前的所有行（空行和孤儿代码）
    print(f"删除第2681-{start_idx}行 ({start_idx - 2680} 行)")
    del lines[2680:start_idx]
    
    # 删除pass行（现在应该在2760附近，需要重新找）
    # 查找 spa_share_report_gate 函数中的 pass
    for i in range(len(lines)):
        if 'def spa_share_report_gate' in lines[i]:
            print(f"\n找到函数定义在第{i+1}行")
            # 查看接下来的几行
            for j in range(i+1, min(i+5, len(lines))):
                print(f"  {j+1}: {lines[j].rstrip()}")
                if lines[j].strip() == 'pass':
                    # 删除这行pass
                    del lines[j]
                    print(f"  -> 删除了第{j+1}行的pass")
                    break
            break

with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# 验证
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
    for j in range(max(0, e.lineno-3), min(e.lineno+4, len(content.split('\n')))):
        marker = ">>>" if j == e.lineno-1 else "   "
        print(f"{marker} {j+1}: {content.split(chr(10))[j][:100]}")
