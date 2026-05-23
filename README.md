# ATP data updater v6

Zmiana względem v5:
- poprawka parsera dla finałów, gdzie ATP rozdziela nagłówek na `Final` oraz `Centre Court`,
- `Centre Court`, `Court 1`, `Grandstand` itp. nie są już traktowane jako zawodnicy,
- powinno to naprawić brak finału Hamburga.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
