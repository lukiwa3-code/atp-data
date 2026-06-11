# ATP data v37 - bez pola update_mode

Ta wersja nie wymaga wpisywania `update_mode` przy ręcznym uruchamianiu workflow.

Workflow ma na stałe:
- `UPDATE_MODE: "live"`
- refresh co 6 godzin
- Playwright fallback przez osobny proces

Ważne:
Folder `.github` jest ukryty w Windows. Jeżeli wrzucasz pliki przez GitHub → Code → Upload files,
upewnij się, że faktycznie podmieniasz:

.github/workflows/main.yml

Jeżeli po uruchomieniu workflow w logu nie ma:
Playwright Chromium OK
UPDATE_MODE=live

to znaczy, że plik `.github/workflows/main.yml` nie został podmieniony.
