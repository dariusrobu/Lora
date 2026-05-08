import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, Navigation, Plus, GraduationCap, 
  Dumbbell, Wallet, ArrowLeft, Loader2, Settings,
  Calendar, ShoppingCart, Heart, Flame, Brain, Play, Pause, RotateCcw,
  TrendingUp, Star, Moon, Droplets, Scale,
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
    whileHover={onClick ? { scale: 1.01, backgroundColor: 'rgba(255, 255, 255, 0.05)' } : {}}
    whileTap={onClick ? { scale: 0.99 } : {}}
    onClick={onClick}
    className={`liquid-panel rounded-2xl p-6 ${className} ${onClick ? 'cursor-pointer' : ''}`}
  >
    {children}
  </motion.div>
);

const ViewContainer = ({ children, title, onBack }: any) => (
  <motion.div 
    initial={{ opacity: 0, scale: 0.98 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 1.02 }}
    className="fixed inset-0 bg-[#050505] z-[100] p-8 lg:p-16 overflow-y-auto no-scrollbar"
  >
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-12">
        <button onClick={onBack} className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-colors">
          <ArrowLeft className="w-5 h-5 text-[#adc6ff]" />
        </button>
        <h2 className="label-ethereal">{title}</h2>
        <div className="w-12" />
      </div>
      {children}
    </div>
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
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [timerActive, setTimerActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const timerRef = useRef<any>(null);

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    console.log("🚀 Safe Mode Boot: Lora Hub");
    fetchData();
    const safety = setTimeout(() => setLoading(false), 10000);
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
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#050505] p-8 text-center space-y-12">
        <motion.div
           animate={{ 
             scale: [0.9, 1.1, 0.9], 
             opacity: [0.3, 0.7, 0.3],
             boxShadow: ["0 0 0px rgba(59,130,246,0)", "0 0 40px rgba(59,130,246,0.2)", "0 0 0px rgba(59,130,246,0)"]
           }}
           transition={{ duration: 3, repeat: Infinity }}
           className="w-20 h-20 liquid-panel rounded-full flex items-center justify-center"
        >
           <Loader2 className="w-8 h-8 text-[#adc6ff] animate-spin" />
        </motion.div>
        
        {errorMessage && (
          <div className="space-y-6">
            <p className="label-ethereal text-red-400">
              Sincronizare Eșuată • {errorMessage}
            </p>
            <button 
              onClick={() => { setLoading(true); fetchData(); }}
              className="primary-button"
            >
              Reîncearcă
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen text-white font-sans overflow-x-hidden selection:bg-[#3b82f6]/30">
      
      <AnimatePresence mode="wait">
        {view === 'home' && (
          <motion.div 
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="p-8 lg:p-16 pb-32 space-y-12 max-w-7xl mx-auto"
          >
            <header className="flex justify-between items-start">
              <div className="space-y-2">
                <h1 className="text-5xl font-light tracking-[-0.05em] text-[#adc6ff]">LORA<span className="text-white/30">.</span></h1>
                <p className="label-ethereal">{tasks.filter(t => t.status !== 'done').length} Task-uri Active</p>
              </div>
              <div className="flex gap-4">
                <button className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-colors"><Search className="w-5 h-5 text-gray-500" /></button>
                <button className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-colors"><Settings className="w-5 h-5 text-gray-400" /></button>
              </div>
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

                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2 flex justify-between items-center">
                    <span>Project Pulse</span>
                    <span className="bg-blue-500/10 text-[#adc6ff] px-2 py-0.5 rounded text-[8px] uppercase tracking-widest">{tasks.filter(t => t.status !== 'done').length} Total</span>
                  </h3>
                  
                  <div className="space-y-4">
                    {tasks.filter(t => t.status !== 'done').length > 0 ? (
                      Object.entries(
                        tasks.filter(t => t.status !== 'done').reduce((acc: any, t) => {
                          const p = t.project_name || 'Altele';
                          acc[p] = (acc[p] || 0) + 1;
                          return acc;
                        }, {})
                      ).map(([proj, count]: [string, any]) => (
                        <div key={proj} className="liquid-panel p-5 flex justify-between items-center hover:bg-white/5 transition-all group cursor-pointer" onClick={() => setView('tasks')}>
                          <div className="flex items-center gap-4">
                             <div className="w-1 h-6 bg-[#3b82f6] rounded-full group-hover:scale-y-125 transition-transform" />
                             <p className="font-light text-lg tracking-tight">{proj}</p>
                          </div>
                          <div className="flex items-center gap-3">
                             <span className="label-ethereal text-[8px] opacity-40">Active</span>
                             <span className="text-xl font-thin text-[#adc6ff]">{count}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="py-20 text-center space-y-6 liquid-panel border-dashed border-white/5">
                         <CheckCircle2 className="w-10 h-10 text-emerald-500/30 mx-auto" />
                         <p className="label-ethereal text-[9px]">Sistem Nominal • Toate sarcinile completate</p>
                      </div>
                    )}
                  </div>
                </section>
              </div>

              {/* Right Column: Schedule & Vitals */}
              <div className="lg:col-span-3 space-y-12">
                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2">Program Azi</h3>
                  <div className="space-y-4">
                    {calendarToday?.schedule?.map((s: any) => (
                      <div key={s.id} className="liquid-panel p-5 flex gap-6 items-center hover:bg-white/5 transition-all">
                        <div className="w-14 text-center space-y-1">
                           <p className="text-xs font-light text-[#adc6ff]">{s.start_time.slice(0, 5)}</p>
                           <div className="w-4 h-[1px] bg-white/10 mx-auto" />
                        </div>
                        <div className="flex-1 space-y-1">
                          <p className="font-medium text-sm tracking-tight">{s.subject_name}</p>
                          <p className="label-ethereal text-[8px] opacity-50">{s.room}</p>
                        </div>
                        <Navigation className="w-4 h-4 text-gray-700" />
                      </div>
                    ))}
                    {(!calendarToday?.schedule || calendarToday.schedule.length === 0) && (
                       <div className="py-12 text-center liquid-panel border-dashed border-white/5">
                          <p className="label-ethereal text-[8px]">Program Liber • Weekend Mode</p>
                       </div>
                    )}
                  </div>
                </section>

                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2">Vitals</h3>
                  <div className="space-y-4">
                    <GlassCard className="flex gap-5 items-center group" onClick={() => setView('health')}>
                      <div className="w-12 h-12 rounded-xl bg-pink-500/10 flex items-center justify-center">
                        <Heart className="w-5 h-5 text-pink-500" />
                      </div>
                      <div className="flex-1">
                        <p className="label-ethereal text-[8px]">Health Score</p>
                        <p className="text-lg font-light">{healthLogs[0]?.sleep_hours || '8'}h Somn</p>
                      </div>
                      <button className="text-[8px] label-ethereal p-2 liquid-panel hover:bg-blue-500/10">vConsole</button>
                    </GlassCard>
                    
                    <GlassCard className="flex gap-5 items-center group" onClick={() => setView('gym')}>
                      <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
                        <Dumbbell className="w-5 h-5 text-red-500" />
                      </div>
                      <div className="flex-1">
                        <p className="label-ethereal text-[8px]">Antrenament</p>
                        <p className="text-lg font-light">{gymStats?.summary?.total_sessions || 0} Sesiuni</p>
                      </div>
                    </GlassCard>
                  </div>
                </section>
              </div>
            </div>
          </motion.div>
        )}

        {/* --- Specific Module Views --- */}
        {view === 'uni' && (
          <ViewContainer title="Academic" onBack={() => setView('home')}>
            <div className="space-y-12 pb-32">
              <GlassCard className="bg-gradient-to-br from-[#ffb786]/10 to-transparent p-10">
                <div className="flex justify-between items-center">
                  <p className="text-6xl font-thin tracking-tighter text-[#ffb786]">{uniSummary?.average_grade || '—'}</p>
                  <TrendingUp className="text-[#ffb786] w-10 h-10 opacity-50" />
                </div>
                <p className="label-ethereal mt-4">Media Generală • Sesiune Curentă</p>
              </GlassCard>
              
              <div className="space-y-6">
                <h3 className="label-ethereal ml-2">Discipline Active</h3>
                {uniSummary?.subjects?.map((s: any) => {
                   const attPct = s.total_logged > 0 ? Math.round((s.attended_count / s.total_logged) * 100) : 0;
                   const isLowAtt = s.total_logged > 0 && attPct < (s.min_attendance_pct || 70);
                   return (
                     <div key={s.id} className="liquid-panel p-8 space-y-8 hover:bg-white/5 transition-all">
                        <div className="flex justify-between items-start">
                          <div className="space-y-1">
                            <p className="font-light text-2xl tracking-tight">{s.name}</p>
                            <p className="label-ethereal text-[8px] opacity-40">{s.class_type || 'Curs / Seminar'}</p>
                          </div>
                          <div className="text-right">
                             <p className="text-3xl font-thin text-[#adc6ff]">{s.avg_grade || '—'}</p>
                             <p className="label-ethereal text-[8px] opacity-40">Media</p>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                           <div className="space-y-3">
                              <p className="label-ethereal text-[8px]">Prezență</p>
                              <div className="flex items-end gap-3">
                                 <p className={`text-2xl font-light ${isLowAtt ? 'text-red-400' : 'text-white'}`}>{attPct}%</p>
                                 <div className="h-1.5 flex-1 bg-white/5 rounded-full overflow-hidden mb-2">
                                    <div className={`h-full ${isLowAtt ? 'bg-red-400' : 'bg-[#4cd7f6]'} opacity-50`} style={{ width: `${attPct}%` }} />
                                 </div>
                              </div>
                           </div>
                           <div className="space-y-3">
                              <p className="label-ethereal text-[8px]">Note</p>
                              <div className="flex flex-wrap gap-2">
                                 {s.grades?.map((g: any, i: number) => (
                                   <span key={i} className="w-8 h-8 flex items-center justify-center liquid-panel text-xs font-light text-[#adc6ff]">{g.grade}</span>
                                 ))}
                                 {(!s.grades || s.grades.length === 0) && <span className="text-[10px] text-gray-700 italic">Nicio notă logată</span>}
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
             <div className="space-y-12 pb-32">
               <div className="flex justify-between items-center px-2">
                  <div className="space-y-1">
                    <p className="text-4xl font-thin tracking-tight">{shopping.filter(i => !i.is_bought).length}</p>
                    <p className="label-ethereal text-[8px]">Produse de achiziționat</p>
                  </div>
                  <button 
                    onClick={() => fetch('/api/shopping/clear', { method: 'DELETE', headers: HEADERS }).then(fetchData)} 
                    className="label-ethereal text-red-400 hover:text-red-300 transition-colors p-4 liquid-panel"
                  >
                    Arhivează
                  </button>
               </div>

               <div className="space-y-4">
                  {shopping.map(i => (
                    <div 
                      key={i.id} 
                      className={`liquid-panel p-6 flex items-center justify-between transition-all cursor-pointer group ${i.is_bought ? 'opacity-40 grayscale' : 'hover:bg-white/5'}`}
                      onClick={() => fetch(`/api/shopping/${i.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ is_bought: !i.is_bought }) }).then(fetchData)}
                    >
                       <div className="flex items-center gap-6">
                          <div className={`w-6 h-6 rounded-lg border-[0.5px] transition-all flex items-center justify-center ${i.is_bought ? 'bg-[#4cd7f6] border-[#4cd7f6]' : 'border-white/20 group-hover:border-white/40'}`}>
                             {i.is_bought && <CheckCircle2 className="w-4 h-4 text-black" />}
                          </div>
                          <p className={`text-lg font-light tracking-tight ${i.is_bought ? 'line-through' : ''}`}>{i.item}</p>
                       </div>
                       <span className="label-ethereal text-[8px] opacity-40 px-3 py-1 liquid-panel border-none">{i.category}</span>
                    </div>
                  ))}
               </div>
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
            <div className="space-y-12 pb-32">
              <div className="grid grid-cols-2 gap-6">
                <div className="liquid-panel p-8 text-center space-y-3">
                  <Flame className="mx-auto w-6 h-6 text-red-400 opacity-50" />
                  <p className="text-3xl font-thin">{gymStats?.summary?.total_sessions || 0}</p>
                  <p className="label-ethereal text-[8px] opacity-40">Sesiuni Active</p>
                </div>
                <div className="liquid-panel p-8 text-center space-y-3">
                  <Star className="mx-auto w-6 h-6 text-[#ffb786] opacity-50" />
                  <p className="text-3xl font-thin">{gymStats?.prs?.length || 0}</p>
                  <p className="label-ethereal text-[8px] opacity-40">Recorduri</p>
                </div>
              </div>

              <section className="space-y-6">
                <h4 className="label-ethereal ml-2">Personal Records</h4>
                <div className="flex gap-4 overflow-x-auto no-scrollbar py-2">
                   {gymStats?.prs?.map((pr: any, i: number) => (
                      <div key={i} className="min-w-[160px] p-6 liquid-panel space-y-4">
                         <p className="label-ethereal text-[8px] opacity-40 truncate">{pr.exercise_name}</p>
                         <p className="text-2xl font-thin text-[#ffb786]">{pr.max_weight} <span className="text-[10px] opacity-50">KG</span></p>
                      </div>
                   ))}
                </div>
              </section>

              <section className="space-y-6">
                <h4 className="label-ethereal ml-2">Istoric Recent</h4>
                <div className="space-y-6">
                   {gymStats?.recent_workouts?.map((w: any) => (
                      <div key={w.id} className="liquid-panel p-8 space-y-6 hover:bg-white/5 transition-all">
                         <div className="flex justify-between items-start">
                            <div className="flex gap-5 items-center">
                               <div className="w-12 h-12 rounded-2xl liquid-panel border-none flex items-center justify-center text-xl bg-red-400/5">{w.icon || '💪'}</div>
                               <div className="space-y-1">
                                  <p className="font-light text-xl tracking-tight">{w.type}</p>
                                  <p className="label-ethereal text-[8px] opacity-40">{new Date(w.workout_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })} • {w.duration_min} min</p>
                               </div>
                            </div>
                         </div>
                         {w.exercises && w.exercises.length > 0 && (
                            <div className="space-y-3 pt-6 border-t border-white/5">
                               {w.exercises.map((ex: any, idx: number) => (
                                  <div key={idx} className="flex justify-between text-xs font-light">
                                     <span className="text-[#8c909f]">{ex.name}</span>
                                     <span className="text-[#adc6ff]">{ex.sets}x{ex.reps} • {ex.weight_kg}kg</span>
                                  </div>
                               ))}
                            </div>
                         )}
                      </div>
                   ))}
                </div>
              </section>
            </div>
          </ViewContainer>
        )}

        {view === 'skills' && (
          <ViewContainer title={selectedSkill ? "Evoluție" : "Abilități"} onBack={() => selectedSkill ? setSelectedSkill(null) : setView('home')}>
            <div className="space-y-12 pb-32">
               {selectedSkill ? (
                 <div className="space-y-12">
                    <div className="text-center space-y-8 p-12 liquid-panel">
                       <p className="label-ethereal">Loghează progres</p>
                       <h2 className="text-5xl font-thin tracking-tighter text-[#adc6ff]">{selectedSkill.name}</h2>
                       <div className="flex justify-center items-end gap-4">
                          <input 
                            type="number" 
                            value={logValue} 
                            onChange={(e) => setLogValue(e.target.value)}
                            placeholder="0"
                            className="bg-transparent text-6xl font-thin w-40 text-center outline-none border-b-[0.5px] border-[#3b82f6]/20 focus:border-[#3b82f6] transition-all placeholder:opacity-10"
                            autoFocus
                          />
                          <span className="label-ethereal pb-3 opacity-40">{selectedSkill.unit}</span>
                       </div>
                    </div>
                    <button 
                      onClick={async () => {
                        await fetch('/api/skills/log', { method: 'POST', headers: HEADERS, body: JSON.stringify({ skill_id: selectedSkill.id, value: logValue, metric: selectedSkill.unit }) });
                        setSelectedSkill(null); setLogValue(''); fetchData();
                      }}
                      className="w-full py-6 primary-button text-sm uppercase tracking-[0.2em] font-light"
                    >
                      Sincronizează Datele
                    </button>
                 </div>
               ) : (
                 <div className="space-y-12">
                   {Array.from(new Set(skills.map(s => s.category || 'Personal'))).sort().map(cat => {
                     const catSkills = skills.filter(s => (s.category || 'Personal') === cat);
                     if (catSkills.length === 0) return null;
                     return (
                       <section key={cat} className="space-y-6">
                          <h4 className="label-ethereal ml-2">{cat}</h4>
                          <div className="space-y-4">
                             {catSkills.map(s => (
                               <div key={s.id} className="liquid-panel p-8 space-y-6 hover:bg-white/5 transition-all cursor-pointer group" onClick={() => { setSelectedSkill(s); setLogValue(''); }}>
                                  <div className="flex justify-between items-start">
                                     <div className="space-y-2">
                                        <div className="flex items-center gap-4">
                                           <p className="font-light text-2xl tracking-tight group-hover:text-[#adc6ff] transition-colors">{s.name}</p>
                                           {s.streak > 0 && (
                                              <div className="flex items-center gap-2 bg-orange-500/5 text-orange-400 px-3 py-1 rounded-full border-[0.5px] border-orange-500/10">
                                                 <Flame className="w-3 h-3" />
                                                 <span className="label-ethereal text-[8px]">{s.streak}z</span>
                                              </div>
                                           )}
                                        </div>
                                        <p className="label-ethereal text-[8px] opacity-40">Nivel {s.level || 1} • XP {s.total_exp || 0}</p>
                                     </div>
                                     <p className="text-3xl font-thin text-[#4cd7f6]">{s.progress || 0}%</p>
                                  </div>
                                  
                                  <div className="w-full h-[1px] bg-white/5 rounded-full overflow-hidden">
                                     <motion.div 
                                        initial={{ width: 0 }}
                                        animate={{ width: `${s.progress || 0}%` }}
                                        className="h-full bg-[#4cd7f6] opacity-40 shadow-[0_0_20px_rgba(76,215,246,0.3)]"
                                     />
                                  </div>

                                  <div className="flex justify-between items-center">
                                     <span className="label-ethereal text-[8px] opacity-30">Ultima actualizare: {s.last_log_date ? new Date(s.last_log_date).toLocaleDateString('ro-RO') : '—'}</span>
                                     {s.last_value && <span className="label-ethereal text-[8px] text-[#adc6ff]">{s.last_value} {s.unit}</span>}
                                  </div>
                               </div>
                             ))}
                          </div>
                       </section>
                     );
                   })}
                 </div>
               )}
            </div>
          </ViewContainer>
        )}

        {view === 'finance' && (
          <ViewContainer title="Tezaur" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="focus-panel p-12 text-center relative overflow-hidden group">
                   <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[100px] -mr-32 -mt-32" />
                   <p className="label-ethereal mb-4 opacity-50">Lichiditate Totală</p>
                   <p className="text-7xl font-thin tracking-tighter text-white">{finance?.balance || 0} <span className="text-xl font-light opacity-30">LEI</span></p>
                </div>

                <div className="grid grid-cols-2 gap-6">
                   <div className="liquid-panel p-8 space-y-2">
                      <p className="label-ethereal text-[8px] text-emerald-400">Flux Intrare (30z)</p>
                      <p className="text-3xl font-thin text-white">+{finance?.total_income || 0}</p>
                   </div>
                   <div className="liquid-panel p-8 space-y-2">
                      <p className="label-ethereal text-[8px] text-red-400">Flux Ieșire (30z)</p>
                      <p className="text-3xl font-thin text-white">-{finance?.total_expenses || 0}</p>
                   </div>
                </div>

                <section className="space-y-6">
                   <h3 className="label-ethereal ml-2">Arhivă Tranzacții</h3>
                   <div className="space-y-4">
                      {financeHistory.map((tx: any) => (
                        <div key={tx.id} className="liquid-panel p-6 flex justify-between items-center hover:bg-white/5 transition-all group">
                           <div className="flex gap-6 items-center">
                              <div className={`w-12 h-12 rounded-2xl liquid-panel border-none flex items-center justify-center ${tx.type === 'income' ? 'bg-emerald-500/5 text-emerald-400' : 'bg-red-400/5 text-red-400'}`}>
                                 {tx.type === 'income' ? <TrendingUp className="w-5 h-5" /> : <Wallet className="w-5 h-5" />}
                              </div>
                              <div className="space-y-1">
                                 <p className="font-light text-lg tracking-tight group-hover:text-[#adc6ff] transition-colors">{tx.description || tx.category}</p>
                                 <p className="label-ethereal text-[8px] opacity-40">{tx.category} • {new Date(tx.tx_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</p>
                              </div>
                           </div>
                           <p className={`text-xl font-light tabular-nums ${tx.type === 'income' ? 'text-emerald-400' : 'text-white'}`}>
                              {tx.type === 'income' ? '+' : '-'}{tx.amount}
                           </p>
                        </div>
                      ))}
                   </div>
                </section>
             </div>
          </ViewContainer>
        )}

        {view === 'tasks' && (
          <ViewContainer title="Task-uri" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                {Object.entries(
                  tasks.filter(t => t.status !== 'done').reduce((acc: any, t) => {
                    const p = t.project_name || 'Fără proiect';
                    if (!acc[p]) acc[p] = [];
                    acc[p].push(t);
                    return acc;
                  }, {})
                ).map(([proj, projTasks]: [string, any]) => (
                  <section key={proj} className="space-y-6">
                     <h3 className="label-ethereal ml-2 flex justify-between items-center">
                        <span>{proj}</span>
                        <span className="opacity-30">{projTasks.length}</span>
                     </h3>
                     <div className="space-y-4">
                        {projTasks.map((t: any) => (
                          <div 
                            key={t.id} 
                            className={`liquid-panel p-6 flex items-center justify-between group cursor-pointer hover:bg-white/5 transition-all ${t.priority === 'high' ? 'border-l-[2px] border-l-red-400/50' : ''}`}
                            onClick={() => fetch(`/api/tasks/${t.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ action: 'complete' }) }).then(fetchData)}
                          >
                            <div className="flex items-center gap-6">
                               <div className={`w-5 h-5 rounded-md border-[0.5px] transition-all flex items-center justify-center ${t.priority === 'high' ? 'border-red-400/50' : 'border-white/20'}`}>
                                  <div className={`w-2 h-2 rounded-full ${t.priority === 'high' ? 'bg-red-400 shadow-[0_0_10px_#ef4444]' : 'bg-white/20'}`} />
                               </div>
                               <p className="font-light text-lg tracking-tight group-hover:translate-x-1 transition-transform">{t.title}</p>
                            </div>
                            {t.due_date && <span className="label-ethereal text-[8px] opacity-30">{new Date(t.due_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</span>}
                          </div>
                        ))}
                     </div>
                  </section>
                ))}

                {tasks.filter(t => t.status !== 'done').length === 0 && (
                  <div className="py-32 text-center space-y-6">
                     <CheckCircle2 className="w-12 h-12 text-emerald-500/20 mx-auto" />
                     <p className="label-ethereal opacity-40 italic">Flux de lucru optimizat • Nicio sarcină restantă</p>
                  </div>
                )}
             </div>
             
             <button onClick={() => setIsAddingTask(true)} className="fixed bottom-12 right-12 w-16 h-16 rounded-full bg-[#3b82f6]/20 border-[0.5px] border-[#3b82f6]/40 backdrop-blur-xl flex items-center justify-center hover:scale-110 active:scale-95 transition-all z-[110] shadow-[0_0_40px_rgba(59,130,246,0.2)]">
                <Plus className="w-8 h-8 text-[#adc6ff]" />
             </button>
          </ViewContainer>
        )}

        {view === 'projects' && (
          <ViewContainer title="Proiecte" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                {projects.map((p: any) => {
                  const total = (p.pending_tasks || 0) + (p.completed_tasks || 0);
                  const progress = total > 0 ? Math.round((p.completed_tasks / total) * 100) : 0;
                  
                  return (
                    <div key={p.id} className="liquid-panel p-8 space-y-8 group hover:bg-white/5 transition-all">
                       <div className="flex justify-between items-start">
                          <div className="space-y-2">
                             <div className="flex items-center gap-4">
                                <h3 className="text-2xl font-light tracking-tight">{p.name}</h3>
                                {p.priority === 'high' && <Zap className="w-4 h-4 text-orange-400 fill-orange-400/20" />}
                             </div>
                             <p className="text-xs font-light text-[#8c909f] leading-relaxed max-w-lg line-clamp-2">{p.description || 'Nicio descriere definită.'}</p>
                          </div>
                          <span className={`label-ethereal text-[8px] px-3 py-1 liquid-panel border-none ${
                            p.priority === 'high' ? 'bg-red-400/5 text-red-400' : 'bg-[#adc6ff]/5 text-[#adc6ff]'
                          }`}>
                             {p.priority}
                          </span>
                       </div>

                       <div className="space-y-4">
                          <div className="flex justify-between items-end">
                             <span className="label-ethereal text-[9px] opacity-40">Progres: {progress}%</span>
                             <span className="label-ethereal text-[9px] opacity-40">{p.completed_tasks}/{total} Tasks</span>
                          </div>
                          <div className="w-full h-[1px] bg-white/5 rounded-full overflow-hidden">
                             <motion.div 
                               initial={{ width: 0 }}
                               animate={{ width: `${progress}%` }}
                               className={`h-full ${progress === 100 ? 'bg-emerald-500' : p.overdue_tasks > 0 ? 'bg-red-500' : 'bg-[#3b82f6]'} opacity-40`}
                             />
                          </div>
                       </div>
                    </div>
                  );
                })}
             </div>
          </ViewContainer>
        )}

      </AnimatePresence>

      {/* Add Task Modal */}
      <AnimatePresence>
        {isAddingTask && (
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-6">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-[#050505]/90 backdrop-blur-md" onClick={() => setIsAddingTask(false)} />
            <motion.div initial={{ scale: 0.98, opacity: 0, y: 10 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.98, opacity: 0, y: 10 }} className="relative w-full max-w-lg liquid-panel p-12 space-y-10">
               <div className="space-y-2">
                 <h2 className="label-ethereal">Nou Input Sistem</h2>
                 <p className="text-xs font-light text-[#8c909f]">Sincronizare în timp real cu nucleul Lora</p>
               </div>
               
               <input 
                 autoFocus 
                 value={newTaskTitle} 
                 onChange={e => setNewTaskTitle(e.target.value)} 
                 onKeyDown={e => e.key === 'Enter' && handleAddTask()} 
                 placeholder="Ce inițiem acum?" 
                 className="w-full bg-transparent border-b-[0.5px] border-white/10 p-6 font-light text-2xl outline-none focus:border-[#3b82f6] transition-all placeholder:text-[#32353c]" 
               />
               
               <div className="flex gap-6">
                  <button onClick={() => setIsAddingTask(false)} className="flex-1 py-5 liquid-panel border-none hover:bg-white/5 text-[10px] label-ethereal">Anulează</button>
                  <button onClick={handleAddTask} className="flex-1 py-5 primary-button text-[10px] label-ethereal text-white">Execută</button>
               </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <style>{`
        .no-scrollbar::-webkit-scrollbar { display: none; }
        body { selection-background-color: rgba(59, 130, 246, 0.2); }
      `}</style>
    </div>
  );
}

export default App;
