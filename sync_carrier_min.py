#!/usr/bin/env python3
import argparse,base64,json,os,sys
import mysql.connector,requests
from dotenv import load_dotenv
load_dotenv()
BASE="https://mobile.fmcsa.dot.gov/qc/services/carriers"
ZYTE="https://api.zyte.com/v1/extract"
def env(n):
 v=os.getenv(n)
 if not v: raise SystemExit("Missing env: "+n)
 return v
def s(v):
 if v is None: return None
 if isinstance(v,bool): return "Y" if v else "N"
 t=str(v).strip(); return t or None
def fetch_json(url):
 h={"Accept":"application/json","User-Agent":"CDL/1.0"}
 try:
  r=requests.get(url,headers=h,timeout=45)
  if r.status_code==200: return r.json()
  print("FMCSA HTTP",r.status_code,file=sys.stderr)
  if not os.getenv("ZYTE_API_KEY"): r.raise_for_status()
 except requests.RequestException as e:
  print("FMCSA err",e,file=sys.stderr)
  if not os.getenv("ZYTE_API_KEY"): raise
 key=(os.getenv("ZYTE_API_KEY") or "").strip()
 if not key: raise SystemExit("FMCSA failed; set ZYTE_API_KEY")
 zr=requests.post(ZYTE,auth=(key,""),json={"url":url,"httpResponseBody":True,"customHttpRequestHeaders":[{"name":"Accept","value":"application/json"}]},timeout=90)
 zr.raise_for_status(); body=zr.json(); raw=base64.b64decode(body["httpResponseBody"]); st=body.get("statusCode")
 if st and int(st)>=400: raise SystemExit("Zyte HTTP %s"%st)
 return json.loads(raw)
def extract_carriers(payload):
 content=payload.get("content",payload)
 items=content if isinstance(content,list) else ([content] if isinstance(content,dict) else [])
 out=[]
 for item in items:
  if not isinstance(item,dict): continue
  c=item.get("carrier",item)
  if isinstance(c,dict) and c.get("dotNumber") is not None: out.append(c)
 return out
def map_carrier(c):
 op=c.get("carrierOperation") or {}
 if not isinstance(op,dict): op={}
 act=s(c.get("statusCode")) or s(c.get("allowedToOperate"))
 return {"DOT_NUMBER":s(c.get("dotNumber")),"NAME":s(c.get("legalName")),"NAME_DBA":s(c.get("dbaName")),"ACT_STAT":act,"PHY_STR":s(c.get("phyStreet")),"PHY_CITY":s(c.get("phyCity")),"PHY_ST":s(c.get("phyState")),"PHY_ZIP":s(c.get("phyZipcode") or c.get("phyZip")),"PHY_NATN":s(c.get("phyCountry")),"TEL_NUM":s(c.get("telephone") or c.get("phone")),"EMAILADDRESS":s(c.get("emailAddress") or c.get("email")),"TOT_DRS":s(c.get("totalDrivers")),"TOT_PWR":s(c.get("totalPowerUnits")),"RATING":s(c.get("safetyRating")),"RATEDATE":s(c.get("safetyRatingDate")),"CRRINTER":s(op.get("carrierOperationCode") or op.get("code")),"USDOT_REVOKED_FLAG":s(c.get("usdotRevoked") or c.get("dotRevoked"))}
COLS=["DOT_NUMBER","NAME","NAME_DBA","ACT_STAT","PHY_STR","PHY_CITY","PHY_ST","PHY_ZIP","PHY_NATN","TEL_NUM","EMAILADDRESS","TOT_DRS","TOT_PWR","RATING","RATEDATE","CRRINTER","USDOT_REVOKED_FLAG"]
def upsert(conn,table,row):
 cols=[c for c in COLS if row.get(c) is not None]
 if "DOT_NUMBER" not in cols: raise ValueError("DOT_NUMBER required")
 sql="INSERT INTO `%s` (%s) VALUES (%s) ON DUPLICATE KEY UPDATE %s"%(table,", ".join("`%s`"%c for c in cols),", ".join(["%s"]*len(cols)),", ".join("`%s`=VALUES(`%s`)"%(c,c) for c in cols if c!="DOT_NUMBER"))
 cur=conn.cursor(); cur.execute(sql,[row[c] for c in cols]); conn.commit(); print("DOT",row["DOT_NUMBER"],"ok",row.get("NAME")); cur.close()
def db():
 return mysql.connector.connect(host=os.getenv("MYSQL_HOST","127.0.0.1"),port=int(os.getenv("MYSQL_PORT","3306")),user=env("MYSQL_USER"),password=os.getenv("MYSQL_PASSWORD",""),database=os.getenv("MYSQL_DATABASE","fmcsaaa"))
def sync_dot(dot):
 url="%s/%s?webKey=%s"%(BASE,dot,env("FMCSA_WEBKEY")); carriers=extract_carriers(fetch_json(url))
 if not carriers: raise SystemExit("No carrier for DOT "+dot)
 conn=db()
 try:
  for c in carriers: upsert(conn,os.getenv("MYSQL_TABLE","carrierinformation_csv"),map_carrier(c))
 finally: conn.close()
if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("dot"); sync_dot(p.parse_args().dot.strip())
