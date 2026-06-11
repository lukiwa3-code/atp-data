# ATP data updater v13d - STOP przy 403

Problem z v13c:
- skrypt wykrywał 403 na kalendarzu,
- brał starą bazę `tournaments_flat.json`,
- ale potem próbował odświeżać 419 turniejów,
- każdy request do ATP dostawał 403,
- było dużo logów i ryzyko pustych commitów.

Zmiany v13d:
- jeżeli kalendarz ATP zwróci 403 na GitHub Actions,
  skrypt kończy pracę od razu,
- nie dotyka `matches.json`,
- nie dotyka `draw.json`,
- nie dotyka `players.json`,
- nie dotyka `tournament.json`,
- nie generuje na nowo `results_index.json`,
- chroni przywróconą starą bazę danych,
- workflow zostaje co 6 godzin.

To jest wersja stabilizująca. Nie rozwiązuje blokady ATP, tylko zapobiega dalszemu psuciu danych.
