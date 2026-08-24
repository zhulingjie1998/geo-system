import re, subprocess, sys
fp = r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py'
px = sys.executable

def bad(s):
    for c in s:
        o=ord(c)
        if o>127 and((0x2E80<=o<=0x2FDF)or(0xF900<=o<=0xFAFF)or(0x3200<=o<=0x32FF)or(0xFF00<=o<=0xFFEF)or(0xE000<=o<=0xF8FF)):
            return 1
    return 0

for i in range(100):
    r=subprocess.run([px,'-m','py_compile',fp],capture_output=True,text=True)
    if r.returncode==0:
        print(f'OK after {i} fixes')
        break
    m=re.search(r'line (\d+)',r.stderr)
    if not m:
        print('ERR:'+r.stderr[:100])
        break
    ln=int(m.group(1))
    with open(fp,'r',encoding='utf-8') as f: lines=f.readlines()
    if ln>len(lines): print('OOR');break
    L=lines[ln-1].rstrip()
    print(f'{i} L{ln}: {L[:60]}')
    if '"""' in L and bad(L):
        lines[ln-1]=re.sub(r'""".*?"""','""""""',L)+'\n'
    elif bad(L):
        lines[ln-1]=re.sub(r'"[^"]*"','',L).replace("''","")+'\n'
    else:
        print('CANTFIX');break
    with open(fp,'w',encoding='utf-8') as f: f.writelines(lines)
