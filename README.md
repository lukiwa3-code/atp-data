# ATP data updater v14

Naprawy:
- status turnieju nie bazuje już tylko na polach ATP `IsLive` i `IsPastEvent`,
- skrypt parsuje datę turnieju i dodaje:
  - dateStart
  - dateEnd
  - computedIsCurrent
  - computedIsPastEvent
  - computedIsUpcoming
- Hamburg i Geneva po zakończeniu dat powinny przejść do `Zakończone`,
- French Open zostanie w `Teraz`, jeśli dzisiejsza data mieści się między startem i końcem turnieju.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
