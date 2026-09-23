# Testarea Lora

## Verificări standard

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
cd dashboard && npm run build
```

## Ordinea verificării

1. Teste unitare pentru logica modificată.
2. Teste API pentru rutele afectate.
3. Build TypeScript pentru dashboard.
4. Teste de regresie pentru modulele dependente.
5. Verificare manuală în UI pentru schimbările vizuale.

Un patch nu este considerat final dacă testele sau build-ul eșuează. Dacă o verificare nu poate fi rulată, motivul trebuie menționat explicit în raport.
