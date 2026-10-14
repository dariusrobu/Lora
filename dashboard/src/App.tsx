import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom"
import { lazy, Suspense, useEffect } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { Layout } from "./components/layout/Layout"
import DailyHome from "./pages/daily/DailyHome"
import DailyCalendar from "./pages/daily/DailyCalendar"
import ProjectBoard from "./pages/daily/ProjectBoard"
import Journal from "./pages/daily/Journal"
import More from "./pages/daily/More"

const Dashboard = lazy(() => import("./pages/Dashboard"))
const Plan = lazy(() => import("./pages/Plan"))
const Body = lazy(() => import("./pages/Body"))
const Mind = lazy(() => import("./pages/Mind"))
const Life = lazy(() => import("./pages/Life"))
const University = lazy(() => import("./pages/University"))
const Tasks = lazy(() => import("./pages/Tasks"))
const Notes = lazy(() => import("./pages/Notes"))
const Goals = lazy(() => import("./pages/Goals"))
const Finance = lazy(() => import("./pages/Finance"))
const Health = lazy(() => import("./pages/Health"))
const Shopping = lazy(() => import("./pages/Shopping"))
const Calendar = lazy(() => import("./pages/Calendar"))
const Weather = lazy(() => import("./pages/Weather"))
const Mood = lazy(() => import("./pages/Mood"))
const Insights = lazy(() => import("./pages/Insights"))
const Memory = lazy(() => import("./pages/Memory"))
const Focus = lazy(() => import("./pages/Focus"))
const Reading = lazy(() => import("./pages/Reading"))
const Skills = lazy(() => import("./pages/Skills"))
const Workout = lazy(() => import("./pages/Workout"))
const Nutrition = lazy(() => import("./pages/Nutrition"))
const Places = lazy(() => import("./pages/Places"))
const Travel = lazy(() => import("./pages/Travel"))
const News = lazy(() => import("./pages/News"))
const Login = lazy(() => import("./pages/Login"))
const KioskPage = lazy(() => import("./pages/Kiosk"))
const SpacePage = lazy(() => import("./pages/Space"))
const Chat = lazy(() => import("./pages/Chat"))

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const isTelegramMiniApp = Boolean((window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData)

export default function App() {
  useEffect(() => {
    // Older kiosk links put the JWT in the URL. Remove it immediately so it
    // cannot leak through browser history or HTTP Referer headers.
    const params = new URLSearchParams(window.location.search)
    if (params.has("token")) {
      params.delete("token")
      const query = params.toString()
      window.history.replaceState({}, document.title, `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`)
    }
  }, [])

  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ErrorBoundary>
          <Suspense fallback={<div className="daily-route-loading" role="status">Se încarcă…</div>}><Routes>
            <Route path="/login" element={isTelegramMiniApp ? <Navigate to="/" replace /> : <Login />} />
            <Route path="/kiosk" element={<KioskPage />} />
            <Route element={<Layout />}>
              <Route index element={<DailyHome />} />
              <Route path="plan" element={<Plan />} />
              <Route path="body" element={<Body />} />
              <Route path="mind" element={<Mind />} />
              <Route path="life" element={<Life />} />
              <Route path="university" element={<University />} />
              <Route path="tasks" element={<Tasks />} />
              <Route path="notes" element={<Notes />} />
              <Route path="goals" element={<Goals />} />
              <Route path="finance" element={<Finance />} />
              <Route path="health" element={<Health />} />
              <Route path="shopping" element={<Shopping />} />
              <Route path="calendar" element={<DailyCalendar />} />
              <Route path="projects" element={<ProjectBoard />} />
              <Route path="journal" element={<Journal />} />
              <Route path="more" element={<More />} />
              <Route path="overview" element={<Dashboard />} />
              <Route path="calendar-legacy" element={<Calendar />} />
              <Route path="weather" element={<Weather />} />
              <Route path="mood" element={<Mood />} />
              <Route path="insights" element={<Insights />} />
              <Route path="memory" element={<Memory />} />
              <Route path="focus" element={<Focus />} />
              <Route path="reading" element={<Reading />} />
              <Route path="skills" element={<Skills />} />
              <Route path="workout" element={<Workout />} />
              <Route path="nutrition" element={<Nutrition />} />
              <Route path="places" element={<Places />} />
              <Route path="travel" element={<Travel />} />
              <Route path="news" element={<News />} />
              <Route path="space" element={<SpacePage />} />
              <Route path="chat" element={<Chat />} />
              <Route path="*" element={<DailyHome />} />
            </Route>
          </Routes></Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
