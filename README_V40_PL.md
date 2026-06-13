# ATP data updater v40 - pełna historia + bezpieczne odświeżanie

To jest aktualna paczka do repo `atp-data`.

Najważniejsze:
- ręczne uruchomienie workflow ma domyślnie `update_mode = full`,
- `full` pobiera turnieje historyczne i bieżące,
- harmonogram co 6 godzin działa jako `live`, czyli tylko aktualne turnieje,
- jeśli ATP/Cloudflare odda 403 albo parser znajdzie 0 meczów, stare `matches.json` nie jest kasowane,
- nie dopisuje flag do starych plików, więc nie powinno robić sztucznych commitów,
- Playwright jest instalowany w workflow,
- jest fallback przez Playwright, gdy zwykłe requests dostaje 403.

Wgraj do repo `atp-data`:
- `scripts/update_atp.py`
- `scripts/playwright_fetch.py`
- `.github/workflows/main.yml`
- `requirements.txt`

Jak uruchomić pełną historię:
1. GitHub → repo `atp-data`
2. Actions
3. Update ATP Data
4. Run workflow
5. update_mode = full
6. Run workflow

Później harmonogram co 6 godzin będzie używał `live`.
