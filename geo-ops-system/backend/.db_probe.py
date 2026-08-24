import pymysql
from itertools import product
hosts=['127.0.0.1','localhost']
ports=[3307]
users=['root','geo_system','mariadb.sys']
passwords=['','root','123456','geo_dev_2026','admin','password']
dbs=['mysql','waimao_geo','geo_system']
for h,p,u,pw,d in product(hosts,ports,users,passwords,dbs):
    try:
        conn=pymysql.connect(host=h,port=p,user=u,password=pw,database=d,connect_timeout=2)
        conn.close()
        print('OK',h,p,u,pw if pw else '<empty>',d)
    except Exception:
        pass
