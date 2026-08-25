# Client checklist (videos + QCMobile docs)

## Video 2026-08-24 (`bandicam 2026-08-24 16-36-26-199.mp4`)

See **`VIDEO_2026-08-24.md`** for full breakdown.

- RDP **anthoney** → `localhost:5173` FMCSA CARRIERS  
- Filter **TN** / **PHY_ST** → **Total Items: 79621**  
- **Chunks** (1–8) + **EXPORT TO EXCEL**  
- Official SODA: TN **79,641** · ALL USA **~4,490,646**

### Deliverables from that video

| Item | Script |
|------|--------|
| Fill TN gap (~20) | `import_census.py --from-api --phy-st TN` |
| Chunked Excel export | `export_excel_chunks.py --phy-st TN --chunks 8` |
| Full USA | `import_census.py --from-api` (+ `--start-offset` to resume) |
| Compare counts | `verify_counts.py TN` |

## Older video (`bandicam 2026-08-21...`)

- RDP to `155.254.24.135`
- **Total Items: 42827** (pre-growth)
- Export / filters already in UI

## Must not lose existing data

| Rule | How we enforce |
|------|----------------|
| No truncate/delete | Script never TRUNCATE/DELETE |
| Upsert only matching DOT | `ON DUPLICATE KEY UPDATE` on `uq_dot_number` |
| Don’t blank census cells | `COALESCE(VALUES(col), col)` |
| Untouched columns stay | Cargo/OWN*/TRM* not in API → not in UPDATE |

```sql
SELECT COUNT(*) FROM fmcsaaa.carrierinformation_csv;
```

## QCMobile docs → DB mapping

| API element (docs) | DB / storage |
|--------------------|--------------|
| allowToOperate | ACT_STAT (+ API_RAW_JSON) |
| outOfService / outOfServiceDate | API_RAW_JSON |
| complaintCount | API_RAW_JSON |
| dotNumber | DOT_NUMBER |
| mcNumber | ICC_DOCKET_1_PREFIX + ICC1 |
| legalName | NAME |
| dbaName | NAME_DBA |
| phyStreet/City/State/Zip/Country | PHY_* |
| telephone | TEL_NUM |
| BASIC measures | `/carriers/{dot}/basics` → API_RAW_JSON.basics |

Census-only columns stay as loaded — API does not provide them.
