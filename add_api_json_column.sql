-- Run once in MySQL Workbench (so no API field is lost)
ALTER TABLE fmcsaaa.carrierinformation_csv
  ADD COLUMN API_RAW_JSON LONGTEXT NULL
  AFTER COMPANY_REP2;
