# ATP data updater v15 - historical rankings

Zmiana względem v14:
- historia zawodnika używa rankingu z tygodnia meczu, a nie bieżącego rankingu z profilu ATP,
- dla daty meczu skrypt wyznacza poniedziałek ATP rankingu obowiązujący w tym dniu,
- zapisuje pliki:
  - `data/rankings/YYYY-MM-DD.json`
  - `data/rankings_index.json`
  - `data/player-history/{playerKey}.json`
- w historii meczu pojawiają się:
  - `playerRank`
  - `opponentRank`
  - `rankingDate`
  - `rankingNote: historical_week`

Uwaga:
- jeśli ATP nie zwróci rankingu dla danego tygodnia albo zawodnika nie da się dopasować, ranking będzie pusty.
- aplikacja v9 może zostać bez zmian, bo już czyta pola `playerRank` i `opponentRank`.
