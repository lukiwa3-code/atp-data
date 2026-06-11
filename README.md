# ATP data updater v28 stable - co 2 godziny i bez przycinania wyników

To jest wersja konserwatywna, czyli bliżej stabilnej wersji sprzed eksperymentów z agresywnym scalaniem draw.

Zmiany:
- workflow uruchamia się co 2 godziny: `0 */2 * * *`,
- `fetch_tournament_results` sprawdza wszystkie kandydaty wyników:
  - current,
  - archive,
  - results z drawUrl,
  i wybiera wersję z największą liczbą meczów,
- `save_matches_safely` nie nadpisuje pliku, jeśli świeży parser zwróci mniej meczów niż stary plik,
- dzięki temu dane nie powinny się ucinać do samych R32 lub kilku meczów,
- nie ma agresywnego draw fallback z v27.

Po podmianie uruchom `Update ATP Data`.
