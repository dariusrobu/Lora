import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { login } from "../api/auth"
import { ArrowLeft, LockKeyhole } from "lucide-react"
import { Link } from "react-router-dom"
import "../components/layout/daily.css"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")
    try {
      const token = await login(email, password)
      localStorage.setItem("lora_token", token)
      navigate("/")
    } catch {
      setError("Nu te-am putut conecta. Verifică adresa și parola.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="daily-shell daily-login-screen"><Link to="/" className="daily-login-back"><ArrowLeft size={17} /> Înapoi</Link><div className="daily-panel daily-login-card"><span className="daily-auth-icon"><LockKeyhole size={24} /></span><p className="daily-eyebrow">SPAȚIUL TĂU</p><h1>Conectează-te</h1><p className="daily-subtitle">Calendarul, taskurile și restul zilei tale sunt aici.</p><form onSubmit={handleSubmit} className="daily-login-form"><label className="daily-field"><span>Adresa contului</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label><label className="daily-field"><span>Parola</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>{error && <p className="daily-inline-error" role="alert">{error}</p>}<button className="daily-primary-button" type="submit" disabled={loading}>{loading ? "Se conectează…" : "Intră în Lora"}</button></form></div></div>
  )
}
