# ATP data updater v23 - poprawka turniejów na granicy roku

Poprawka względem v22:
- poprawiono parsowanie zakresów typu `30 Dec - 5 Jan, 2025`,
- wcześniej mogło wyjść błędnie:
  `2025-12-30` → `2026-01-05`,
- teraz wychodzi poprawnie:
  `2024-12-30` → `2025-01-05`,
- dzięki temu turnieje typu Bank of China Hong Kong nie wskakują na górę historii jako turnieje z 2026,
- dla syntetycznych turniejów historycznych wyczyszczono skopiowaną datę/miesiąc z roku referencyjnego, żeby nie dziedziczyć złego roku.

Nie zgadujemy dat pojedynczych meczów. Zmieniamy tylko oryginalny zakres dat turnieju używany do sortowania.
