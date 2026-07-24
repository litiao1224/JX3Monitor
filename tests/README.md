# Tests

Run the golden settlement regression test with the project Python:

```powershell
C:\Users\litia\AppData\Local\Python\bin\python.exe .\tests\test_golden_basic_settlement.py
```

The fixture under `tests/golden/basic_settlement.raw_events.jsonl` covers:

- auction start parsing
- room bid parsing
- explicit final purchase parsing
- settlement snapshot parsing
- team append income included in total auction gold
- identity fallback from session metadata
