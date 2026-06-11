# ATP data updater v29 - naprawa draw i ucinanych wyników

Problem:
- `Results` dla turniejów live potrafi zwrócić tylko część turnieju, np. samą R32 albo mecze z jednego dnia.
- `draw.json` dla live turniejów potrafił zapisać się jako pusty, bo parser nie łapał nowego HTML-a ATP.
- Przez to aplikacja traciła rundy do finału i historia zawodników była ucięta.

Poprawka:
- workflow nadal odświeża dane co 2 godziny,
- draw parser ma fallback tekstowy dla statycznego HTML-a ATP,
- draw URL ma warianty bez apostrofu, np. `s-hertogenbosch`,
- `draw.json` nie jest nadpisywany pustą/uboższą drabinką,
- `matches.json` jest uzupełniany rozegranymi meczami z draw,
- `matches.json` nie jest obcinany, jeśli świeży parser zwróci mniej meczów niż stary plik.

Po podmianie uruchom `Update ATP Data`.
