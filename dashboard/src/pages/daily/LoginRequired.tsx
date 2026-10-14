import { Send } from "lucide-react"

export function LoginRequired() {
  return <div className="daily-page daily-auth-page"><div className="daily-panel daily-auth-panel"><span className="daily-auth-icon"><Send size={24} /></span><p className="daily-eyebrow">LORA MINI APP</p><h1>Deschide Lora din Telegram</h1><p className="daily-subtitle">Închide această fereastră și deschide din nou Mini App din conversația cu Lora. Accesul se face automat, fără cont sau parolă.</p></div></div>
}
