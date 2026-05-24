# ATP data updater v8

Naprawa po v7:
- liczby wyników są teraz przypisywane do zawodnika przed filtrowaniem `is_noise_line`,
- v7 traktował same cyfry jako szum i dlatego potrafił wygenerować `count: 0`,
- dodany bezpiecznik: jeśli nowy parser zwróci 0 meczów, a w repo był wcześniej dobry `matches.json`, skrypt zachowa stary plik zamiast go wyzerować.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
