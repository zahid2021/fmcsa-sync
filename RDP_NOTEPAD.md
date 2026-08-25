# RDP Notepad method (same as Aug 21 history)

History mein yeh tareeqa use hua tha jab folder copy fail hua:

1. `mkdir C:\fmcsa_sync` + `cd C:\fmcsa_sync`
2. `notepad FILENAME` → Yes (create) → Ctrl+A Delete → paste code → Ctrl+S
3. `dir` se files check
4. `python -m venv .venv` → activate → `pip install ...`
5. `python SCRIPT.py ...`

Badi file ke liye baad mein base64/PowerShell bhi use hua — video fix files chhoti hain (~5KB), Notepad kaafi hai.
