# ATP data updater v31 - prosty update meczów

To jest wersja cofająca kombinowanie przy matches.json.

Zmiany:
- workflow co 2 godziny,
- matches.json zapisuje się normalnie, bez porównywania count ze starym plikiem,
- nie ma blokowania aktualizacji, gdy nowy parser zwróci mniej meczów,
- fetch wyników wraca do prostej logiki:
  1. dla live najpierw current,
  2. potem archive,
  3. pierwszy poprawnie sparsowany wynik jest zapisywany,
- draw.json wraca do normalnego zapisu z parsera draw, bez uzupełniania matches z draw,
- zachowane jest zabezpieczenie `tournaments_flat.json`, żeby nie wyzerować całej listy turniejów.

Wrzucić do repo `atp-data`:
- scripts/update_atp.py
- .github/workflows/main.yml
