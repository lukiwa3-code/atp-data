# ATP data updater v3

Ta wersja pobiera kalendarz ATP oraz wyniki z zakładki `Results`.
Nie bazuje już na `Player Draw`, bo tam dla wielu turniejów lista zawodników była pusta.

Po uruchomieniu GitHub Actions powstaną pliki:

- `data/tournaments_flat.json`
- `data/results_index.json`
- `data/{year}/{eventId}/matches.json`
- `data/{year}/{eventId}/players.json`

Aplikacji Android nie trzeba przebudowywać, jeśli czyta dane online z tego repo.
