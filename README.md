# ATP data updater v33 - guard na 403 i debug

Logi pokazują, że GitHub Actions dostaje 403 Forbidden z atptour.com dla kalendarza, wyników i drabinek.
To nie jest błąd Androida ani samego parsera: ATP blokuje requesty z GitHub Actions.

Zmiany:
- jeśli source_url jest None, skrypt NIE nadpisuje matches.json / players.json zerami,
- jeśli draw_source_url jest None, skrypt NIE nadpisuje draw.json pustą drabinką,
- istniejące dane są zachowane i oznaczone:
  - preservedBecauseResultsSourceWasBlocked
  - preservedBecauseDrawSourceWasBlocked
- zostaje bezpiecznik: nowe 0 nie kasuje starego niepustego matches.json,
- workflow zostaje co 2 godziny.

Uwaga:
- jeśli pliki zostały już wcześniej wyzerowane, ta wersja ich magicznie nie odbuduje.
- trzeba przywrócić dane z historii GitHuba albo zmienić źródło pobierania, bo ATP daje 403.
