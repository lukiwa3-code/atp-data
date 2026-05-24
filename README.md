# ATP data updater v9

Poprawka tie-breaków i kolejności zawodników:

- wynik jest teraz zawsze w perspektywie zwycięzcy,
- zwycięzca jest zawsze zapisywany jako `playerName`,
- przegrany jako `opponentName`,
- parser lepiej obsługuje tie-breaki, gdy ATP rozbija wynik na osobne tokeny,
  np. `7`, `6`, `6` -> `7-6(6)`,
- zapobiega dziwnym wynikom setów w aplikacji.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
