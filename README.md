# ATP data updater v16 - ATP + Challenger

Nowość:
- pobiera ATP Tour jak wcześniej,
- dodatkowo pobiera ATP Challenger z endpointu:
  `https://www.atptour.com/en/-/tournaments/calendar/challenger`,
- zapis ATP zostaje bez zmian:
  `data/tournaments_flat.json`, `data/{year}/{id}/matches.json`,
- Challenger zapisuje się osobno:
  `data/challenger/tournaments_flat.json`,
  `data/challenger/{year}/{id}/matches.json`,
  `data/challenger/{year}/{id}/draw.json`,
- dane rankingowe z v15 nadal są dopisywane do `draw.json` i `matches.json`,
- powstaje wspólny indeks:
  `data/results_index_all.json`.

Po podmianie uruchom:
1. `Actions -> Update ATP Rankings`
2. `Actions -> Update ATP Data`
