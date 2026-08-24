import re,subprocess,sys
fp=r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
px=sys.executable
with open(fp,'r',encoding='utf-8') as f: c=f.read()
c=c.replace('瀹㈡埛涓嶅瓨鍦?','客户不存在')
c=c.replace('鎭㈠澶辫触','恢复失败')
def fixds(m):
 s=m.group(0)
 for ch in s:
  o=ord(ch)
  if o>127 and(0x2E80<=o<=0x2FDF or 0xF900<=o<=0xFAFF or 0x3200<=o<=0x32FF or 0xFF00<=o<=0xFFEF):return '""""""'
 return s
c=re.sub(r'""".*?"""',fixds,c)
with open(fp,'w',encoding='utf-8') as f:f.write(c)
r=subprocess.run([px,'-m','py_compile',fp],capture_output=True,text=True)
print('OK' if r.returncode==0 else 'FAIL: '+r.stderr[:100])
