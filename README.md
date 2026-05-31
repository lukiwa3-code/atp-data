# ATP data updater v19 - używa rankingów z data/rankings/singles

Problem:
- rankingi są już w repo w folderze `data/rankings/singles/YYYY-MM-DD.json`,
- poprzedni updater szukał ich w `data/rankings/YYYY-MM-DD.json`,
- dlatego historia 2025 pokazywała ranking rywala jako `-`.

Poprawka:
- updater najpierw czyta `data/rankings/singles/YYYY-MM-DD.json`,
- obsługuje format `players` jako lista,
- awaryjnie obsługuje też stary format `players` jako słownik,
- jeśli rankingu nie ma, pobiera go i zapisuje do `data/rankings/singles/YYYY-MM-DD.json`,
- `data/player-history/{playerKey}.json` dostaje poprawne `opponentRank`.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
