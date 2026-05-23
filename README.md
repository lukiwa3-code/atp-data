# ATP Data Starter

Ten pakiet zawiera gotową strukturę do automatycznego pobierania danych ATP na GitHubie.

## Struktura

```text
data/
  tournaments.json
  tournaments_flat.json

scripts/
  update_atp.py

.github/workflows/
  update_atp.yml
```

## Jak użyć

1. Wrzuć zawartość tego ZIP-a do repozytorium GitHub.
2. Wejdź w zakładkę `Actions`.
3. Wybierz workflow `Update ATP Data`.
4. Kliknij `Run workflow`.
5. Po wykonaniu workflow pliki w folderze `data/` zostaną zaktualizowane.

## GitHub Pages

W repozytorium ustaw:

```text
Settings → Pages → Deploy from a branch → main → /root
```

Wtedy plik będzie dostępny np.:

```text
https://TWOJ_LOGIN.github.io/NAZWA_REPO/data/tournaments_flat.json
```
