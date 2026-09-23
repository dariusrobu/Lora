# Lora — contracte de module

| Modul | Responsabilitate | Date principale |
|---|---|---|
| `finance` | venituri, cheltuieli, categorii și bonuri | `transactions`, memorii bonuri |
| `tasks` | lucruri de făcut și termene | `tasks` |
| `projects` | proiecte și progres | `projects` |
| `events` | reminder-e și evenimente | `events` |
| `university` | materii, note, examene, prezențe și activități academice | tabele university + `schedule` |
| `schedule` | orarul săptămânal și paritatea săptămânii | `schedule` |
| `memory` | preferințe și informații utile | `memory` |

## Flux standard

Un modul primește date validate, execută logica specifică și returnează un rezultat. Nu trebuie să importe Telegram sau să formateze direct răspunsuri pentru chat.

Pentru o funcție nouă, agentul trebuie să verifice întâi query-ul DB, ruta API, modulul Telegram și testele aferente.
