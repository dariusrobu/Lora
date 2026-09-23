# Workflow pentru Lora Dev

1. Citește `AGENTS.md`, `AI_MEMORY.md` și documentația relevantă.
2. Verifică `git status` și nu suprascrie modificări existente.
3. Reproduce problema din logs sau dintr-un test.
4. Identifică fișierele și modulele afectate.
5. Scrie un plan scurt cu criterii de acceptare.
6. Creează branch separat; nu modifica direct `main`.
7. Aplică patch-ul minim necesar.
8. Rulează teste, lint și build.
9. Inspectează `git diff` și caută secrete, fișiere generate sau modificări inutile.
10. Raportează cauza, schimbările, verificările și riscurile.
11. Cere confirmare înainte de merge, migrare, restart sau deploy.

## Oprire obligatorie

Agentul se oprește și cere confirmare pentru ștergeri, migrații de schemă, tokenuri, date financiare, autentificare sau schimbări de permisiuni.
