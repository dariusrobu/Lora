# Lora — harta proiectului

## Fluxul principal

```text
mesaj utilizator
  → bot/handler.py
  → core/agent.py sau core/gemini.py (Ollama)
  → core/router.py
  → core/dispatcher.py
  → modules/{modul}.py
  → db/queries/{modul}.py
  → PostgreSQL
```

Dashboard-ul folosește fluxul separat:

```text
React page → lora_api/routers/{modul}.py → db/queries/{modul}.py → PostgreSQL
```

## Reguli rapide

- Ollama este singurul runtime LLM pentru conversație.
- Modulele nu trimit mesaje Telegram direct.
- Query-urile DB folosesc parametri `$1, $2`; nu se construiesc query-uri cu f-string.
- Scrierile importante necesită confirmare.
- Modificările agentului Dev se fac într-un branch separat și se verifică prin teste.
