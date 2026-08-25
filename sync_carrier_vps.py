#!/usr/bin/env python3
import argparse,base64,json,os,sys
import mysql.connector,requests
from dotenv import load_dotenv
load_dotenv()
BASE="https://mobile.fmcsa.dot.gov/qc/services/carriers"
ZYTE="https://api.zyte.com/v1/extract"
COLS=["ACT_STAT","CARSHIP","DOT_NUMBER","NAME","NAME_DBA","DBNUM","PHY_NATN","PHY_STR","PHY_CITY","PHY_CNTY","PHY_ST","PHY_ZIP","UNDELIV_PHY","TEL_NUM","CELL_NUM","FAX_NUM","MAI_NATN","MAI_STR","MAI_CITY","MAI_CNTY","MAI_ST","MAI_ZIP","UNDELIV_MAI","ICC_DOCKET_1_PREFIX","ICC1","CRRINTER","CRRHMINTRA","PASSENGERS","HM_IND","OWNCOACH","OWNBUS_16","OWNVAN_9_15","OWNLIMO_16","OWNSCHOOL_16","TOT_TRUCKS","TOT_BUSES","TOT_PWR","FLEETSIZE","TOT_DRS","CDL_DRS","REVTYPE","REVDATE","ACC_RATE","MLG150","RATING","RATEDATE","MCS150MILEAGEYEAR","ADDDATE","MCS_150_DATE","EMAILADDRESS","USDOT_REVOKED_FLAG","USDOT_REVOKED_NUMBER","COMPANY_REP1","COMPANY_REP2","API_RAW_JSON"]
def env(n):
 v=os.getenv(n)
 if not v: raise SystemExit("Missing env: "+n)
 return v
def s(v):
 if v is None: return None
 if isinstance(v,bool): return "Y" if v else "N"
 t=str(v).strip(); return t or None
def yn(v):
 if v is None: return None
 if isinstance(v,bool): return "Y" if v else "N"
 t=str(v).strip().upper()
 if t in ("Y","YES","TRUE","1"): return "Y"
 if t in ("N","NO","FALSE","0"): return "N"
 return s(v)
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
def op_code(c):
 op=c.get("carrierOperation") or {}
 if isinstance(op,dict): return s(op.get("carrierOperationCode") or op.get("code") or op.get("carrierOperationDesc"))
 return s(op)
def mc_parts(c):
 raw=c.get("mcNumber") or c.get("docketNumber")
 if raw is None: return None,None
 text=str(raw).strip().upper().replace(" ","")
 for p in ("MC","MX","FF"):
  if text.startswith(p): return p, text[len(p):].lstrip("-")
 if text.isdigit(): return "MC", text
 return None,None
def map_carrier(c,payload=None,basics=None):
 pref,icc=mc_parts(c)
 bus,limo,mini,coach,van,pv=s(c.get("busVehicle")),s(c.get("limoVehicle")),s(c.get("miniBusVehicle")),s(c.get("motorCoachVehicle")),s(c.get("vanVehicle")),s(c.get("passengerVehicle"))
 tot_pwr=s(c.get("totalPowerUnits") or c.get("powerUnitTotal") or pv)
 tot_drs=s(c.get("totalDrivers"))
 allow=yn(c.get("allowToOperate") or c.get("allowedToOperate")); oos=yn(c.get("outOfService"))
 act=s(c.get("statusCode"))
 if not act: act="I" if oos=="Y" else ("A" if allow=="Y" else allow)
 fleet=None
 try:
  if tot_pwr is not None:
   n=int(float(tot_pwr)); fleet="1" if n<=1 else "2-6" if n<=6 else "7-20" if n<=20 else "21+"
 except Exception: fleet=tot_pwr
 pass_flag=None
 for v in (bus,limo,mini,coach,van,pv):
  if v is None: continue
  try:
   if float(v)>0: pass_flag="Y"; break
  except Exception: pass_flag="Y"; break
 row={
  "DOT_NUMBER":s(c.get("dotNumber")),"NAME":s(c.get("legalName")),"NAME_DBA":s(c.get("dbaName")),"ACT_STAT":act,
  "CARSHIP":s(c.get("carrierOperationDesc") or op_code(c)),"DBNUM":s(c.get("ein")),
  "PHY_STR":s(c.get("phyStreet")),"PHY_CITY":s(c.get("phyCity")),"PHY_CNTY":s(c.get("phyCounty")),"PHY_ST":s(c.get("phyState")),
  "PHY_ZIP":s(c.get("phyZipcode") or c.get("phyZip")),"PHY_NATN":s(c.get("phyCountry")),"TEL_NUM":s(c.get("telephone") or c.get("phone")),
  "FAX_NUM":s(c.get("fax")),"MAI_STR":s(c.get("mailingStreet")),"MAI_CITY":s(c.get("mailingCity")),"MAI_ST":s(c.get("mailingState")),
  "MAI_ZIP":s(c.get("mailingZipcode") or c.get("mailingZip")),"MAI_NATN":s(c.get("mailingCountry")),
  "ICC_DOCKET_1_PREFIX":pref,"ICC1":icc,"CRRINTER":op_code(c),"CRRHMINTRA":yn(c.get("hmFlag")),"HM_IND":yn(c.get("hmFlag")),
  "PASSENGERS":pass_flag,"OWNCOACH":coach,"OWNBUS_16":bus,"OWNVAN_9_15":van or mini,"OWNLIMO_16":limo,"OWNSCHOOL_16":bus,
  "TOT_BUSES":bus or s(c.get("totalBuses")),"TOT_PWR":tot_pwr,"FLEETSIZE":fleet,"TOT_DRS":tot_drs,
  "RATING":s(c.get("safetyRating")),"RATEDATE":s(c.get("safetyRatingDate")),"EMAILADDRESS":s(c.get("emailAddress") or c.get("email")),
  "USDOT_REVOKED_FLAG":yn(c.get("usdotRevoked") or c.get("dotRevoked")),"COMPANY_REP1":s(c.get("companyRep1")),"COMPANY_REP2":s(c.get("companyRep2")),
  "API_RAW_JSON":json.dumps({"carrier":c,"docs":{"allowToOperate":allow,"outOfService":oos,"outOfServiceDate":s(c.get("outOfServiceDate") or c.get("oosDate")),"complaintCount":s(c.get("complaintCount")),"mcNumber":s(c.get("mcNumber")),"busVehicle":bus,"limoVehicle":limo,"miniBusVehicle":mini,"motorCoachVehicle":coach,"vanVehicle":van,"passengerVehicle":pv},"basics":basics,"response":payload},ensure_ascii=False,default=str),
 }
 return row
def table_cols(conn,table):
 cur=conn.cursor(); cur.execute("SHOW COLUMNS FROM `%s`"%table); cols={r[0] for r in cur.fetchall()}; cur.close(); return cols
def upsert(conn,table,row,existing):
 cols=[c for c in COLS if c in existing and row.get(c) is not None]
 if "DOT_NUMBER" not in cols: raise ValueError("DOT_NUMBER required")
 # SAFE: COALESCE keeps existing census data if API value missing
 sql="INSERT INTO `%s` (%s) VALUES (%s) ON DUPLICATE KEY UPDATE %s"%(table,", ".join("`%s`"%c for c in cols),", ".join(["%s"]*len(cols)),", ".join("`%s`=COALESCE(VALUES(`%s`),`%s`)"%(c,c,c) for c in cols if c!="DOT_NUMBER"))
 cur=conn.cursor(); cur.execute(sql,[row[c] for c in cols]); conn.commit()
 print("DOT",row["DOT_NUMBER"],"ok",row.get("NAME"),"cols",len(cols)); cur.close()
def db():
 return mysql.connector.connect(host=os.getenv("MYSQL_HOST","127.0.0.1"),port=int(os.getenv("MYSQL_PORT","3306")),user=env("MYSQL_USER"),password=os.getenv("MYSQL_PASSWORD",""),database=os.getenv("MYSQL_DATABASE","fmcsaaa"))
def fetch_basics(dot,webkey):
 try: return fetch_json("%s/%s/basics?webKey=%s"%(BASE,dot,webkey))
 except Exception as e:
  print("BASICS skip",e,file=sys.stderr); return None
def sync_dot(dot):
 webkey=env("FMCSA_WEBKEY"); table=os.getenv("MYSQL_TABLE","carrierinformation_csv")
 payload=fetch_json("%s/%s?webKey=%s"%(BASE,dot,webkey)); carriers=extract_carriers(payload)
 if not carriers: raise SystemExit("No carrier for DOT "+dot)
 basics=fetch_basics(dot,webkey); conn=db()
 try:
  cur=conn.cursor(); cur.execute("SELECT COUNT(*) FROM `%s`"%table); before=cur.fetchone()[0]; cur.close()
  print("Rows before:",before,"(no truncate)")
  existing=table_cols(conn,table)
  for c in carriers: upsert(conn,table,map_carrier(c,payload,basics),existing)
  cur=conn.cursor(); cur.execute("SELECT COUNT(*) FROM `%s`"%table); after=cur.fetchone()[0]; cur.close()
  print("Rows after:",after)
  if after<before: raise SystemExit("ERROR row count dropped")
 finally: conn.close()
if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("dot"); sync_dot(p.parse_args().dot.strip())
