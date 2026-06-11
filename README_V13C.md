# ATP data updater v13c - nie ruszaj tournament.json bez nowych danych

Problem z v13b:
- gdy ATP calendar dawał 403, skrypt używał starego tournaments_flat.json,
- ale w pętli dla turnieju zawsze zapisywał `tournament.json`,
- dlatego w GitHubie wyglądało, że odświeżył się tylko `tournament.json`,
  mimo że matches/draw były chronione.

Zmiany v13c:
- nie zapisuje `tournament.json`, jeżeli nie pobrano nowych wyników ani drabinki,
- zapisuje `tournament.json` tylko przy realnym update albo gdy plik nie istnieje,
- nie rusza `results_index.json`, jeśli nie było żadnego realnego update,
- dalej używa starego `data/tournaments_flat.json`, jeśli ATP calendar daje 403,
- dalej nie nadpisuje `matches.json` zerem,
- dalej nie nadpisuje `draw.json` pustą drabinką.

Wrzucić do repo `atp-data`:
- `scripts/update_atp.py`
- `.github/workflows/main.yml`
- `requirements.txt`
