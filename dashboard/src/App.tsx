import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, Navigation, Plus, GraduationCap, 
  Dumbbell, Wallet, ArrowLeft, Loader2, Settings,
  Calendar, ShoppingCart, Heart, Flame, Brain, Play, Pause, RotateCcw,
  TrendingUp, Star, AlertTriangle, Moon, Droplets, Scale,
  Pin, MapPin, Search, Sun, Cloud, CloudRain, CloudDrizzle, CloudSnow, CloudLightning,
  Briefcase, Target, Zap
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Types & Constants ---
const API_SECRET = import.meta.env.VITE_LORA_API_SECRET || '73860b29fd5d087fd78a1e59fb23254ed1692139e933a9465de82ed709b7f70e';
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://lora-bot-tgbi.onrender.com';
const BASE_URL = RAW_BASE_URL.endsWith('/') ? RAW_BASE_URL.slice(0, -1) : RAW_BASE_URL;

const HEADERS = { 
  'X-Internal-Secret': API_SECRET, 
  'Content-Type': 'application/json',
  'Bypass-Tunnel-Reminder': 'true'
};

type View = 'home' | 'map' | 'uni' | 'gym' | 'skills' | 'shop' | 'notes' | 'health' | 'calendar' | 'finance' | 'tasks' | 'projects' | 'memory';

// --- Shared Components ---
const GlassCard = ({ children, className = "", onClick }: any) => (
  <motion.div 
    whileHover={onClick ? { scale: 1.02 } : {}}
    whileTap={onClick ? { scale: 0.98 } : {}}
    onClick={onClick}
    className={`relative overflow-hidden rounded-[24px] border border-white/[0.08] bg-[#0a0a0a] p-6 ${className} ${onClick ? 'cursor-pointer' : ''}`}
  >
    {children}
  </motion.div>
);

const ViewContainer = ({ children, title, onBack }: any) => (
  <motion.div 
    initial={{ x: 300, opacity: 0 }}
    animate={{ x: 0, opacity: 1 }}
    exit={{ x: -300, opacity: 0 }}
    className="fixed inset-0 bg-black z-[100] p-6 overflow-y-auto no-scrollbar"
  >
    <div className="flex justify-between items-center mb-8">
      <button onClick={onBack} className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
        <ArrowLeft className="w-5 h-5" />
      </button>
      <h2 className="text-sm font-black uppercase tracking-[0.3em] text-gray-400">{title}</h2>
      <div className="w-10" />
    </div>
    {children}
  </motion.div>
);

function App() {
  const [view, setView] = useState<View>('home');
  const [tasks, setTasks] = useState<any[]>([]);
  const [finance, setFinance] = useState<any>(null);
  const [uniSummary, setUniSummary] = useState<any>(null);
  const [gymStats, setGymStats] = useState<any>(null);
  const [skills, setSkills] = useState<any[]>([]);
  const [shopping, setShopping] = useState<any[]>([]);
  const [notes, setNotes] = useState<any[]>([]);
  const [healthLogs, setHealthLogs] = useState<any[]>([]);
  const [calendarToday, setCalendarToday] = useState<any>(null);
  const [financeHistory, setFinanceHistory] = useState<any[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [weather, setWeather] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [logValue, setLogValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  
  // Pomodoro
  const [timerActive, setTimerActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    fetchData();
    // Safety timeout: force loading to false after 15s no matter what
    const safety = setTimeout(() => setLoading(false), 15000);
    return () => clearTimeout(safety);
  }, []);

  useEffect(() => {
    if (timerActive && timeLeft > 0) {
      timerRef.current = setInterval(() => setTimeLeft(t => t - 1), 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [timerActive, timeLeft]);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchData = async () => {
    const fetchModule = async (url: string, defaultValue: any = null) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const fullUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`;
        const r = await fetch(fullUrl, { 
          headers: HEADERS,
          signal: controller.signal 
        });
        clearTimeout(timeoutId);
        if (!r.ok) {
           const errText = await r.text();
           console.error(`Error ${r.status} on ${url}: ${errText}`);
           return defaultValue;
        }
        return await r.json();
      } catch (e: any) {
        clearTimeout(timeoutId);
        console.error(`Failed to fetch ${url}:`, e);
        return defaultValue;
      }
    };

    try {
      setErrorMessage(null);
      const [t, f, u, g, s, shop, n, h, c, f_hist, prof, w, projs, mems] = await Promise.all([
        fetchModule('/api/tasks?status=all', []),
        fetchModule('/api/finances/summary'),
        fetchModule('/api/university/summary'),
        fetchModule('/api/workout/stats'),
        fetchModule('/api/skills', []),
        fetchModule('/api/shopping', []),
        fetchModule('/api/notes', []),
        fetchModule('/api/health/summary', []),
        fetchModule('/api/calendar/today'),
        fetchModule('/api/finances/history', []),
        fetchModule('/api/profile'),
        fetchModule('/api/weather'),
        fetchModule('/api/projects', []),
        fetchModule('/api/memory', [])
      ]);

      setTasks(t);
      setFinance(f);
      setUniSummary(u);
      setGymStats(g);
      setSkills(s);
      setShopping(shop);
      setNotes(n);
      setHealthLogs(h);
      setCalendarToday(c);
      setFinanceHistory(f_hist);
      setProfile(prof);
      setWeather(w);
      setProjects(projs);
      setMemories(mems);
    } catch (e: any) {
      console.error("Global fetch error:", e);
      setErrorMessage(e.message || "Eroare necunoscută la sincronizare");
    } finally {
      setLoading(false);
    }
  };

  const handleAddTask = async () => {
    if (!newTaskTitle) return;
    await fetch('/api/tasks', { method: 'POST', headers: HEADERS, body: JSON.stringify({ title: newTaskTitle, priority: 'medium' }) });
    setNewTaskTitle(''); setIsAddingTask(false);
    fetchData();
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (loading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#000] p-8 text-center space-y-6">
        <motion.div
           animate={{ scale: [1, 1.2, 1], opacity: [0.3, 1, 0.3] }}
           transition={{ duration: 2, repeat: Infinity }}
           className="w-12 h-12 text-blue-500"
        >
           <Loader2 className="w-full h-full animate-spin" />
        </motion.div>
        
        {errorMessage && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <p className="text-red-500 text-xs font-black uppercase tracking-widest leading-relaxed">
              Sincronizare Eșuată:<br/>{errorMessage}
            </p>
            <button 
              onClick={() => { setLoading(true); fetchData(); }}
              className="px-6 py-3 bg-white/5 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-colors"
            >
              Reîncearcă
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white font-sans overflow-x-hidden selection:bg-blue-500/30">
      
      <AnimatePresence mode="wait">
        {view === 'home' && (
          <motion.div 
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="p-6 pb-20 space-y-8 max-w-7xl mx-auto"
          >
            <header className="flex justify-between items-end">
              <div className="space-y-1">
                <h1 className="text-4xl font-black tracking-tighter">LORA<span className="text-blue-500">.</span></h1>
                <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">{tasks.length} Task-uri Active</p>
              </div>
              <button className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center"><Settings className="w-5 h-5 text-gray-400" /></button>
            </header>

            {/* Top Stats Scroll */}
            <div className="flex gap-4 overflow-x-auto no-scrollbar py-2">
              <GlassCard className="min-w-[160px] p-4 flex gap-3 items-center" onClick={() => setView('finance')}>
                <Wallet className="w-4 h-4 text-emerald-500" />
                <div>
                  <p className="text-[8px] font-black uppercase text-gray-500">Balanță</p>
                  <p className="text-sm font-black">{finance?.balance || 0} Lei</p>
                </div>
              </GlassCard>
              <GlassCard className="min-w-[160px] p-4 flex gap-3 items-center" onClick={() => setView('health')}>
                <Heart className="w-4 h-4 text-pink-500" />
                <div>
                  <p className="text-[8px] font-black uppercase text-gray-500">Vitals Azi</p>
                  <p className="text-[11px] font-black leading-tight mt-0.5">
                    {healthLogs[0]?.sleep_hours || '—'}h Somn • {healthLogs[0]?.water_ml || 0}ml
                  </p>
                  <p className="text-[9px] font-bold text-gray-500 uppercase mt-0.5">Nutriție: {healthLogs[0]?.nutrition || '—'}</p>
                </div>
              </GlassCard>
              <GlassCard className="min-w-[160px] p-4 flex gap-3 items-center" onClick={() => setView('gym')}>
                <Dumbbell className="w-4 h-4 text-red-500" />
                <div>
                  <p className="text-[8px] font-black uppercase text-gray-500">Antrenament</p>
                  <p className="text-sm font-black">{gymStats?.summary?.total_sessions || 0} Sesiuni</p>
                </div>
              </GlassCard>
            </div>
            
            {/* Weather Bento */}
            {weather && weather.main && (
              <section className="mt-8 mb-4">
                <GlassCard className="flex items-center justify-between p-6 overflow-hidden relative group border-blue-500/10">
                  <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-1">
                      <MapPin className="w-3 h-3 text-blue-500" />
                      <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">{weather.name}</span>
                    </div>
                    <div className="flex items-end gap-2">
                      <h3 className="text-5xl font-black text-white leading-none">{Math.round(weather.main?.temp)}°</h3>
                      <p className="text-xs font-bold text-gray-500 uppercase pb-1">{weather.weather?.[0]?.description}</p>
                    </div>
                  </div>
                  
                  <div className="relative z-10 text-right">
                    {weather.weather?.[0]?.main === 'Clear' && <Sun className="w-14 h-14 text-yellow-500 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]" />}
                    {weather.weather?.[0]?.main === 'Clouds' && <Cloud className="w-14 h-14 text-blue-300 drop-shadow-[0_0_15px_rgba(147,197,253,0.5)]" />}
                    {weather.weather?.[0]?.main === 'Rain' && <CloudRain className="w-14 h-14 text-blue-500" />}
                    {weather.weather?.[0]?.main === 'Drizzle' && <CloudDrizzle className="w-14 h-14 text-blue-400" />}
                    {weather.weather?.[0]?.main === 'Snow' && <CloudSnow className="w-14 h-14 text-white" />}
                    {['Thunderstorm', 'Mist', 'Fog', 'Haze'].includes(weather.weather?.[0]?.main) && <CloudLightning className="w-14 h-14 text-purple-400" />}
                  </div>

                  {/* Decorative circle */}
                  <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-blue-500/10 rounded-full blur-3xl group-hover:bg-blue-500/20 transition-all duration-700" />
                </GlassCard>
              </section>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              
              {/* Left Column: Modules & Focus (Desktop) */}
              <div className="lg:col-span-4 space-y-8">
                {/* Module Hub (Desktop: Sidebar-ish, Mobile: Grid) */}
                <section className="space-y-4">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2">Sisteme Lora</h3>
                  <div className="grid grid-cols-4 lg:grid-cols-2 gap-4">
                    {[
                      { id: 'tasks', icon: CheckCircle2, label: 'Tasks', color: 'text-emerald-400' },
                      { id: 'projects', icon: Briefcase, label: 'Proiecte', color: 'text-indigo-400' },
                      { id: 'map', icon: MapPin, label: 'Hartă', color: 'text-blue-500' },
                      { id: 'finance', icon: Wallet, label: 'Bani', color: 'text-emerald-500' },
                      { id: 'uni', icon: GraduationCap, label: 'Academic', color: 'text-orange-500' },
                      { id: 'gym', icon: Dumbbell, label: 'Sală', color: 'text-red-500' },
                      { id: 'skills', icon: Flame, label: 'Skills', color: 'text-yellow-500' },
                      { id: 'shop', icon: ShoppingCart, label: 'Shop', color: 'text-purple-500' },
                      { id: 'memory', icon: Brain, label: 'Memorie', color: 'text-emerald-500' },
                      { id: 'notes', icon: Target, label: 'Brain', color: 'text-blue-500' },
                      { id: 'health', icon: Heart, label: 'Sănătate', color: 'text-pink-500' },
                      { id: 'calendar', icon: Calendar, label: 'Plan', color: 'text-blue-400' }
                    ].map(m => (
                      <button key={m.id} onClick={() => setView(m.id as View)} className="flex lg:flex-row flex-col items-center gap-3 p-3 lg:bg-white/[0.03] lg:border lg:border-white/5 lg:rounded-2xl hover:bg-white/10 transition-all">
                        <div className="w-10 h-10 lg:w-8 lg:h-8 rounded-xl bg-white/[0.05] flex items-center justify-center">
                          <m.icon className={`w-5 h-5 lg:w-4 lg:h-4 ${m.color}`} />
                        </div>
                        <span className="text-[8px] lg:text-[10px] font-black uppercase tracking-widest text-gray-400">{m.label}</span>
                      </button>
                    ))}
                  </div>
                </section>

                <GlassCard className="h-44 flex flex-col justify-between border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-500">Focus OS</p>
                  <div className="text-center space-y-2">
                    <p className="text-3xl font-black tracking-tighter">{formatTime(timeLeft)}</p>
                    <div className="flex justify-center gap-2">
                      <button onClick={() => setTimerActive(!timerActive)} className="p-2 bg-blue-500/10 rounded-full">{timerActive ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}</button>
                      <button onClick={() => setTimeLeft(25 * 60)} className="p-2 bg-white/5 rounded-full"><RotateCcw className="w-4 h-4" /></button>
                    </div>
                  </div>
                </GlassCard>
              </div>

              {/* Middle Column: Priorities & Add Task */}
              <div className="lg:col-span-5 space-y-8">
                <GlassCard className="h-44 flex flex-col justify-between bg-blue-600 shadow-[0_20px_50px_rgba(37,99,235,0.2)] border-none" onClick={() => setIsAddingTask(true)}>
                  <p className="text-[8px] font-black uppercase tracking-widest text-blue-100">Quick Entry</p>
                  <div className="flex items-center gap-6">
                    <div className="w-16 h-16 rounded-3xl bg-white/20 backdrop-blur-md flex items-center justify-center"><Plus className="w-8 h-8" /></div>
                    <div>
                      <p className="text-2xl font-black leading-none">Ceva nou?</p>
                      <p className="text-[10px] font-bold text-blue-100 uppercase tracking-widest mt-2">Adaugă un task sau o idee</p>
                    </div>
                  </div>
                </GlassCard>

                <section className="space-y-4">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2 flex justify-between items-center">
                    <span>{tasks.filter(t => t.priority === 'high' && t.status !== 'done').length > 0 ? 'Priorități Critice' : 'Project Pulse / Overview'}</span>
                    <span className="bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded text-[8px]">{tasks.filter(t => t.status !== 'done').length} Total</span>
                  </h3>
                  
                  <div className="space-y-3">
                    {tasks.filter(t => t.priority === 'high' && t.status !== 'done').length > 0 ? (
                      // --- CRISIS MODE: High Priority Tasks ---
                      tasks.filter(t => t.priority === 'high' && t.status !== 'done').slice(0, 5).map(t => (
                        <GlassCard key={t.id} className="p-5 flex items-center gap-4 border-l-4 border-l-red-500 hover:bg-white/[0.04]" onClick={() => fetch(`/api/tasks/${t.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ action: 'complete' }) }).then(fetchData)}>
                          <div className="w-6 h-6 rounded-full border-2 border-red-500/20 flex items-center justify-center">
                            <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_12px_#ef4444]" />
                          </div>
                          <div className="flex-1">
                            <p className="font-bold text-base leading-tight">{t.title}</p>
                            {t.project_name && <p className="text-[10px] text-gray-500 font-bold uppercase mt-1">Proiect: {t.project_name}</p>}
                          </div>
                        </GlassCard>
                      ))
                    ) : (
                      // --- OVERVIEW MODE: Project Summary ---
                      <div className="grid grid-cols-1 gap-3">
                        {Object.entries(
                          tasks.filter(t => t.status !== 'done').reduce((acc: any, t) => {
                            const p = t.project_name || 'Fără proiect';
                            acc[p] = (acc[p] || 0) + 1;
                            return acc;
                          }, {})
                        ).map(([proj, count]: [string, any]) => (
                          <div key={proj} className="p-4 bg-white/[0.03] border border-white/5 rounded-3xl flex justify-between items-center hover:bg-white/5 transition-colors cursor-pointer" onClick={() => setView('tasks')}>
                            <div className="flex items-center gap-3">
                               <div className="w-1.5 h-6 bg-blue-500 rounded-full" />
                               <p className="font-bold text-sm">{proj}</p>
                            </div>
                            <div className="flex items-center gap-2">
                               <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Active:</span>
                               <span className="text-sm font-black text-blue-500">{count}</span>
                            </div>
                          </div>
                        ))}
                        {tasks.filter(t => t.status !== 'done').length === 0 && (
                          <div className="py-12 text-center space-y-4 bg-white/[0.02] rounded-[32px] border border-dashed border-white/10">
                             <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto opacity-50" />
                             <p className="text-xs text-gray-500 font-bold uppercase tracking-widest">Toate sistemele sunt nominale.</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </section>
              </div>

              {/* Right Column: Schedule & Context */}
              <div className="lg:col-span-3 space-y-8">
                <section className="space-y-4">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2">Program Azi</h3>
                  <div className="space-y-3">
                    {calendarToday?.schedule?.map((s: any) => (
                      <div key={s.id} className="flex gap-4 items-center bg-white/[0.03] border border-white/5 p-4 rounded-3xl hover:bg-white/10 transition-colors">
                        <div className="w-10 text-center">
                           <p className="text-[10px] font-black text-blue-500">{s.start_time.slice(0, 5)}</p>
                        </div>
                        <div className="flex-1">
                          <p className="font-black text-xs">{s.subject_name}</p>
                          <p className="text-[9px] text-gray-500 font-bold uppercase">{s.room}</p>
                        </div>
                      </div>
                    ))}
                    {(!calendarToday?.schedule || calendarToday.schedule.length === 0) && (
                       <p className="text-center text-xs text-gray-600 font-bold py-10 bg-white/[0.02] rounded-3xl">Weekend Mode / Relax. ☕</p>
                    )}
                  </div>
                </section>

                {/* Secondary View Links (Desktop only) */}
                <div className="hidden lg:grid grid-cols-1 gap-4">
                  <GlassCard className="p-4 flex gap-3 items-center border-emerald-500/20" onClick={() => setView('finance')}>
                    <Wallet className="w-5 h-5 text-emerald-500" />
                    <div>
                      <p className="text-[9px] font-black uppercase text-gray-500">Finance</p>
                      <p className="text-xs font-black">{finance?.balance || 0} Lei</p>
                    </div>
                  </GlassCard>
                  <GlassCard className="p-4 flex gap-3 items-center border-pink-500/20" onClick={() => setView('health')}>
                    <Heart className="w-5 h-5 text-pink-500" />
                    <div>
                      <p className="text-[9px] font-black uppercase text-gray-500">Health</p>
                      <p className="text-xs font-black">{healthLogs[0]?.sleep_hours || 8}h Somn</p>
                    </div>
                  </GlassCard>
                </div>
              </div>

            </div>
          </motion.div>
        )}

        {/* --- Specific Module Views --- */}
        {view === 'uni' && (
          <ViewContainer title="Academic" onBack={() => setView('home')}>
            <div className="space-y-6 pb-20">
              <GlassCard className="bg-gradient-to-br from-orange-500/10 to-transparent">
                <div className="flex justify-between items-center">
                  <p className="text-4xl font-black tracking-tighter">{uniSummary?.average_grade || '—'}</p>
                  <TrendingUp className="text-orange-500 w-8 h-8" />
                </div>
                <p className="text-[10px] font-black uppercase text-gray-500 mt-2 tracking-widest">Media Generală</p>
              </GlassCard>
              <div className="space-y-4">
                {uniSummary?.subjects?.map((s: any) => {
                   const attPct = s.total_logged > 0 ? Math.round((s.attended_count / s.total_logged) * 100) : 0;
                   const isLowAtt = s.total_logged > 0 && attPct < (s.min_attendance_pct || 70);
                   return (
                     <div key={s.id} className="bg-white/[0.03] border border-white/5 rounded-3xl p-5 space-y-4">
                        <div className="flex justify-between">
                          <p className="font-black text-lg tracking-tight">{s.name}</p>
                          <div className="flex items-center gap-2">
                             {isLowAtt && <AlertTriangle className="w-4 h-4 text-red-500" />}
                             <p className="text-xl font-black text-emerald-500">{s.avg_grade || '—'}</p>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                           <div className={`p-3 rounded-2xl ${isLowAtt ? 'bg-red-500/10 border border-red-500/20' : 'bg-white/5'}`}>
                              <p className="text-[8px] font-black text-gray-500 uppercase">Prezență</p>
                              <p className={`text-lg font-black ${isLowAtt ? 'text-red-500' : 'text-white'}`}>{attPct}%</p>
                           </div>
                           <div className="p-3 bg-white/5 rounded-2xl">
                              <p className="text-[8px] font-black text-gray-500 uppercase">Note</p>
                              <div className="flex flex-wrap gap-1 mt-1">
                                 {s.grades?.map((g: any, i: number) => <span key={i} className="px-1.5 py-0.5 bg-white/10 rounded text-[9px] font-black">{g.grade}</span>)}
                              </div>
                           </div>
                        </div>
                     </div>
                   );
                })}
              </div>
            </div>
          </ViewContainer>
        )}

        {view === 'shop' && (
          <ViewContainer title="Cumpărături" onBack={() => setView('home')}>
             <div className="flex justify-between items-center mb-6 px-2">
                <p className="text-[10px] font-black uppercase tracking-widest text-gray-500">{shopping.filter(i => !i.is_bought).length} Produse Rămase</p>
                <button onClick={() => fetch('/api/shopping/clear', { method: 'DELETE', headers: HEADERS }).then(fetchData)} className="text-[10px] font-black uppercase tracking-widest text-red-500 bg-red-500/10 px-3 py-1.5 rounded-lg active:scale-95 transition-transform">Curăță</button>
             </div>
             <div className="space-y-3">
                {shopping.map(i => (
                  <GlassCard key={i.id} className="flex items-center justify-between py-4" onClick={() => fetch(`/api/shopping/${i.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ is_bought: !i.is_bought }) }).then(fetchData)}>
                     <div className="flex items-center gap-4">
                        <div className={`w-6 h-6 rounded-lg border-2 ${i.is_bought ? 'bg-emerald-500 border-emerald-500' : 'border-white/10'} flex items-center justify-center`}>
                           {i.is_bought && <CheckCircle2 className="w-4 h-4 text-black" />}
                        </div>
                        <p className={`font-bold ${i.is_bought ? 'line-through text-gray-600' : ''}`}>{i.item}</p>
                     </div>
                     <span className="text-[8px] font-black uppercase text-gray-600 px-2 py-1 bg-white/5 rounded-md">{i.category}</span>
                  </GlassCard>
                ))}
             </div>
          </ViewContainer>
        )}

        {view === 'notes' && (
          <ViewContainer title="Creier / Note" onBack={() => setView('home')}>
             <div className="space-y-4">
                {notes.map(n => (
                  <GlassCard key={n.id} className="space-y-3">
                     <div className="flex justify-between items-start">
                        <Pin className={`w-4 h-4 ${n.is_pinned ? 'text-blue-500' : 'text-gray-700'}`} />
                        <span className="text-[8px] font-black uppercase text-gray-500">{new Date(n.created_at).toLocaleDateString()}</span>
                     </div>
                     <p className="text-sm font-medium leading-relaxed">{n.content}</p>
                     <div className="flex gap-2">
                        {n.tags?.map((t: string) => <span key={t} className="text-[8px] font-black text-blue-500 bg-blue-500/10 px-2 py-1 rounded-md">#{t}</span>)}
                     </div>
                  </GlassCard>
                ))}
             </div>
          </ViewContainer>
        )}

        {view === 'memory' && (
          <ViewContainer title="Memorie Core" onBack={() => setView('home')}>
             <div className="space-y-6 pb-20">
                <GlassCard className="bg-gradient-to-br from-emerald-500/10 to-transparent">
                   <div className="flex justify-between items-center">
                      <p className="text-3xl font-black tracking-tighter">{memories.length}</p>
                      <Brain className="text-emerald-500 w-8 h-8" />
                   </div>
                   <p className="text-[10px] font-black uppercase text-gray-500 mt-2 tracking-widest">Fapte Memorate</p>
                </GlassCard>
                
                <div className="space-y-4">
                   {['personal', 'preference', 'pattern', 'achievement', 'relationship', 'goal'].map(cat => {
                      const catMems = memories.filter(m => m.category === cat);
                      if (catMems.length === 0) return null;
                      return (
                        <section key={cat} className="space-y-3">
                           <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2">{cat}</h4>
                           <div className="space-y-2">
                              {catMems.map(m => (
                                <div key={m.id} className="p-4 bg-white/[0.03] border border-white/5 rounded-2xl">
                                   <p className="text-sm font-medium leading-relaxed">{m.fact}</p>
                                   <div className="flex justify-between items-center mt-2">
                                      <span className="text-[7px] font-black uppercase text-gray-600">{new Date(m.created_at).toLocaleDateString()}</span>
                                      <span className="text-[7px] font-black uppercase text-emerald-500/50">Confidență: {Math.round(m.confidence * 100)}%</span>
                                   </div>
                                </div>
                              ))}
                           </div>
                        </section>
                      );
                   })}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'health' && (
          <ViewContainer title="Sănătate" onBack={() => setView('home')}>
             <div className="grid grid-cols-3 gap-4 mb-8">
                <GlassCard className="p-4 text-center space-y-1">
                   <Moon className="mx-auto w-4 h-4 text-indigo-500" />
                   <p className="text-lg font-black">{healthLogs[0]?.sleep_hours || '—'}</p>
                   <p className="text-[7px] font-black uppercase text-gray-500">Sleep</p>
                </GlassCard>
                <GlassCard className="p-4 text-center space-y-1">
                   <Droplets className="mx-auto w-4 h-4 text-blue-500" />
                   <p className="text-lg font-black">{healthLogs[0]?.water_ml || 0}</p>
                   <p className="text-[7px] font-black uppercase text-gray-500">Water</p>
                </GlassCard>
                <GlassCard className="p-4 text-center space-y-1">
                   <Scale className="mx-auto w-4 h-4 text-emerald-500" />
                   <p className="text-lg font-black">{healthLogs[0]?.weight_kg || '—'}</p>
                   <p className="text-[7px] font-black uppercase text-gray-500">Weight</p>
                </GlassCard>
             </div>
             <div className="space-y-4">
                {healthLogs.map(l => (
                   <div key={l.id} className="p-4 bg-white/5 rounded-2xl flex justify-between items-center">
                      <div>
                        <p className="font-bold text-sm">{new Date(l.log_date).toLocaleDateString('ro-RO', { weekday: 'long' })}</p>
                        <p className="text-[9px] text-gray-500 uppercase tracking-widest">Calitate somn: {l.sleep_quality || '—'}</p>
                      </div>
                      <div className={`px-2 py-1 rounded-lg text-[9px] font-black uppercase ${l.nutrition === 'great' ? 'bg-emerald-500/20 text-emerald-500' : 'bg-orange-500/10 text-orange-400'}`}>{l.nutrition}</div>
                   </div>
                ))}
             </div>
          </ViewContainer>
        )}

        {view === 'calendar' && (
          <ViewContainer title="Planificare" onBack={() => setView('home')}>
             <div className="space-y-6">
                <div className="space-y-3">
                   {calendarToday?.events?.map((e: any) => (
                      <div key={e.id} className="p-5 bg-blue-600/10 border border-blue-500/20 rounded-[28px] space-y-2">
                         <div className="flex justify-between items-center">
                            <p className="font-black text-blue-500 text-lg">{e.title}</p>
                            <span className="text-xs font-black text-blue-400">{e.event_time?.slice(0, 5) || 'Toată ziua'}</span>
                         </div>
                         <p className="text-xs text-gray-400 font-medium">{e.description}</p>
                      </div>
                   ))}
                   {(!calendarToday?.events || calendarToday.events.length === 0) && <p className="text-center py-6 text-xs text-gray-700 font-black uppercase tracking-widest">Fără evenimente logate</p>}
                </div>
                <div className="space-y-3">
                   <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2">Orar Academic</h4>
                   {calendarToday?.schedule?.map((s: any) => (
                      <div key={s.id} className="p-4 bg-white/5 rounded-2xl flex justify-between items-center">
                         <div className="flex gap-4 items-center">
                            <div className="w-1.5 h-6 bg-orange-500 rounded-full" />
                            <div>
                               <p className="font-bold text-sm">{s.subject_name}</p>
                               <p className="text-[9px] text-gray-500 font-bold uppercase">{s.class_type} | {s.room}</p>
                            </div>
                         </div>
                         <p className="text-xs font-black">{s.start_time.slice(0, 5)}</p>
                      </div>
                   ))}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'map' && (
            <ViewContainer title="Sistem Localizare" onBack={() => setView('home')}>
               <div className="relative w-full h-[65vh] rounded-[36px] overflow-hidden border border-white/10 bg-white/[0.02]">
                  {profile?.latitude && profile?.longitude ? (
                    <iframe 
                      title="Lora Map"
                      width="100%" 
                      height="100%" 
                      frameBorder="0" 
                      scrolling="no" 
                      marginHeight={0} 
                      marginWidth={0} 
                      src={`https://www.openstreetmap.org/export/embed.html?bbox=${profile.longitude-0.01}%2C${profile.latitude-0.01}%2C${profile.longitude+0.01}%2C${profile.latitude+0.01}&layer=mapnik&marker=${profile.latitude}%2C${profile.longitude}`}
                      style={{ filter: 'invert(90%) hue-rotate(180deg) brightness(0.8) contrast(1.2)' }}
                    />
                  ) : (
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center space-y-4">
                      <div className="w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center">
                        <MapPin className="w-10 h-10 text-blue-500 animate-pulse" />
                      </div>
                      <p className="font-black text-sm uppercase tracking-widest text-gray-400">Locație Ne-sincronizată</p>
                      <p className="text-[10px] text-gray-500 font-bold leading-relaxed">
                        Trimite locația ta Lorei pe Telegram pentru a activa hărțile interactive și vremea locală exactă.
                      </p>
                    </div>
                  )}
               </div>
              <div className="mt-6 grid grid-cols-2 gap-4">
                 <GlassCard className="p-4 flex gap-3 items-center">
                    <Navigation className="w-4 h-4 text-blue-500" />
                    <span className="text-[10px] font-black uppercase">Traseu Casă</span>
                 </GlassCard>
                 <GlassCard className="p-4 flex gap-3 items-center">
                    <Search className="w-4 h-4 text-gray-500" />
                    <span className="text-[10px] font-black uppercase">Caută Locuri</span>
                 </GlassCard>
              </div>
           </ViewContainer>
        )}

        {view === 'gym' && (
          <ViewContainer title="Antrenament" onBack={() => setView('home')}>
            <div className="grid grid-cols-2 gap-4 mb-8">
              <GlassCard className="text-center">
                <Flame className="mx-auto mb-2 text-red-500" />
                <p className="text-xl font-black">{gymStats?.summary?.total_sessions || 0}</p>
                <p className="text-[8px] font-bold uppercase text-gray-500">Sesiuni (30z)</p>
              </GlassCard>
              <GlassCard className="text-center">
                <Star className="mx-auto mb-2 text-yellow-500" />
                <p className="text-xl font-black">{gymStats?.prs?.length || 0}</p>
                <p className="text-[8px] font-bold uppercase text-gray-500">Recorduri</p>
              </GlassCard>
            </div>

            <div className="space-y-8 pb-20">
               {/* PRs Section */}
               <section className="space-y-4">
                  <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2">Personal Records</h4>
                  <div className="flex gap-3 overflow-x-auto no-scrollbar py-2">
                     {gymStats?.prs?.map((pr: any, i: number) => (
                        <div key={i} className="min-w-[120px] p-4 bg-white/[0.03] border border-white/5 rounded-2xl">
                           <p className="text-[8px] font-black text-gray-500 uppercase truncate">{pr.exercise_name}</p>
                           <p className="text-lg font-black text-yellow-500">{pr.max_weight} <span className="text-[10px]">KG</span></p>
                        </div>
                     ))}
                  </div>
               </section>

               {/* Recent Workouts */}
               <section className="space-y-4">
                  <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2">Istoric Recent</h4>
                  <div className="space-y-4">
                     {gymStats?.recent_workouts?.map((w: any) => (
                        <div key={w.id} className="bg-white/[0.03] border border-white/5 rounded-3xl p-5 space-y-4">
                           <div className="flex justify-between items-start">
                              <div className="flex gap-3 items-center">
                                 <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center text-lg">{w.icon || '💪'}</div>
                                 <div>
                                    <p className="font-black text-sm">{w.type}</p>
                                    <p className="text-[10px] text-gray-500 font-bold uppercase">{new Date(w.workout_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })} • {w.duration_min} min</p>
                                 </div>
                              </div>
                           </div>
                           {w.exercises && w.exercises.length > 0 && (
                              <div className="space-y-2 pt-2 border-t border-white/5">
                                 {w.exercises.map((ex: any, idx: number) => (
                                    <div key={idx} className="flex justify-between text-[11px] font-medium">
                                       <span className="text-gray-400">{ex.name}</span>
                                       <span className="font-bold">{ex.sets}x{ex.reps} • {ex.weight_kg}kg</span>
                                    </div>
                                 ))}
                              </div>
                           )}
                           {w.notes && <p className="text-[10px] text-gray-500 italic">"{w.notes}"</p>}
                        </div>
                     ))}
                  </div>
               </section>
            </div>
          </ViewContainer>
        )}

        {view === 'skills' && (
          <ViewContainer title={selectedSkill ? "Log Progres" : "Abilități"} onBack={() => selectedSkill ? setSelectedSkill(null) : setView('home')}>
            <div className="space-y-8 pb-20">
               {selectedSkill ? (
                 <div className="p-2 space-y-6">
                    <GlassCard className="text-center p-8 space-y-4">
                       <p className="text-[10px] font-black uppercase text-gray-500 tracking-widest">Loghează progres pentru</p>
                       <h2 className="text-3xl font-black">{selectedSkill.name}</h2>
                       <div className="flex justify-center items-center gap-2">
                          <input 
                            type="number" 
                            value={logValue} 
                            onChange={(e) => setLogValue(e.target.value)}
                            placeholder="Valoare"
                            className="bg-transparent text-4xl font-black w-32 text-center outline-none border-b-2 border-blue-500/30 focus:border-blue-500 transition-colors"
                            autoFocus
                          />
                          <span className="text-xl font-bold text-gray-500">{selectedSkill.unit}</span>
                       </div>
                    </GlassCard>
                    <button 
                      onClick={async () => {
                        await fetch('/api/skills/log', { method: 'POST', headers: HEADERS, body: JSON.stringify({ skill_id: selectedSkill.id, value: logValue, metric: selectedSkill.unit }) });
                        setSelectedSkill(null);
                        setLogValue('');
                        fetchData();
                      }}
                      className="w-full py-5 bg-blue-600 rounded-3xl font-black uppercase tracking-widest shadow-[0_10px_30px_rgba(37,99,235,0.3)] active:scale-95 transition-transform"
                    >
                      Salvează Progresul
                    </button>
                 </div>
               ) : (
                 <>
               {/* Categorii Dinamice */}
               {Array.from(new Set(skills.map(s => s.category || 'Personal'))).sort().map(cat => {
                 const catSkills = skills.filter(s => (s.category || 'Personal') === cat);
                 if (catSkills.length === 0) return null;
                 return (
                   <section key={cat} className="space-y-4">
                      <h4 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2">{cat}</h4>
                      <div className="space-y-3">
                         {catSkills.map(s => (
                           <GlassCard key={s.id} className="relative group active:scale-[0.98] transition-transform" onClick={() => { setSelectedSkill(s); setLogValue(''); }}>
                              <div className="flex justify-between items-start mb-4">
                                 <div>
                                    <div className="flex items-center gap-2">
                                       <p className="font-black text-lg tracking-tight">{s.name}</p>
                                       {s.streak > 0 && (
                                          <div className="flex items-center gap-1 bg-orange-500/10 text-orange-500 px-2 py-0.5 rounded-full">
                                             <Flame className="w-3 h-3" />
                                             <span className="text-[10px] font-black">{s.streak}z</span>
                                          </div>
                                       )}
                                    </div>
                                    <p className="text-[10px] text-gray-500 font-bold uppercase mt-1">Nivel {s.level || 1} • XP {s.total_exp || 0}</p>
                                 </div>
                                 <div className="text-right">
                                    <p className="text-sm font-black text-blue-500">{s.progress || 0}%</p>
                                 </div>
                              </div>
                              
                              {/* Progress Bar */}
                              <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden mb-4">
                                 <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${s.progress || 0}%` }}
                                    className="h-full bg-gradient-to-r from-blue-600 to-blue-400 shadow-[0_0_10px_rgba(37,99,235,0.3)]"
                                 />
                              </div>

                              <div className="flex justify-between items-center text-[9px] font-black uppercase text-gray-600">
                                 <span>Ultima: {s.last_log_date ? new Date(s.last_log_date).toLocaleDateString('ro-RO') : 'Niciodată'}</span>
                                 {s.last_value && <span>{s.last_value} {s.unit}</span>}
                              </div>
                           </GlassCard>
                         ))}
                      </div>
                   </section>
                 );
               })}
                 </>
               )}
            </div>
          </ViewContainer>
        )}

        {view === 'finance' && (
          <ViewContainer title="Finanțe Lora" onBack={() => setView('home')}>
             <div className="space-y-8 pb-20">
                {/* Balance Hero */}
                <GlassCard className="bg-gradient-to-br from-emerald-500/10 to-transparent p-8 text-center relative overflow-hidden">
                   <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl -mr-16 -mt-16" />
                   <p className="text-[10px] font-black uppercase tracking-[0.4em] text-emerald-500 mb-2">Balanță Totală</p>
                   <p className="text-5xl font-black tabular-nums tracking-tighter">{finance?.balance || 0} <span className="text-sm font-bold opacity-50">LEI</span></p>
                </GlassCard>

                {/* Summary Grid */}
                <div className="grid grid-cols-2 gap-4">
                   <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl space-y-1">
                      <p className="text-[8px] font-black text-emerald-500 uppercase tracking-widest">Venituri (30z)</p>
                      <p className="text-xl font-black">+{finance?.total_income || 0}</p>
                   </div>
                   <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl space-y-1">
                      <p className="text-[8px] font-black text-red-500 uppercase tracking-widest">Cheltuieli (30z)</p>
                      <p className="text-xl font-black">-{finance?.total_expenses || 0}</p>
                   </div>
                </div>

                {/* Top Spending Category */}
                {finance?.top_categories?.length > 0 && (
                  <GlassCard className="flex items-center justify-between">
                     <div>
                        <p className="text-[8px] font-black text-gray-500 uppercase tracking-widest mb-1">Top Cheltuieli</p>
                        <p className="text-lg font-black uppercase">{finance.top_categories[0].category}</p>
                     </div>
                     <div className="text-right">
                        <p className="text-lg font-black text-red-500">-{finance.top_categories[0].amount} Lei</p>
                        <div className="w-20 h-1 bg-white/5 rounded-full mt-1 overflow-hidden">
                           <div className="w-full h-full bg-red-500 shadow-[0_0_10px_#ef4444]" />
                        </div>
                     </div>
                  </GlassCard>
                )}

                {/* Transaction History */}
                <section className="space-y-4">
                   <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2">Istoric Tranzacții</h3>
                   <div className="space-y-3">
                      {financeHistory.map((tx: any) => (
                        <div key={tx.id} className="p-4 bg-white/[0.02] border border-white/5 rounded-2xl flex justify-between items-center hover:bg-white/[0.05] transition-colors">
                           <div className="flex gap-4 items-center">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${tx.type === 'income' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                                 {tx.type === 'income' ? <TrendingUp className="w-5 h-5" /> : <Wallet className="w-5 h-5" />}
                              </div>
                              <div>
                                 <p className="font-bold text-sm">{tx.description || tx.category}</p>
                                 <p className="text-[9px] text-gray-500 font-bold uppercase tracking-widest">{tx.category} • {new Date(tx.tx_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</p>
                              </div>
                           </div>
                           <p className={`font-black tabular-nums ${tx.type === 'income' ? 'text-emerald-500' : 'text-white'}`}>
                              {tx.type === 'income' ? '+' : '-'}{tx.amount}
                           </p>
                        </div>
                      ))}
                      {financeHistory.length === 0 && <p className="text-center py-10 text-xs text-gray-600 font-bold italic">Nicio tranzacție logată recent.</p>}
                   </div>
                </section>
             </div>
          </ViewContainer>
        )}

        {view === 'tasks' && (
          <ViewContainer title="Tasks & Proiecte" onBack={() => setView('home')}>
             <div className="space-y-10 pb-24">
                {/* Pending Tasks Grouped by Project */}
                {Object.entries(
                  tasks.filter(t => t.status !== 'done').reduce((acc: any, t) => {
                    const p = t.project_name || 'Fără proiect';
                    if (!acc[p]) acc[p] = [];
                    acc[p].push(t);
                    return acc;
                  }, {})
                ).map(([proj, projTasks]: [string, any]) => (
                  <section key={proj} className="space-y-4">
                     <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2 flex justify-between items-center">
                        <span>{proj}</span>
                        <span className="bg-white/5 px-2 py-0.5 rounded text-[8px] opacity-50">{projTasks.length}</span>
                     </h3>
                     <div className="space-y-3">
                        {projTasks.map((t: any) => (
                          <GlassCard key={t.id} className={`p-4 flex items-center gap-4 ${t.priority === 'high' ? 'border-l-2 border-red-500' : ''}`} onClick={() => fetch(`/api/tasks/${t.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ action: 'complete' }) }).then(fetchData)}>
                            <div className={`w-6 h-6 rounded-lg border-2 ${t.priority === 'high' ? 'border-red-500/30' : 'border-white/10'} flex items-center justify-center`}>
                               <div className={`w-2.5 h-2.5 rounded-full ${t.priority === 'high' ? 'bg-red-500' : 'bg-gray-700'}`} />
                            </div>
                            <div className="flex-1">
                               <p className="font-bold text-sm leading-tight">{t.title}</p>
                            </div>
                            {t.due_date && <span className="text-[9px] font-black text-gray-600">{new Date(t.due_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</span>}
                          </GlassCard>
                        ))}
                     </div>
                  </section>
                ))}

                {tasks.filter(t => t.status !== 'done').length === 0 && (
                  <div className="py-20 text-center space-y-4">
                     <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto">
                        <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                     </div>
                     <p className="text-xs text-gray-600 font-bold italic">Toate task-urile sunt rezolvate. ✨</p>
                  </div>
                )}

                <section className="space-y-4">
                   <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-500 px-2 opacity-50">Finalizate recent</h3>
                   <div className="space-y-2 opacity-50">
                      {tasks.filter(t => t.status === 'done').slice(0, 10).map(t => (
                        <div key={t.id} className="p-4 bg-white/[0.02] border border-white/5 rounded-2xl flex items-center gap-4">
                           <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                           <p className="text-sm font-medium line-through text-gray-600">{t.title}</p>
                        </div>
                      ))}
                   </div>
                </section>
             </div>
             
             {/* Float Add Button */}
             <button onClick={() => setIsAddingTask(true)} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-blue-600 shadow-[0_10px_30px_rgba(37,99,235,0.4)] flex items-center justify-center active:scale-95 transition-transform z-[110]">
                <Plus className="w-8 h-8" />
             </button>
          </ViewContainer>
        )}

        {view === 'projects' && (
          <ViewContainer title="Gestiune Proiecte" onBack={() => setView('home')}>
             <div className="space-y-8 pb-24">
                {projects.map((p: any) => {
                  const total = (p.pending_tasks || 0) + (p.completed_tasks || 0);
                  const progress = total > 0 ? Math.round((p.completed_tasks / total) * 100) : 0;
                  
                  return (
                    <GlassCard key={p.id} className="p-6 relative overflow-hidden group">
                       <div className="flex justify-between items-start mb-4">
                          <div className="space-y-1">
                             <div className="flex items-center gap-2">
                                <h3 className="text-xl font-black">{p.name}</h3>
                                {p.priority === 'high' && <Zap className="w-4 h-4 text-orange-500 fill-orange-500" />}
                             </div>
                             <p className="text-xs text-gray-500 font-medium line-clamp-2">{p.description || 'Nicio descriere adăugată.'}</p>
                          </div>
                          <span className={`px-2 py-1 rounded text-[8px] font-black uppercase tracking-widest ${
                            p.priority === 'high' ? 'bg-red-500/20 text-red-500' : 
                            p.priority === 'medium' ? 'bg-blue-500/20 text-blue-500' : 'bg-gray-500/20 text-gray-500'
                          }`}>
                             {p.priority}
                          </span>
                       </div>

                       <div className="space-y-2">
                          <div className="flex justify-between items-end">
                             <span className="text-[10px] font-bold text-gray-400">Progres: {progress}%</span>
                             <span className="text-[10px] font-bold text-gray-500">{p.completed_tasks}/{total} Tasks</span>
                          </div>
                          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                             <motion.div 
                               initial={{ width: 0 }}
                               animate={{ width: `${progress}%` }}
                               transition={{ duration: 1, ease: "easeOut" }}
                               className={`h-full rounded-full ${
                                 progress === 100 ? 'bg-emerald-500' : 
                                 p.overdue_tasks > 0 ? 'bg-red-500' : 'bg-blue-600'
                               }`}
                             />
                          </div>
                       </div>

                       <div className="mt-4 flex gap-4 border-t border-white/5 pt-4">
                          <div className="flex items-center gap-2">
                             <Target className="w-3 h-3 text-gray-500" />
                             <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                                {p.pending_tasks} Pending
                             </span>
                          </div>
                          {p.overdue_tasks > 0 && (
                            <div className="flex items-center gap-2">
                               <AlertTriangle className="w-3 h-3 text-red-500" />
                               <span className="text-[10px] font-black text-red-500 uppercase tracking-widest">
                                  {p.overdue_tasks} Overdue
                               </span>
                            </div>
                          )}
                       </div>
                    </GlassCard>
                  );
                })}
                
                {projects.length === 0 && (
                  <div className="py-20 text-center text-xs text-gray-600 font-bold italic">
                    Niciun proiect activ în curs. 📁
                  </div>
                )}
             </div>
          </ViewContainer>
        )}

      {/* Diagnostics */}
      {errorMessage && (
        <div className="fixed top-0 left-0 right-0 z-[2000] bg-red-600/90 text-white p-2 text-[8px] font-mono backdrop-blur-sm">
          ERR: {errorMessage} | API: {BASE_URL}
        </div>
      )}
      
      </AnimatePresence>

      {/* Add Task Modal */}
      <AnimatePresence>
        {isAddingTask && (
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setIsAddingTask(false)} />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }} className="relative w-full max-w-sm bg-[#0a0a0a] border border-white/10 rounded-[32px] p-8 space-y-6">
               <h2 className="text-xl font-black uppercase tracking-widest">Flux Nou</h2>
               <input autoFocus value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAddTask()} placeholder="Ce inițiem?" className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 font-bold text-lg outline-none focus:border-blue-500/50 placeholder:text-gray-700" />
               <div className="flex gap-4">
                  <button onClick={() => setIsAddingTask(false)} className="flex-1 py-4 bg-white/5 rounded-2xl font-black text-xs uppercase tracking-widest text-gray-500">Renunță</button>
                  <button onClick={handleAddTask} className="flex-1 py-4 bg-blue-600 rounded-2xl font-black text-xs uppercase tracking-widest shadow-[0_0_20px_rgba(37,99,235,0.4)]">Salvează</button>
               </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;900&display=swap');
        body { font-family: 'Outfit', sans-serif; background: #000; color: #fff; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  );
}

export default App;
