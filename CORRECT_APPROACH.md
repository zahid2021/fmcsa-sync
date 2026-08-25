# Correct approach (video + history)

DO NOT use `api_server.py` / port 8000 for the FMCSA CARRIERS UI.

## Already exists on Anthony RDP

| Piece | Path |
|-------|------|
| Frontend (Vite :5173) | `C:\Users\Administrator\Desktop\fmsca\fmsca_frontend` |
| Backend (Flask :5000) | `C:\Users\Administrator\Desktop\fmsca\fmsca_backend` |
| Sync scripts only | `C:\fmcsa_sync` |

Original UI already calls:
- `http://127.0.0.1:5000/all?page=…`
- `http://127.0.0.1:5000/filter/`

## Video asks (only these)

1. Backup project + DB → Slack/email  
2. Keep Total Items = full count; ~1000 rows/page (already how Flask was designed)  
3. Remove **Chunks** dropdown; one-file export  

## What we should change

1. **MainData.tsx** — remove Chunks UI; keep Flask `:5000`  
2. **fmsca_backend** — add/fix one-file `/export` on the **same** Flask app (not a new FastAPI)  
3. `export_one_file.py` in `C:\fmcsa_sync` is optional CLI helper only  

## Start existing backend (items will show again)

```bat
cd /d C:\Users\Administrator\Desktop\fmsca\fmsca_backend
call env\Scripts\activate.bat
python app.py
```

(If entry file is different: `run.py` / `main.py` — check with `dir *.py`)

Test:
```bat
curl "http://127.0.0.1:5000/all?page=1"
```
