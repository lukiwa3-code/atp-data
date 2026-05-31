# ATP data updater v25b - ATP Challenger + current

Zmiany:
- dodaje turnieje ATP Challenger z archiwum wyników ATP dla 2025 i 2026,
- dodatkowo próbuje czytać bieżące Challengery z `https://www.atptour.com/en/scores/current-challenger`,
- turnieje mają pole `circuit`: `tour` albo `challenger`,
- parser wyników jest ten sam co dla ATP Tour, bo Challenger ma takie same karty meczowe: `match-header`, rundy, zawodnicy i wynik,
- historia zawodników buduje się łącznie z ATP Tour + Challenger,
- dane zapisują się tak samo: `data/{year}/{id}/matches.json`, `draw.json`, `tournament.json`.

Po podmianie uruchom workflow `Update ATP Data`.
