# ATP data v38 - debug HTML i brak zapisu zera

Log v37 pokazał:
- Playwright subprocess już startuje,
- ale strona pobrana przez GitHub Actions parsuje się na 0 meczów,
- trzeba zobaczyć realny HTML, który dostaje runner.

Zmiany v38:
- gdy parser wyników widzi 0 meczów, zapisuje HTML do:
  data/debug/<year>/<circuit>-<id>-results-zero-parse.html
- gdy parser drabinki widzi 0 rund, zapisuje HTML do:
  data/debug/<year>/<circuit>-<id>-draw-zero-parse.html
- zapisuje też plik meta .json ze snippetem tekstu i tytułem strony,
- jeśli wszystkie wyniki dają 0, source_url = None, więc istniejące matches.json NIE będzie nadpisane zerem,
- workflow dalej co 6 godzin,
- UPDATE_MODE na stałe live, bez pola przy uruchamianiu.

Po uruchomieniu workflow sprawdź np.:
data/debug/2026/tour-440-results-zero-parse.html
data/debug/2026/tour-440-results-zero-parse.json

To pokaże, czy ATP daje normalną stronę, pustą stronę, captcha/blocked, albo HTML z inną strukturą.
