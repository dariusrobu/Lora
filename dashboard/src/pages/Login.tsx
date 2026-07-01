import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { login } from "../api/auth"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Spinner } from "../components/ui/Spinner"

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
      setError("Email sau parolă incorectă")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4 transition-colors">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm"
      >
        <div className="text-center mb-8">
          <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-indigo-500 flex items-center justify-center text-2xl font-bold shadow-lg shadow-indigo-500/20 dark:shadow-black/30">
            L
          </div>
          <h1 className="text-2xl font-bold text-text-primary">Lora</h1>
          <p className="text-text-secondary text-sm mt-1">Your personal dashboard</p>
        </div>
        <form onSubmit={handleSubmit} className="rounded-2xl border border-border bg-surface backdrop-blur-xl p-6 space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Spinner size="sm" /> : "Sign in"}
          </Button>
        </form>
      </motion.div>
    </div>
  )
}
