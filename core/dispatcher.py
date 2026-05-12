import importlib
import logging
import traceback
from db.queries.log import log_execution

logger = logging.getLogger("core.dispatcher")


async def execute_module_intent(pool, module, intent, data, reply, user_id, bot):
    """
    Dispatcher point for all modules.
    Ensures a 3-tuple return: (reply_text, keyboard, item_id)
    """
    try:
        # Load module dynamically
        mod = importlib.import_module(f"modules.{module}")

        # Get intent handler - convention: handle_{module}_intent
        handlers_to_try = [f"handle_{module}_intent"]
        if module.endswith("s") and len(module) > 1:
            handlers_to_try.append(f"handle_{module[:-1]}_intent")

        handler = None
        for h_name in handlers_to_try:
            if hasattr(mod, h_name):
                handler = getattr(mod, h_name)
                break

        if not handler:
            return (
                f"⚠️ Eroare: Modulul '{module}' nu are o funcție de procesare (încercat: {', '.join(handlers_to_try)})",
                None,
                None,
            )

        # Inject reply so modules can use it
        data["_original_reply"] = reply

        # Call handler with flexible signature
        import inspect

        sig = inspect.signature(handler)
        params = {}
        if "bot" in sig.parameters:
            params["bot"] = bot
        if "user_id" in sig.parameters:
            params["user_id"] = user_id
            
        result = await handler(pool, intent, data, **params)

        # UNIVERSAL SAFETY WRAPPER: Force result to (text, markup, item_id)
        reply_text, markup, item_id = "", None, None
        if isinstance(result, tuple):
            reply_text = result[0]
            markup = result[1] if len(result) > 1 else None
            item_id = result[2] if len(result) > 2 else None
        else:
            reply_text = str(result)

        # Update state for future corrections/undo
        from core.state import set_state

        await set_state(pool, "null", module, intent, item_id)
        await log_execution(pool, intent, module, True)

        return reply_text, markup, item_id

    except Exception as e:
        logger.error(f"Module execution failed | module: {module} | error: {e}")
        traceback.print_exc()
        await log_execution(pool, intent, module, False, type(e).__name__, str(e))
        from bot.formatter import escape_md

        return f"⚠️ Eroare modul {module}: {escape_md(str(e))}", None, None
async def undo_last_action(pool, module, intent, item_id):
    """
    Calls the undo_last_action function of the specified module.
    """
    try:
        mod = importlib.import_module(f"modules.{module}")
        if hasattr(mod, "undo_last_action"):
            return await mod.undo_last_action(pool, intent, item_id)
        return False, f"Modulul '{module}' nu suportă anularea acțiunilor."
    except Exception as e:
        logger.error(f"Undo failed | module: {module} | error: {e}")
        return False, str(e)
