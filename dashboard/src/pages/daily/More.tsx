import { Link } from "react-router-dom"
import { ArrowUpRight, BookOpen, Brain, CloudSun, Compass, Focus, Heart, Lightbulb, ListChecks, MessageCircle, Newspaper, Settings2, ShoppingBasket, Sparkles, Trophy } from "lucide-react"

const groups = [
  { title: "Organizare", links: [
    { to: "/tasks", label: "Toate taskurile", icon: ListChecks },
    { to: "/shopping", label: "Cumpărături", icon: ShoppingBasket },
    { to: "/notes", label: "Note", icon: BookOpen },
    { to: "/goals", label: "Obiective", icon: Lightbulb },
    { to: "/plan", label: "Plan extins", icon: ListChecks },
  ] },
  { title: "Personal", links: [
    { to: "/focus", label: "Focus", icon: Focus },
    { to: "/reading", label: "Lectură", icon: BookOpen },
    { to: "/mood", label: "Stare", icon: Brain },
    { to: "/life", label: "Călătorii și locuri", icon: Compass },
    { to: "/skills", label: "Abilități", icon: Trophy },
    { to: "/body", label: "Corp și sănătate", icon: Heart },
  ] },
  { title: "Lora", links: [
    { to: "/chat", label: "Vorbește cu Lora", icon: MessageCircle },
    { to: "/insights", label: "Observații", icon: Sparkles },
    { to: "/memory", label: "Memorie", icon: Brain },
    { to: "/space", label: "Setări și integrări", icon: Settings2 },
    { to: "/weather", label: "Vreme", icon: CloudSun },
    { to: "/news", label: "Știri", icon: Newspaper },
    { to: "/overview", label: "Privire generală", icon: Compass },
  ] },
]

export default function More() {
  return <div className="daily-page"><div className="daily-page-heading"><div><p className="daily-eyebrow">EXPLORARE</p><h1>Mai mult</h1><p className="daily-subtitle">Celelalte instrumente sunt aici când ai nevoie de ele.</p></div></div><div className="daily-more-grid">{groups.map((group) => <section className="daily-panel" key={group.title}><h2>{group.title}</h2><div className="daily-more-list">{group.links.map(({ to, label, icon: Icon }) => <Link to={to} key={to}><Icon size={18} /><span>{label}</span><ArrowUpRight size={15} /></Link>)}</div></section>)}</div></div>
}
