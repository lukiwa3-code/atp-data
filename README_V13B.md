# ATP data updater v13b - stara baza + fallback na 403

Ta wersja bazuje na Twoim v13.

Problem:
- stary skrypt zawsze zaczynał od `fetch_calendar()`,
- ATP zwraca teraz 403 dla kalendarza,
- przez to workflow kończył się błędem zanim zaczął używać starej bazy.

Zmiany:
- jeśli kalendarz ATP zwróci 403, skrypt używa istniejącego `data/tournaments_flat.json`,
- nie wywala workflow na starcie,
- nie nadpisuje `matches.json` zerem,
- nie nadpisuje `draw.json` pustą drabinką, jeśli jest stara drabinka,
- nie dopisuje flag do plików przy 403,
- workflow zostaje co 6 godzin.

Wrzucić do repo `atp-data`:
- `scripts/update_atp.py`
- `.github/workflows/main.yml`
- `requirements.txt`

Ważne:
- ta wersja nie rozwiązuje blokady ATP/Cloudflare.
- ona ma uruchomić workflow i ochronić starą bazę, którą przywróciłeś.
