# ATP data updater v32 - zero guard

Naprawia błąd z v31:
- v31 kończyła na pierwszej stronie, nawet gdy parser zwrócił 0 meczów,
- potem zapisywała `matches.json` z `count: 0`,
- dlatego każdy turniej mógł nagle mieć 0 meczów.

v32:
- nie kończy na pustym parsowaniu, tylko sprawdza kolejne kandydaty URL,
- nie nadpisuje istniejącego niepustego `matches.json` zerem,
- nie porównuje liczby nowych/starych meczów poza przypadkiem 0,
- workflow zostaje co 2 godziny,
- nie wraca do agresywnego scalania draw.

Wrzucić do repo `atp-data`:
- scripts/update_atp.py
- .github/workflows/main.yml
