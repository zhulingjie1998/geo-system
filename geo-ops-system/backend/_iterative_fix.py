#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
迭代修复 app.py 的所有语法错误
"""
import py_compile
import re
from pathlib import Path

filepath = Path(r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py')

max_iterations = 50  # 最大修复次数

for iteration in range(max_iterations):
    print(f"\n=== 迭代 {iteration + 1} ===")
    
    # 尝试编译
    try:
        py_compile.compile(str(filepath), doraise=True)
        print("✅ 语法检查通过!")
        break
    except py_compile.PyCompileError as e:
        print(f"❌ 第 {e.lineno} 行: {e.msg}")
        
        if e.lineno is None:
            print("无法确定错误位置，停止")
            break
        
        # 读取文件
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        line_idx = e.lineno - 1
        if line_idx >= len(lines):
            print(f"行号超出范围 ({e.lineno} > {len(lines)})")
            break
            
        line = lines[line_idx]
        print(f"   原始: {line.rstrip()[:80]}")
        
        fixed = False
        
        # 模式1: 未闭合字符串 - 在行末添加引号
        if 'unterminated string' in str(e.msg).lower():
            # 找到最后一个引号位置
            last_quote = max(line.rfind('"'), line.rfind("'"))
            if last_quote != -1:
                # 在行末（换行符前）添加相同类型的引号
                quote_char = line[last_quote]
                if line.endswith('\n'):
                    lines[line_idx] = line[:-1] + quote_char + '\n'
                else:
                    lines[line_idx] = line + quote_char
                fixed = True
                print(f"   修复: 添加闭合引号 '{quote_char}'")
        
        # 模式2: 多余的字符在行末 (如 :")
        elif e.lineno and line_idx < len(lines):
            stripped = line.rstrip('\n')
            # 移除行末可能的垃圾字符
            new_line = re.sub(r'[\s:"]+$', '', stripped)
            if new_line != stripped:
                if not new_line.endswith((':', ',', ')', ']', '}', ':')):
                    # 保持原样如果结尾不正常
                    pass
                else:
                    lines[line_idx] = new_line + '\n'
                    fixed = True
                    print(f"   修复: 清理行末多余字符")
            
            # 特殊处理: for ch in ...):"
            if 'for ch in' in line and '):"' in line:
                lines[line_idx] = line.replace('):"', '):\n')
                fixed = True
                print(f"   修复: 移除多余的 :\"")
        
        # 模式3: invalid syntax (可能是缩进或结构问题)
        elif 'invalid syntax' in str(e.msg).lower():
            # 检查是否有多余的 else/冒号等
            if line.strip() == 'else:':
                # 可能是多余的 else
                print(f"   警告: 可能需要手动处理此行")
            elif line.strip().endswith(':') and len(line.strip()) < 10:
                # 短行以冒号结尾，可能有问题
                pass
        
        if fixed:
            # 写回文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print("   ✅ 已保存修复")
        else:
            print(f"   ⚠️ 无法自动修复此错误")
            # 显示上下文
            start = max(0, line_idx - 2)
            end = min(len(lines), line_idx + 3)
            print("\n   上下文:")
            for i in range(start, end):
                marker = ">>>" if i == line_idx else "   "
                print(f"   {marker} {i+1}: {lines[i].rstrip()[:70]}")

print("\n" + "=" * 50)
if iteration < max_iterations - 1:
    print("✅ 所有语法错误已修复!")
else:
    print("⚠️ 达到最大迭代次数，可能仍有错误")
