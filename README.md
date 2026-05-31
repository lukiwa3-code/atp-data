# ATP data updater v22 - oryginalne daty turniejów

Poprawka:
- nie zgaduje dat meczów,
- jeśli ATP nie podaje dat przy meczach 2025, `date` i `dateIso` zostają puste,
- skrypt czyta jednak oryginalny zakres dat turnieju z nagłówka ATP,
  np. `30 Jun - 13 Jul, 2025`,
- zapisuje w historii zawodnika:
  - `tournamentDate`
  - `tournamentStartDate`
  - `tournamentEndDate`

Po co:
- aplikacja może sortować turnieje w historii po prawdziwej dacie turnieju,
  bez udawania dat pojedynczych meczów.
