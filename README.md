# FMCSA → MySQL (`carrierinformation_csv`)

## Client delivery

| Requirement | Status |
|-------------|--------|
| FMCSA QCMobile API → DB | Done (`run.py` / `sync_carrier.py`) |
| Upsert by DOT (unique key) | Done |
| Map **all API fields that match census columns** | Done |
| Keep full API JSON (nothing lost) | `API_RAW_JSON` column |
| **Full carrier universe (~200k–2M+)** | Use `import_census.py` (Company Census File) |

### Important (honest)

**QCMobile API cannot dump all carriers** (lookup by name/DOT/MC only). For “all data / nothing missing”, import the official **Company Census File**.

```bat
cd C:\fmcsa_sync
.venv\Scripts\activate
python import_census.py --download
```

Or download CSV manually then:

```bat
python import_census.py census.csv
```

Test first:

```bat
python import_census.py census.csv --max-rows 1000
```

Never truncates; upserts by `DOT_NUMBER`; blank cells do not wipe existing rows.

## One-time SQL (Workbench)

```sql
ALTER TABLE fmcsaaa.carrierinformation_csv
  ADD COLUMN API_RAW_JSON LONGTEXT NULL
  AFTER COMPANY_REP2;
```

(If column already exists, ignore duplicate-column error.)

## VPS run

```bat
cd C:\fmcsa_sync
.venv\Scripts\activate
python sync_carrier.py 44110
```

Verify:

```sql
SELECT DOT_NUMBER, NAME, TEL_NUM, TOT_DRS, TOT_PWR, RATING,
       LENGTH(API_RAW_JSON) AS json_bytes
FROM fmcsaaa.carrierinformation_csv
WHERE DOT_NUMBER = '44110';
```
