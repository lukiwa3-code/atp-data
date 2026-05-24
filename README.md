# ATP data updater v10

Poprawka dla Grand Slam / best-of-five i tie-breaków:

- parser używa teraz algorytmu wyboru najlepszej ścieżki wyniku,
- poprawnie skleja tie-breaki rozbite na osobne tokeny,
- naprawia przypadki typu:
  `6-3 7-6 6-6 5-7 6-0`
  na:
  `6-3 7-6(6) 6-7(5) 6-0`,
- działa również dla standardowych meczów best-of-three.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
