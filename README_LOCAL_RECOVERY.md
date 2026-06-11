# ATP data v34 - local update recovery

Problem z logów:
- GitHub Actions dostaje `403 Forbidden` z atptour.com dla kalendarza, wyników i drabinek.
- Parser nie dostaje HTML-a, więc nie ma czego parsować.
- To nie jest problem aplikacji Android.

Co robi ta paczka:
- zostawia update_atp.py z ochroną przed nadpisywaniem danych przy 403,
- wyłącza automatyczne odświeżanie co 2 godziny w GitHub Actions,
- zostawia workflow tylko ręczny (`workflow_dispatch`),
- dodaje `run_update_local.bat`, żeby uruchomić pobieranie na Twoim komputerze.

Co zrobić:
1. Wrzuć do repo `atp-data`:
   - `scripts/update_atp.py`
   - `.github/workflows/main.yml`
   - opcjonalnie `run_update_local.bat`

2. Nie uruchamiaj już automatycznie GitHub Actions do pobierania ATP, bo ATP blokuje runnera.

3. Otwórz folder repo `atp-data` na komputerze i uruchom:
   `run_update_local.bat`

4. Jeżeli lokalnie nie ma 403, wykonaj:
   git add data
   git commit -m "Update ATP data local"
   git push

5. Aplikacja Android pobierze dane z GitHuba tak jak wcześniej.

Jeśli lokalnie też będzie 403:
- trzeba przejść na Playwright/Selenium z prawdziwą przeglądarką albo inne źródło danych.
