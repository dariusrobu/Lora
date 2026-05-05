from google.genai import types


def get_lora_tools() -> list[types.Tool]:
    """Returns the list of tool definitions for Lora."""

    add_task = types.FunctionDeclaration(
        name="add_task",
        description="Adaugă un task nou în lista de activități.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "title": types.Schema(type="STRING", description="Titlul task-ului."),
                "priority": types.Schema(
                    type="STRING",
                    enum=["low", "medium", "high"],
                    description="Prioritatea task-ului.",
                ),
                "due_date": types.Schema(
                    type="STRING", description="Data limită (YYYY-MM-DD)."
                ),
                "project": types.Schema(
                    type="STRING", description="Numele proiectului."
                ),
            },
            required=["title"],
        ),
    )

    finance_log = types.FunctionDeclaration(
        name="finance_log",
        description="Înregistrează o cheltuială sau un venit.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "amount": types.Schema(type="NUMBER", description="Suma de bani."),
                "type": types.Schema(
                    type="STRING",
                    enum=["expense", "income"],
                    description="Tipul tranzacției.",
                ),
                "category": types.Schema(
                    type="STRING",
                    description="Categoria (ex: mâncare, transport, salariu).",
                ),
                "description": types.Schema(
                    type="STRING", description="Descriere scurtă."
                ),
            },
            required=["amount", "type", "category"],
        ),
    )

    log_skill = types.FunctionDeclaration(
        name="log_skill",
        description="Înregistrează progresul pentru un skill sau o obișnuință (habit).",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "skill_name": types.Schema(
                    type="STRING", description="Numele skill-ului."
                ),
                "value": types.Schema(
                    type="NUMBER",
                    description="Valoarea înregistrată (ex: minute, pagini, unități).",
                ),
                "notes": types.Schema(type="STRING", description="Note opționale."),
            },
            required=["skill_name", "value"],
        ),
    )

    health_log = types.FunctionDeclaration(
        name="health_log",
        description="Înregistrează date despre sănătate: somn, apă, greutate.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "sleep_hours": types.Schema(type="NUMBER", description="Ore de somn."),
                "water_ml": types.Schema(
                    type="NUMBER", description="Mililitri de apă."
                ),
                "weight_kg": types.Schema(type="NUMBER", description="Greutate în kg."),
                "sleep_quality": types.Schema(
                    type="STRING", enum=["great", "good", "neutral", "bad", "terrible"]
                ),
            },
        ),
    )

    return [
        types.Tool(function_declarations=[add_task, finance_log, log_skill, health_log])
    ]
