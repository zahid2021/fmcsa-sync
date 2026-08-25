# Frontend fix (Anthony `localhost:5173`)

Client video: keep filter UI, change pagination + export.

## 1) Pagination

- API / query must return **`total`** = full filtered count (show as **Total Items**).
- Fetch only **`limit=1000`** rows per page.
- Page count = `Math.ceil(total / 1000)` (for 79621 → 80 pages is OK).

Example fetch:

```js
const limit = 1000;
const res = await fetch(
  `http://127.0.0.1:8000/api/carriers?phy_st=${value}&page=${page}&limit=${limit}`
);
const data = await res.json();
// data.total  → "Total Items: …"
// data.items  → table rows (≤ 1000)
```

## 2) Remove Chunks — one-file export

- Delete / hide the **Chunks** dropdown.
- **EXPORT TO EXCEL** should hit a **server** download (not build Excel in the browser):

```js
// Opens one file with ALL filtered rows (streamed CSV; Excel opens it)
window.location.href =
  `http://127.0.0.1:8000/api/carriers/export?phy_st=${value}&format=csv`;
```

Or run offline on the server:

```bat
python export_one_file.py --phy-st TN --out C:\fmcsa_sync\exports
```

## 3) Before you edit the Vite app

```bat
cd C:\fmcsa_sync
.venv\Scripts\activate
python backup_for_client.py --project-dir C:\path\to\fmcsa-frontend
```

Send `backups\*.zip` + `backups\*.sql` on **Slack + email**, then change the UI.

## 4) Run API next to the UI

```bat
pip install fastapi uvicorn mysql-connector-python python-dotenv openpyxl
python api_server.py
```

Keep Vite on `:5173`, API on `:8000`.
