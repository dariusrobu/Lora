# Database Migrations — Lora

## Convenție de naming

```
NNN_descriere_scurta.sql
```

| Part | Regulă |
|------|--------|
| `NNN` | Număr secvențial cu 3 cifre, **fără goluri** în secvență (`001`, `002`, …) |
| `_` | Un singur underscore ca separator |
| `descriere_scurta` | Snake case, minim 2 cuvinte, descrie clar **ce adaugă** migrarea |
| `.sql` | Extensie obligatorie |

**Exemple corecte:** `009_reading_list.sql`, `010_mood_tracking.sql`  
**Exemple greșite:** `9_reading.sql`, `009-reading-list.sql`, `new_table.sql`

---

## Header obligatoriu

Fiecare fișier de migrare **trebuie** să înceapă cu:

```sql
-- Migration: NNN_descriere.sql
-- Date: YYYY-MM-DD
-- Description: Ce face această migrare (1-2 propoziții clare).
```

---

## Cum se rulează o migrare

```bash
# Rulează o singură migrare
psql $DATABASE_URL -f db/migrations/NNN_descriere.sql

# Verifică că s-a aplicat (exemplu pentru o tabelă nouă)
psql $DATABASE_URL -c "\dt"
```

> [!IMPORTANT]
> Migrările sunt **idempotente** — folosesc `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`. Le poți rula de oricâte ori fără efecte secundare.

---

## Ordinea obligatorie de execuție

Rulează întotdeauna în ordine numerică **strictă**. Schema de bază mai întâi, migrările după.

```bash
# 1. Schema de bază (o singură dată, la instalare nouă)
psql $DATABASE_URL -f db/schema.sql

# 2. Migrări în ordine (pe un server existent)
psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
psql $DATABASE_URL -f db/migrations/002_academic_profile.sql
psql $DATABASE_URL -f db/migrations/003_projects_enhanced.sql
psql $DATABASE_URL -f db/migrations/004_finance_categories.sql
psql $DATABASE_URL -f db/migrations/005_week_type_enum_fix.sql
psql $DATABASE_URL -f db/migrations/006_academic_periods.sql
psql $DATABASE_URL -f db/migrations/007_conversation_state.sql
psql $DATABASE_URL -f db/migrations/008_execution_log.sql
```

---

## Ce conține fiecare migrare

| Fișier | Ce face |
|--------|---------|
| `001_schema_fixes.sql` | Corecturi inițiale de scheme și indecși lipsă |
| `002_academic_profile.sql` | Tabele pentru profilul academic (subiecte, prezențe) |
| `003_projects_enhanced.sql` | Câmpuri extinse pentru proiecte (deadline, priority, category) |
| `004_finance_categories.sql` | Tabela `finance_categories` și `budget_limits` |
| `005_week_type_enum_fix.sql` | Fixează enum-ul `week_type` pentru paritate săptămânală |
| `006_academic_periods.sql` | Adaugă `semester_config` pentru calculul săptămânilor |
| `007_conversation_state.sql` | Asigură existența tabelei `conversation_state` + coloana `extra JSONB` |
| `008_execution_log.sql` | Creează `execution_log` pentru telemetrie router (intent, module, erori) |

---

## Reguli pentru migrări noi

1. **Nu modifica niciodată** un fișier de migrare deja aplicat în producție.
2. Dacă trebuie să schimbi ceva dintr-o migrare veche → creează o migrare nouă cu numărul următor.
3. Adaugă noua migrare și în tabelul de mai sus din acest README.
4. Actualizează secțiunea **Setup & Running** din `README.md` principal.
