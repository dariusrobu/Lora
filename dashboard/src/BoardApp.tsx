import { useState, useEffect, useRef, useCallback } from 'react';
import {
  CheckCircle2, Wallet, Heart, Dumbbell, Droplets, Moon,
  Sun, Cloud, CloudRain, CloudDrizzle, CloudSnow, CloudLightning,
  Briefcase, TrendingUp, Calendar, Flame, RefreshCw,
  GraduationCap, Zap, ArrowRight, Activity
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ─── Config ─────────────────────────────────────────────────────────────────
const API_SECRET = import.meta.env.VITE_LORA_API_SECRET || '73860b29fd5d087fd78a1e59fb23254ed1692139e933a9465de82ed709b7f70e';
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://lora-bot-tgbi.onrender.com';
const BASE_URL = RAW_BASE_URL.endsWith('/') ? RAW_BASE_URL.slice(0, -1) : RAW_BASE_URL;
const HEADERS = {
  'X-Internal-Secret': API_SECRET,
  'Content-Type': 'application/json',
  'Bypass-Tunnel-Reminder': 'true'
};
const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minute

// ─── Types ────────────────────────────────────────────────────────────────────
interface Task { id: number; title: string; status: string; priority: string; project_name?: string; }
interface ScheduleItem { id: number; subject_name: string; start_time: string; end_time: string; room?: string; }
interface Project { id: number; name: string; progress?: number; }
interface HealthLog { sleep_hours?: number; water_ml?: number; weight_kg?: number; logged_at?: string; }
interface WeatherData {
  name: string;
  main: { temp: number; humidity: number; feels_like: number; };
  weather: { main: string; description: string; }[];
  wind: { speed: number; };
}
interface FinanceSummary { balance: number; today_spent?: number; month_spent?: number; }
interface UniSummary { average_grade?: number; subjects?: { name: string; }[]; }
interface WorkoutStats { summary?: { total_sessions: number; }; }

interface BoardData {
  tasks: Task[];
  finance: FinanceSummary | null;
  uniSummary: UniSummary | null;
  gymStats: WorkoutStats | null;
  healthLogs: HealthLog[];
  calendarToday: { schedule?: ScheduleItem[] } | null;
  weather: WeatherData | null;
  projects: Project[];
}

// ─── Fetch helper ─────────────────────────────────────────────────────────────
async function fetchModule<T>(url: string, defaultValue: T): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);
  try {
    const fullUrl = `${url.startsWith('http') ? url : BASE_URL + url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`;
    const r = await fetch(fullUrl, { headers: HEADERS, signal: controller.signal });
    clearTimeout(timeoutId);
    if (!r.ok) return defaultValue;
    return await r.json();
  } catch {
    clearTimeout(timeoutId);
    return defaultValue;
  }
}

// ─── Clock Widget ─────────────────────────────────────────────────────────────
function ClockWidget() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const timeStr = now.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = now.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none" />
      <div className="label-ethereal opacity-50">Sistem Activ</div>
      <div className="space-y-2">
        <motion.div
          key={timeStr}
          className="font-thin tracking-tighter text-white"
          style={{ fontSize: 'clamp(3.5rem, 6vw, 7rem)', lineHeight: 1 }}
        >
          {timeStr}
        </motion.div>
        <p className="text-sm font-light text-[#adc6ff] capitalize tracking-wide">{dateStr}</p>
      </div>
      <div className="flex gap-2 items-center">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <span className="label-ethereal text-emerald-400">Online</span>
      </div>
    </div>
  );
}

// ─── Weather Widget ────────────────────────────────────────────────────────────
function WeatherWidget({ weather }: { weather: WeatherData | null }) {
  if (!weather) return (
    <div className="liquid-panel rounded-[28px] p-8 flex items-center justify-center h-full">
      <p className="label-ethereal opacity-20">Meteo indisponibil</p>
    </div>
  );

  const WeatherIcon = () => {
    const main = weather.weather?.[0]?.main;
    const cls = "drop-shadow-[0_0_20px_currentColor]";
    if (main === 'Clear') return <Sun className={`text-yellow-400 ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
    if (main === 'Clouds') return <Cloud className={`text-blue-300 ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
    if (main === 'Rain') return <CloudRain className={`text-blue-500 ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
    if (main === 'Drizzle') return <CloudDrizzle className={`text-blue-400 ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
    if (main === 'Snow') return <CloudSnow className={`text-white ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
    return <CloudLightning className={`text-purple-400 ${cls}`} style={{ width: '4rem', height: '4rem' }} />;
  };

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-sky-500/5 to-transparent pointer-events-none" />
      <div className="flex justify-between items-start">
        <div className="label-ethereal opacity-50">{weather.name}</div>
        <motion.div animate={{ y: [0, -6, 0] }} transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}>
          <WeatherIcon />
        </motion.div>
      </div>
      <div>
        <p className="font-thin text-white" style={{ fontSize: 'clamp(3rem, 5vw, 6rem)', lineHeight: 1 }}>
          {Math.round(weather.main?.temp)}°C
        </p>
        <p className="text-[#adc6ff] text-sm mt-1 capitalize">{weather.weather?.[0]?.description}</p>
      </div>
      <div className="flex gap-6 text-xs text-gray-500 font-bold uppercase tracking-widest">
        <span>Umid. {weather.main?.humidity}%</span>
        <span>Vânt {weather.wind?.speed} m/s</span>
        <span>Simte ca {Math.round(weather.main?.feels_like)}°</span>
      </div>
    </div>
  );
}

// ─── Tasks Widget ─────────────────────────────────────────────────────────────
function TasksWidget({ tasks }: { tasks: Task[] }) {
  const active = tasks.filter(t => t.status !== 'done').slice(0, 6);
  const priorityColor: Record<string, string> = {
    high: 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.6)]',
    medium: 'bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.4)]',
    low: 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.4)]'
  };

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col h-full gap-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          <span className="label-ethereal text-base">Priorități Active</span>
        </div>
        <span className="text-sm font-black text-[#adc6ff] tabular-nums">{active.length}</span>
      </div>
      <div className="flex flex-col gap-5 flex-1 overflow-hidden mt-2">
        <AnimatePresence>
          {active.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <p className="label-ethereal opacity-20 text-lg">Toate taskurile completate ✓</p>
            </div>
          ) : (
            active.map((t, i) => (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-5 group"
              >
                <div className={`w-3 h-3 rounded-full flex-shrink-0 ${priorityColor[t.priority] || 'bg-gray-500'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xl font-medium text-white/90 truncate leading-tight">{t.title}</p>
                  {t.project_name && (
                    <p className="text-xs font-black uppercase tracking-widest text-[#8c909f] mt-1">{t.project_name}</p>
                  )}
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─── Schedule Widget ───────────────────────────────────────────────────────────
function ScheduleWidget({ calendarToday }: { calendarToday: { schedule?: ScheduleItem[] } | null }) {
  const schedule = calendarToday?.schedule || [];
  const now = new Date();

  const isActive = (item: ScheduleItem) => {
    const [sh, sm] = item.start_time.split(':').map(Number);
    const [eh, em] = item.end_time.split(':').map(Number);
    const start = sh * 60 + sm;
    const end = eh * 60 + em;
    const current = now.getHours() * 60 + now.getMinutes();
    return current >= start && current <= end;
  };

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col h-full gap-6">
      <div className="flex items-center gap-3">
        <Calendar className="w-4 h-4 text-sky-400" />
        <span className="label-ethereal">Program Azi</span>
      </div>
      <div className="flex flex-col gap-3 flex-1 overflow-hidden">
        {schedule.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-2">
              <p className="label-ethereal opacity-20">Weekend Mode</p>
              <p className="text-xs text-gray-600">Niciun curs detectat</p>
            </div>
          </div>
        ) : (
          schedule.map((s, i) => {
            const active = isActive(s);
            return (
              <motion.div
                key={s.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.07 }}
                className={`flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                  active ? 'bg-sky-500/10 border border-sky-500/20' : 'bg-white/[0.02]'
                }`}
              >
                <div className="w-12 text-center flex-shrink-0">
                  <p className={`text-xs font-black tabular-nums ${active ? 'text-sky-400' : 'text-[#adc6ff]'}`}>
                    {s.start_time.slice(0, 5)}
                  </p>
                  {active && <div className="w-1 h-1 rounded-full bg-sky-400 animate-pulse mx-auto mt-1" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${active ? 'text-white' : 'text-white/70'}`}>{s.subject_name}</p>
                  {s.room && <p className="text-[9px] text-gray-600 font-bold uppercase tracking-widest mt-0.5">{s.room}</p>}
                </div>
                {active && <div className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />}
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Finance Widget ────────────────────────────────────────────────────────────
function FinanceWidget({ finance }: { finance: FinanceSummary | null }) {
  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent pointer-events-none" />
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-3">
          <Wallet className="w-4 h-4 text-emerald-400" />
          <span className="label-ethereal">Tezaur</span>
        </div>
        <TrendingUp className="w-4 h-4 text-emerald-500/30" />
      </div>
      <div className="space-y-2">
        <p className="label-ethereal opacity-30">Balanță Curentă</p>
        <p className="font-thin text-white tabular-nums" style={{ fontSize: 'clamp(2rem, 3.5vw, 4rem)', lineHeight: 1 }}>
          {(finance?.balance ?? 0).toLocaleString('ro-RO', { minimumFractionDigits: 0 })}
          <span className="text-base font-bold text-white/20 ml-2">LEI</span>
        </p>
      </div>
      {finance?.today_spent !== undefined && finance.today_spent > 0 && (
        <div className="flex gap-2 items-center">
          <ArrowRight className="w-3 h-3 text-red-400" />
          <span className="text-xs text-gray-500 font-bold">
            Azi: <span className="text-red-400">{finance.today_spent} lei</span>
          </span>
        </div>
      )}
      {/* Sparkline placeholder */}
      <svg className="w-full h-8 opacity-20">
        <path d="M0,24 Q20,8 40,16 T80,12 T120,20 T160,8 T200,18 T240,6 T280,14" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

// ─── Health Widget ─────────────────────────────────────────────────────────────
function HealthWidget({ healthLogs, gymStats }: { healthLogs: HealthLog[]; gymStats: WorkoutStats | null }) {
  const latest = healthLogs[0];
  const sleep = latest?.sleep_hours;
  const water = latest?.water_ml ?? 0;
  const waterPct = Math.min((water / 2500) * 100, 100);
  const sessions = gymStats?.summary?.total_sessions ?? 0;

  const sleepColor = sleep == null ? 'text-gray-500' : sleep >= 7 ? 'text-emerald-400' : sleep >= 6 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col h-full gap-5 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-pink-500/5 to-transparent pointer-events-none" />
      <div className="flex items-center gap-3">
        <Activity className="w-4 h-4 text-pink-400" />
        <span className="label-ethereal">Vitals</span>
      </div>

      {/* Sleep */}
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center flex-shrink-0">
          <Moon className="w-5 h-5 text-purple-400" />
        </div>
        <div className="flex-1">
          <p className="label-ethereal opacity-40">Somn</p>
          <p className={`text-2xl font-bold tracking-tight ${sleepColor}`}>
            {sleep != null ? `${sleep}h` : '—'}
          </p>
        </div>
      </div>

      {/* Water */}
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center flex-shrink-0">
          <Droplets className="w-5 h-5 text-blue-400" />
        </div>
        <div className="flex-1">
          <p className="label-ethereal opacity-40">Apă</p>
          <p className="text-2xl font-bold tracking-tight text-blue-400">{water}ml</p>
          <div className="w-full h-1 bg-white/5 rounded-full mt-2 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${waterPct}%` }}
              transition={{ duration: 1.2, ease: 'easeOut' }}
              className="h-full bg-blue-500 rounded-full"
            />
          </div>
        </div>
      </div>

      {/* Gym */}
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center flex-shrink-0">
          <Dumbbell className="w-5 h-5 text-red-400" />
        </div>
        <div className="flex-1">
          <p className="label-ethereal opacity-40">Workout</p>
          <p className="text-2xl font-bold tracking-tight text-red-400">{sessions} sesiuni</p>
        </div>
      </div>

      {/* Heart */}
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-pink-500/10 flex items-center justify-center flex-shrink-0">
          <Heart className="w-5 h-5 text-pink-400" />
        </div>
        <div className="flex-1">
          <p className="label-ethereal opacity-40">Health Score</p>
          <div className="flex gap-1 mt-1">
            {[1,2,3,4,5].map(i => (
              <div key={i} className={`h-1.5 flex-1 rounded-full ${
                i <= Math.round(((sleep ?? 0) / 8) * 5) ? 'bg-pink-500' : 'bg-white/5'
              }`} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Projects Widget ───────────────────────────────────────────────────────────
function ProjectsWidget({ projects, tasks }: { projects: Project[]; tasks: Task[] }) {
  const active = projects.slice(0, 5);

  const getTaskCount = (projectName: string) =>
    tasks.filter(t => t.project_name === projectName && t.status !== 'done').length;

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col h-full gap-6">
      <div className="flex items-center gap-3">
        <Briefcase className="w-4 h-4 text-indigo-400" />
        <span className="label-ethereal">Proiecte Active</span>
        <div className="h-px flex-1 bg-white/5" />
        <span className="text-xs font-black text-[#adc6ff]">{active.length}</span>
      </div>
      <div className="flex flex-col gap-4 flex-1">
        {active.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="label-ethereal opacity-20">Niciun proiect activ</p>
          </div>
        ) : (
          active.map((p, i) => {
            const pct = p.progress ?? Math.min(getTaskCount(p.name) * 10, 100);
            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="space-y-2"
              >
                <div className="flex justify-between items-center">
                  <p className="text-sm font-medium text-white/80 truncate max-w-[70%]">{p.name}</p>
                  <span className="text-xs font-black text-[#adc6ff] tabular-nums">{pct}%</span>
                </div>
                <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 1, delay: i * 0.1, ease: 'easeOut' }}
                    className="h-full rounded-full"
                    style={{
                      background: `hsl(${220 + i * 20}, 70%, 65%)`,
                      boxShadow: `0 0 8px hsl(${220 + i * 20}, 70%, 65%, 0.4)`
                    }}
                  />
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Uni Widget ────────────────────────────────────────────────────────────────
function UniWidget({ uniSummary }: { uniSummary: UniSummary | null }) {
  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-transparent pointer-events-none" />
      <div className="flex items-center gap-3">
        <GraduationCap className="w-4 h-4 text-amber-400" />
        <span className="label-ethereal">Academic</span>
      </div>
      <div>
        <p className="label-ethereal opacity-30 mb-1">Medie Generală</p>
        <p className="font-thin text-amber-400" style={{ fontSize: 'clamp(3rem, 4vw, 5rem)', lineHeight: 1 }}>
          {uniSummary?.average_grade ?? '—'}
        </p>
      </div>
      <div className="flex gap-2 flex-wrap">
        {uniSummary?.subjects?.slice(0, 4).map((s, i) => (
          <span key={i} className="px-2 py-1 rounded-lg bg-amber-500/10 text-[9px] font-black uppercase text-amber-400 tracking-wide truncate max-w-[120px]">
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Status Bar ───────────────────────────────────────────────────────────────
function StatusBar({ lastUpdate, refreshing, onRefresh }: { lastUpdate: Date | null; refreshing: boolean; onRefresh: () => void; }) {
  const timeStr = lastUpdate?.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex justify-between items-center px-2 py-1">
      <div className="flex items-center gap-3">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <span className="label-ethereal text-emerald-400 opacity-60">LORA AMBIENT BOARD</span>
      </div>
      <div className="flex items-center gap-4">
        {timeStr && <span className="label-ethereal opacity-30">Sincronizat la {timeStr}</span>}
        <button
          onClick={onRefresh}
          className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-all border border-white/5"
        >
          <RefreshCw className={`w-3 h-3 text-gray-500 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </div>
  );
}

// ─── Skills/Streaks Widget ─────────────────────────────────────────────────────
function StreaksWidget({ tasks }: { tasks: Task[] }) {
  const done = tasks.filter(t => t.status === 'done').length;
  const total = tasks.length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="liquid-panel rounded-[28px] p-8 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent pointer-events-none" />
      <div className="flex items-center gap-3">
        <Flame className="w-4 h-4 text-orange-400" />
        <span className="label-ethereal">Progres Azi</span>
      </div>
      <div className="flex flex-col items-center justify-center gap-4 flex-1 py-4">
        {/* Circular progress */}
        <div className="relative w-28 h-28">
          <svg className="w-full h-full -rotate-90">
            <circle cx="56" cy="56" r="48" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="6" />
            <motion.circle
              cx="56" cy="56" r="48"
              fill="none"
              stroke="#f97316"
              strokeWidth="6"
              strokeLinecap="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: pct / 100 }}
              transition={{ duration: 1.5, ease: 'easeOut' }}
              style={{ filter: 'drop-shadow(0 0 8px rgba(249,115,22,0.5))' }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-black text-orange-400">{pct}%</span>
            <span className="text-[9px] font-black uppercase tracking-widest text-gray-600">Done</span>
          </div>
        </div>
        <p className="text-xs text-gray-500 font-bold">
          {done} / {total} taskuri
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Zap className="w-3 h-3 text-orange-400" />
        <span className="text-[10px] font-black uppercase tracking-widest text-orange-400/60">Keep going</span>
      </div>
    </div>
  );
}

// ─── Main Board ───────────────────────────────────────────────────────────────
export default function BoardApp() {
  const [data, setData] = useState<BoardData>({
    tasks: [], finance: null, uniSummary: null, gymStats: null,
    healthLogs: [], calendarToday: null, weather: null, projects: []
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    setRefreshing(true);
    try {
      const [tasks, finance, uniSummary, gymStats, healthLogs, calendarToday, weather, projects] = await Promise.all([
        fetchModule<Task[]>('/api/tasks?status=all', []),
        fetchModule<FinanceSummary | null>('/api/finances/summary', null),
        fetchModule<UniSummary | null>('/api/university/summary', null),
        fetchModule<WorkoutStats | null>('/api/workout/stats', null),
        fetchModule<HealthLog[]>('/api/health/summary', []),
        fetchModule<{ schedule?: ScheduleItem[] } | null>('/api/calendar/today', null),
        fetchModule<WeatherData | null>('/api/weather', null),
        fetchModule<Project[]>('/api/projects', []),
      ]);
      setData({ tasks, finance, uniSummary, gymStats, healthLogs, calendarToday, weather, projects });
      setLastUpdate(new Date());
    } catch (e) {
      console.error('Board fetch error:', e);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    refreshRef.current = setInterval(loadData, REFRESH_INTERVAL);
    return () => { if (refreshRef.current) clearInterval(refreshRef.current); };
  }, [loadData]);

  if (loading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#050505] gap-8">
        <motion.div
          animate={{ scale: [0.9, 1.1, 0.9], opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 3, repeat: Infinity }}
          className="w-20 h-20 liquid-panel rounded-full flex items-center justify-center"
        >
          <div className="w-6 h-6 border-2 border-[#adc6ff] border-t-transparent rounded-full animate-spin" />
        </motion.div>
        <p className="label-ethereal animate-pulse">Inițializare panou de bord...</p>
      </div>
    );
  }

  const { tasks, finance, uniSummary, gymStats, healthLogs, calendarToday, weather, projects } = data;

  return (
    <div className="min-h-screen text-white font-sans overflow-hidden selection:bg-[#3b82f6]/30">
      {/* Ambient Aura */}
      <div className="aura-container">
        <div className="aura-blob aura-1" style={{ opacity: 0.08 }} />
        <div className="aura-blob aura-2" style={{ opacity: 0.08 }} />
        <div className="aura-blob aura-3" style={{ opacity: 0.06 }} />
      </div>

      {/* Board Layout */}
      <div
        className="relative z-10 p-4 flex flex-col gap-4"
        style={{ minHeight: '100vh' }}
      >
        {/* Status bar */}
        <StatusBar lastUpdate={lastUpdate} refreshing={refreshing} onRefresh={loadData} />

        {/* Main grid */}
        <div
          className="flex-1 grid gap-4"
          style={{
            gridTemplateColumns: 'repeat(4, 1fr)',
            gridTemplateRows: 'repeat(3, 1fr)',
            minHeight: 'calc(100vh - 60px)',
          }}
        >
          {/* Row 1 */}
          {/* Clock — span 2 */}
          <div style={{ gridColumn: '1 / 3', gridRow: '1' }}>
            <ClockWidget />
          </div>
          {/* Weather */}
          <div style={{ gridColumn: '3', gridRow: '1' }}>
            <WeatherWidget weather={weather} />
          </div>
          {/* Finance */}
          <div style={{ gridColumn: '4', gridRow: '1' }}>
            <FinanceWidget finance={finance} />
          </div>

          {/* Row 2 */}
          {/* Tasks */}
          <div style={{ gridColumn: '1', gridRow: '2' }}>
            <TasksWidget tasks={tasks} />
          </div>
          {/* Schedule — span 2 */}
          <div style={{ gridColumn: '2 / 4', gridRow: '2' }}>
            <ScheduleWidget calendarToday={calendarToday} />
          </div>
          {/* Health */}
          <div style={{ gridColumn: '4', gridRow: '2' }}>
            <HealthWidget healthLogs={healthLogs} gymStats={gymStats} />
          </div>

          {/* Row 3 */}
          {/* Projects — span 2 */}
          <div style={{ gridColumn: '1 / 3', gridRow: '3' }}>
            <ProjectsWidget projects={projects} tasks={tasks} />
          </div>
          {/* Uni */}
          <div style={{ gridColumn: '3', gridRow: '3' }}>
            <UniWidget uniSummary={uniSummary} />
          </div>
          {/* Progress */}
          <div style={{ gridColumn: '4', gridRow: '3' }}>
            <StreaksWidget tasks={tasks} />
          </div>
        </div>
      </div>
    </div>
  );
}
