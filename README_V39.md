# ATP data v39 - Cloudflare wait + no zero commit

Co pokazuje debug:
- GitHub Actions przez Playwright dostał stronę Cloudflare "Just a moment...",
  a nie prawdziwą stronę ATP z wynikami.
- Dlatego parser widział 0 meczów.

Zmiany:
- Playwright używa persistent profile w `/tmp/atp-playwright-profile`,
- czeka do 75 sekund aż Cloudflare puści stronę,
- jeśli nadal widzi Cloudflare, zwraca błąd i NIE traktuje tego jako poprawnego HTML,
- nie zapisuje debug HTML domyślnie,
- nie dopisuje flag do istniejących plików, żeby nie robić pustych commitów,
- nie nadpisuje danych zerem,
- Libema sprawdza też URL bez apostrofu,
- workflow nadal co 6 godzin i bez pola update_mode.

Jeśli v39 nadal zobaczy Cloudflare, GitHub Actions jest blokowany i trzeba robić lokalny update albo użyć innego źródła/proxy.
