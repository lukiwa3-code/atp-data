# ATP data updater v21 - tylko oryginalne daty

To jest wersja bez wyliczania dat.

Zasada:
- data meczu jest zapisywana tylko wtedy, gdy ATP poda ją w wynikach jako oryginalny nagłówek dnia,
- skrypt nie wylicza daty po rundzie,
- skrypt nie zgaduje daty po końcu turnieju,
- jeśli ATP archive nie podaje dat przy meczach 2025, `date` i `dateIso` zostają puste,
- wtedy ranking z dnia meczu też zostaje pusty, bo bez oryginalnej daty nie da się uczciwie dobrać tygodnia rankingu.

Nadal działa:
- historia 2025 + 2026,
- rankingi z `data/rankings/singles/YYYY-MM-DD.json`,
- ale tylko dla meczów, które mają prawdziwe `dateIso`.
