# ATP data updater v27 - scalanie wyników i draw fallback

Poprawki:
- `matches.json` nie jest już obcinany, gdy świeży parser zwróci mniej meczów niż było wcześniej.
- Stare i nowe mecze są scalane po rundzie i parze zawodników.
- Jeżeli Results nie złapie finału/półfinału/ćwierćfinału, skrypt uzupełnia brakujące rozegrane mecze z `draw.json`.
- Dotyczy ATP Tour i Challenger.
- To powinno naprawić:
  - urwane historie zawodników,
  - brakujące SF/QF/F,
  - sytuacje, gdy live/current nagle pokazuje tylko kilka meczów R32.

Po podmianie uruchom `Update ATP Data`.
