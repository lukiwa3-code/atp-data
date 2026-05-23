# ATP Data Updater v2

Ten skrypt aktualizuje:

- `data/tournaments.json`
- `data/tournaments_flat.json`
- `data/results_index.json`
- `data/{year}/{eventId}/players.json`
- `data/{year}/{eventId}/matches.json`

Wyniki są generowane dla turniejów live oraz ostatnich zakończonych turniejów.
Liczbę ostatnich zakończonych turniejów ustawisz w `scripts/update_atp.py` w stałej:

```python
PAST_TOURNAMENTS_TO_UPDATE = 16
```
