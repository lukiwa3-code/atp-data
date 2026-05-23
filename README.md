# ATP data updater v5

Zmiana względem v4:
- parser zapisuje również mecze, przy których ATP nie pokazuje tekstu "Game Set and Match",
- dzięki temu łapie brakujące finały, np. BMW Open by Bitpanda,
- nadal dla turniejów live najpierw używa `/current/.../results`, a potem `/archive/.../results`.

Po podmianie uruchom workflow `Update ATP Data`.
