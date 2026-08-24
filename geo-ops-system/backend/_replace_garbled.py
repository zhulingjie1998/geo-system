import re
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
with open(fp,'r',encoding='utf-8') as f: content=f.read()
replacements = {
    '瀹㈡埛涓嶅瓨鍦?': '客户不存在',
    '鎭㈠澶辫触': '恢复失败',
    '褰掓拱鎴愬姛': '归档成功',
    '褰掓拱澶辫触': '归档失败',
    '宸茶禋闄ょ洏鍒?': '已移至归档',
    '鍒楄〃涓嶅瓨鍦?': '列表不存在',
}
count = 0
for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)
        count += 1
        print(f'Replaced: {old} -> {new}')
with open(fp,'w',encoding='utf-8') as f: f.write(content)
print(f'Total: {count} replacements done')
