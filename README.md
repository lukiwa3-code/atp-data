# ATP data updater v15 - historical rankings

Nowość:
- pobiera historyczne rankingi ATP Singles z `rankRange=0-5000`,
- zapisuje snapshoty tygodniowe:
  `data/rankings/singles/YYYY-MM-DD.json`,
- domyślnie backfill startuje od `2024-01-01`,
- można później ustawić starszą datę, np. `2021-01-01`,
- dodaje `data/rankings/singles/index.json`,
- wzbogaca `draw.json` i `matches.json` o:
  - `player1Rank`, `player1RankingPoints`, `player1RankingDate`,
  - `player2Rank`, `player2RankingPoints`, `player2RankingDate`,
  - `playerRank`, `opponentRank`, itd.

Workflow:
- `.github/workflows/main.yml` zostaje do turniejów i wyników,
- `.github/workflows/rankings.yml` robi backfill i cotygodniowe odświeżanie rankingów.

Jak użyć:
1. Wrzuć paczkę do repo `atp-data`.
2. Uruchom `Actions -> Update ATP Rankings`.
3. Start date zostaw `2024-01-01`, albo wpisz starszą datę w przyszłości.
4. Potem uruchom `Actions -> Update ATP Data`, aby turnieje dostały rankingi w `draw.json` i `matches.json`.
