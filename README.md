# ATP data updater v30 - fix URL dla 's-Hertogenbosch i ucinanych live wyników

Główna poprawka:
- ATP calendar zwraca czasem adres z apostrofem:
  `/en/scores/current/'s-hertogenbosch/440/results`
- stabilny adres strony wyników jest bez apostrofu:
  `/en/scores/current/s-hertogenbosch/440/results`
- poprzednie wersje sprawdzały zły wariant i parser łapał stare/ucięte dane.

Zmiany:
- `fetch_tournament_results` sprawdza teraz warianty URL:
  - oryginalny,
  - current,
  - bez apostrofu,
  - bez `/'`,
- wybiera wariant z największą liczbą meczów,
- `matches.json` nie jest nadpisywany, gdy nowe pobranie ma mniej meczów niż stary plik,
- `draw.json` nie jest nadpisywany pustą/uboższą drabinką,
- workflow zostaje co 2 godziny.

Po podmianie uruchom `Update ATP Data`.
