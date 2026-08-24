#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全面诊断 app.py 的编码和语法问题
- 检测文件编码
- 找出所有语法错误位置
- 分析字符串损坏模式
- 统计损坏程度
"""

import os
import re
from pathlib import Path

filepath = Path(r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py')

print("=" * 70)
print("app.py 全面诊断报告")
print("=" * 70)

# 1. 文件基本信息
print("\n【1. 文件基本信息】")
size = filepath.stat().st_size
print(f"  文件大小: {size:,} bytes ({size/1024:.1f} KB)")
print(f"  修改时间: {filepath.stat().st_mtime}")

# 2. 编码检测
print("\n【2. 编码检测】")

# 尝试不同编码读取
encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1', 'cp1252']
encoding_results = {}

for enc in encodings_to_try:
    try:
        with open(filepath, 'r', encoding=enc) as f:
            content = f.read()
            # 检查是否有替换字符（表示解码错误）
            has_replacement = '\ufffd' in content
            encoding_results[enc] = {
                'success': True,
                'has_replacement': has_replacement,
                'length': len(content)
            }
    except (UnicodeDecodeError, UnicodeError) as e:
        encoding_results[enc] = {'success': False, 'error': str(e)}

for enc, result in encoding_results.items():
    if result['success']:
        status = "✅ 成功"
        if result.get('has_replacement'):
            status += " (含替换字符)"
        print(f"  {enc:12s}: {status} - {result['length']} 字符")
    else:
        print(f"  {enc:12s}: ❌ 失败 - {result.get('error', '')[:50]}")

# 3. 使用最佳编码读取并分析
print("\n【3. 语法错误分析】")
best_encoding = 'utf-8'
with open(filepath, 'r', encoding=best_encoding) as f:
    content = f.read()

# 尝试编译
import py_compile
import tempfile
try:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding=best_encoding) as tmp:
        tmp.write(content)
        tmp_name = tmp.name
    py_compile.compile(tmp_name, doraise=True)
    print("  ✅ 语法检查通过!")
except py_compile.PyCompileError as e:
    print(f"  ❌ 语法错误:")
    print(f"     位置: 第 {e.lineno} 行")
    print(f"     类型: {e.msg}")
    if e.text:
        print(f"     内容: {repr(e.text[:100])}")

# 4. 使用 tokenize 详细分析
print("\n【4. Tokenize 分析】")
import tokenize
import io

try:
    tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
    print("  ✅ Tokenize 成功")
    
    # 统计 token 类型
    token_counts = {}
    for tok in tokens:
        ttype = tokenize.tok_name[tok.type]
        token_counts[ttype] = token_counts.get(ttype, 0) + 1
    
    print(f"\n  Token 类型统计:")
    for ttype, count in sorted(token_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {ttype:15s}: {count}")
        
except tokenize.TokenError as e:
    print(f"  ❌ Tokenize 错误:")
    print(f"     {e.args[0] if e.args else 'Unknown error'}")

# 5. 检测未闭合的字符串
print("\n【5. 未闭合字符串检测】")

lines = content.split('\n')
unclosed_lines = []

for i, line in enumerate(lines):
    # 简单检测：检查行末是否在字符串内
    # 使用状态机跟踪引号状态
    in_single_string = False
    in_double_string = False
    in_triple_single = False
    in_triple_double = False
    j = 0
    while j < len(line):
        ch = line[j]
        
        # 检查三引号
        if not in_single_string and not in_double_string:
            if line[j:j+3] == "'''":
                if not in_triple_single and not in_triple_double:
                    in_triple_single = not in_triple_single
                    j += 3
                    continue
                elif in_triple_single:
                    in_triple_single = False
                    j += 3
                    continue
            elif line[j:j+3] == '"""':
                if not in_triple_single and not in_triple_double:
                    in_triple_double = not in_triple_double
                    j += 3
                    continue
                elif in_triple_double:
                    in_triple_double = False
                    j += 3
                    continue
        
        # 检查单引号
        if ch == "'" and not in_double_string and not in_triple_single and not in_triple_double:
            if j+1 < len(line) and line[j+1] == "'":
                pass  # 可能是双引号的一部分
            else:
                in_single_string = not in_single_string
        
        # 检查双引号
        elif ch == '"' and not in_single_string and not in_triple_single and not in_triple_double:
            if j+1 < len(line) and line[j+1] == '"':
                pass  # 可能是三引号的一部分
            else:
                in_double_string = not in_double_string
        
        j += 1
    
    # 如果行结束时还在字符串中
    if in_single_string or in_double_string or in_triple_single or in_triple_double:
        unclosed_lines.append({
            'line_num': i + 1,
            'content': line.strip()[:80],
            'in_single': in_single_string,
            'in_double': in_double_string,
            'in_triple_single': in_triple_single,
            'in_triple_double': in_triple_double
        })

if unclosed_lines:
    print(f"  ⚠️ 发现 {len(unclosed_lines)} 行可能存在未闭合字符串:\n")
    for item in unclosed_lines[:20]:  # 只显示前20个
        types = []
        if item['in_single']: types.append('单引号')
        if item['in_double']: types.append('双引号')
        if item['in_triple_single']: types.append('三单引号')
        if item['in_triple_double']: types.append('三双引号')
        
        print(f"  第 {item['line_num']:4d} 行 ({', '.join(types)}):")
        print(f"         {item['content']}")
else:
    print("  ✅ 未发现明显的未闭合字符串")

# 6. 检测乱码字符
print("\n【6. 乱码/异常字符检测】")

garbled_pattern = re.compile(r'[\ue000-\uf8ff\ufffd]|[\x80-\xff]{3,}')
garbled_count = 0
garbled_lines = []

for i, line in enumerate(lines):
    matches = garbled_pattern.findall(line)
    if matches:
        garbled_count += len(matches)
        if len(garbled_lines) < 10:  # 只记录前10行
            garbled_lines.append({
                'line_num': i + 1,
                'count': len(matches),
                'sample': line.strip()[:60]
            })

if garbled_count > 0:
    print(f"  ⚠️ 发现 {garbled_count} 个可能的乱码字符")
    print(f"  分布在至少 {len(garbled_lines)} 行中:\n")
    for item in garbled_lines:
        print(f"  第 {item['line_num']:4d} 行 ({item['count']}个): {item['sample']}")
else:
    print("  ✅ 未发现明显乱码字符")

# 7. 括号匹配检测
print("\n【7. 括号匹配检测】")

brackets = {'(': ')', '[': ']', '{': '}'}
stack = []
bracket_errors = []

for i, line in enumerate(lines):
    for j, ch in enumerate(line):
        if ch in brackets.keys():
            stack.append((ch, i+1, j+1))
        elif ch in brackets.values():
            if stack:
                open_bracket, line_num, col_num = stack.pop()
                if brackets[open_bracket] != ch:
                    bracket_errors.append((i+1, j+1, f"不匹配: 期望 {brackets[open_bracket]}, 得到 {ch}"))
            else:
                bracket_errors.append((i+1, j+1, f"多余的闭合括号 {ch}"))

if stack:
    for open_bracket, line_num, col_num in stack[-5:]:
        bracket_errors.append((line_num, col_num, f"未闭合的 {open_bracket}"))

if bracket_errors:
    print(f"  ⚠️ 发现 {len(bracket_errors)} 个括号问题 (显示前10个):\n")
    for line_num, col_num, msg in bracket_errors[:10]:
        print(f"  第 {line_num:4d} 行第 {col_num:2d} 列: {msg}")
else:
    print("  ✅ 括号匹配正常")

# 8. 总结
print("\n" + "=" * 70)
print("【诊断总结】")
print("=" * 70)
print(f"""
文件大小: {size/1024:.1f} KB
最佳编码: {best_encoding}
语法状态: {'❌ 有错误' if unclosed_lines or bracket_errors else '✅ 正常'}
未闭合字符串: {len(unclosed_lines)} 处
乱码字符: {garbled_count} 个
括号问题: {len(bracket_errors)} 处

建议修复优先级:
1. 先修复未闭合字符串（导致语法错误）
2. 再处理乱码字符（影响功能但不阻止运行）
3. 最后处理括号问题（可能导致运行时错误）
""")
