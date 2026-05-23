# ATP data updater v7

Zmiana względem v6:
- parser nie bierze już ślepo pierwszych dwóch tekstów wyglądających jak nazwy,
- wybiera pierwszą parę zawodników, przy której faktycznie występują liczby wyników,
- filtruje teksty typu `player-photo`, `wins the point`, `match point`, `serve` itd.,
- powinno to naprawić brak finału Hamburga: Ignacio Buse vs Tommy Paul.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
