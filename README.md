# ATP data updater v18 - fallback dla wyników 2025

Problem w v17:
- jeśli endpoint kalendarza ATP nie zwrócił roku 2025, skrypt nie miał listy turniejów 2025,
- przez to historia zawodnika nie miała meczów z 2025.

Poprawka v18:
- jeśli brakuje kalendarza 2025, skrypt tworzy archiwalne adresy ATP na podstawie znanych ID/slug turniejów,
- generuje URL-e typu:
  `/en/scores/archive/{slug}/{id}/2025/results`
  `/en/scores/archive/{slug}/{id}/2025/draws`
- dzięki temu powinny pobrać się wyniki 2025 dla większości turniejów,
- historia zawodnika nadal obejmuje 2025 + 2026 i rankingi z tygodnia meczu.

Po podmianie uruchom workflow `Update ATP Data` w repo `atp-data`.
