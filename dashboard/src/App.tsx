import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { Layout } from "./components/layout/Layout"
import Dashboard from "./pages/Dashboard"
import Plan from "./pages/Plan"
import Body from "./pages/Body"
import Mind from "./pages/Mind"
import Life from "./pages/Life"
import University from "./pages/University"
import Tasks from "./pages/Tasks"
import Notes from "./pages/Notes"
import Goals from "./pages/Goals"
import Finance from "./pages/Finance"
import Health from "./pages/Health"
import Shopping from "./pages/Shopping"
import Calendar from "./pages/Calendar"
import Weather from "./pages/Weather"
import Mood from "./pages/Mood"
import Insights from "./pages/Insights"
import Memory from "./pages/Memory"
import Focus from "./pages/Focus"
import Reading from "./pages/Reading"
import Skills from "./pages/Skills"
import Workout from "./pages/Workout"
import Nutrition from "./pages/Nutrition"
import Places from "./pages/Places"
import Travel from "./pages/Travel"
import Login from "./pages/Login"
import KioskPage from "./pages/Kiosk"
import SpacePage from "./pages/Space"

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/kiosk" element={<KioskPage />} />
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
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
              <Route path="calendar" element={<Calendar />} />
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
              <Route path="space" element={<SpacePage />} />
              <Route path="*" element={<Dashboard />} />
            </Route>
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
