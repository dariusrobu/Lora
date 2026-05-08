import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, Navigation, Plus, GraduationCap, 
  Dumbbell, Wallet, ArrowLeft, Loader2, Settings,
  ShoppingCart, Heart, Flame, Brain, Play, Pause, RotateCcw,
  TrendingUp, Star, Moon, Droplets, Scale,
  Pin, MapPin, Search, Sun, Cloud, CloudRain, CloudDrizzle, CloudSnow, CloudLightning,
  Briefcase, Zap, BookOpen, Apple
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

const DynamicIsland = ({ active, message, icon: Icon }: any) => (
  <AnimatePresence>
    {active && (
      <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[2000] pointer-events-none">
        <motion.div 
          initial={{ width: 120, height: 36, borderRadius: 100, opacity: 0, y: -20 }}
          animate={{ width: 'auto', height: 48, borderRadius: 24, opacity: 1, y: 0 }}
          exit={{ width: 80, height: 20, borderRadius: 100, opacity: 0, y: -20 }}
          className="bg-black/90 backdrop-blur-3xl border border-white/10 flex items-center gap-4 px-6 py-2 shadow-2xl overflow-hidden min-w-[200px]"
        >
          {Icon && <Icon className="w-4 h-4 text-[#adc6ff] animate-pulse" />}
          <span className="text-[10px] font-black uppercase tracking-widest text-white whitespace-nowrap kinetic-text">{message}</span>
        </motion.div>
      </div>
    )}
  </AnimatePresence>
);

const TiltCard = ({ children, className, onClick }: any) => {
  const ref = useRef<HTMLDivElement>(null);
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    ref.current.style.transform = `perspective(1000px) rotateX(${-y * 10}deg) rotateY(${x * 10}deg) scale3d(1.02, 1.02, 1.02)`;
  };
  const handleMouseLeave = () => {
    if (!ref.current) return;
    ref.current.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
  };
  return (
    <div 
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      className={`liquid-panel tilt-card p-8 rounded-[32px] cursor-pointer group relative overflow-hidden ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative z-10">{children}</div>
    </div>
  );
};

type View = 'home' | 'map' | 'uni' | 'gym' | 'skills' | 'shop' | 'notes' | 'health' | 'calendar' | 'finance' | 'tasks' | 'projects' | 'memory' | 'reading' | 'nutrition';

// --- Shared Components ---
const GlassCard = ({ children, className = "", onClick }: any) => (
  <div onClick={onClick} className={`liquid-panel rounded-2xl p-6 ${className} ${onClick ? 'cursor-pointer hover:bg-white/[0.05]' : ''}`}>
    {children}
  </div>
);

const ViewContainer = ({ children, title, onBack }: any) => (
  <motion.div 
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    className="fixed inset-0 bg-[#050505]/95 backdrop-blur-3xl z-[100] p-8 lg:p-16 overflow-y-auto no-scrollbar"
  >
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-12">
        <button onClick={onBack} className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-colors">
          <ArrowLeft className="w-5 h-5 text-[#adc6ff]" />
        </button>
        <h2 className="label-ethereal kinetic-text">{title}</h2>
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
  const [readingList, setReadingList] = useState<any[]>([]);
  const [nutritionLogs, setNutritionLogs] = useState<any[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [logValue, setLogValue] = useState('');
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [timerActive, setTimerActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const timerRef = useRef<any>(null);
  const [notification, setNotification] = useState<{message: string, active: boolean, icon: any}>({ message: '', active: false, icon: null });

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const showNotification = (message: string, icon: any) => {
    setNotification({ message, active: true, icon });
    setTimeout(() => setNotification(prev => ({ ...prev, active: false })), 5000);
  };

  useEffect(() => {
    console.log("🚀 Safe Mode Boot: Lora Hub");
    fetchData();
    const safety = setTimeout(() => setLoading(false), 10000);
    return () => clearTimeout(safety);
  }, []);

  useEffect(() => {
    if (timerActive && timeLeft > 0) {
      timerRef.current = setInterval(() => setTimeLeft(t => t - 1), 1000);
    } else if (timeLeft === 0) {
      setTimerActive(false);
      showNotification('Focus Session Completat', Zap);
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
      const [t, f, u, g, s, shop, n, h, c, f_hist, prof, w, projs, mems, read, nutr] = await Promise.all([
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
        fetchModule('/api/memory', []),
        fetchModule('/api/reading', []),
        fetchModule('/api/nutrition', [])
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
      setReadingList(read);
      setNutritionLogs(nutr);
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
      <div className="aura-container">
        <div className="aura-blob aura-1" />
        <div className="aura-blob aura-2" />
        <div className="aura-blob aura-3" />
      </div>

      <DynamicIsland active={notification.active} message={notification.message} icon={notification.icon} />
      
      <AnimatePresence mode="wait">
        {view === 'home' && (
          <motion.div 
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="p-8 lg:p-16 pb-32 space-y-12 max-w-7xl mx-auto"
          >
            <header className="flex justify-between items-start mb-8 sm:mb-16">
              <div className="space-y-2 sm:space-y-4">
                <h1 className="text-4xl sm:text-6xl font-light tracking-[-0.05em] text-[#adc6ff] kinetic-text">LORA<span className="text-white/30">.</span></h1>
                <p className="label-ethereal flex items-center gap-2 text-[8px] sm:text-[10px]">
                   <div className="w-1 h-1 sm:w-1.5 sm:h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                   Sistem Activ • {tasks.filter(t => t.status !== 'done').length} Priorități
                </p>
              </div>
              <div className="flex gap-2 sm:gap-4">
                <button className="w-10 h-10 sm:w-14 sm:h-14 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-all hover:scale-110 shadow-2xl shadow-blue-500/10"><Search className="w-4 h-4 sm:w-5 sm:h-5 text-gray-500" /></button>
                <button className="w-10 h-10 sm:w-14 sm:h-14 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-all hover:scale-110 shadow-2xl shadow-blue-500/10"><Settings className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400" /></button>
              </div>
            </header>
                     {/* Top Stats Scroll with Sparklines - Scrollable on all, but more compact on mobile */}
            <div className="flex gap-4 sm:gap-6 overflow-x-auto no-scrollbar py-4 -mx-4 px-4">
              <GlassCard className="min-w-[180px] sm:min-w-[220px] p-4 sm:p-6 space-y-4 sm:space-y-6 group overflow-hidden relative" onClick={() => setView('finance')}>
                <div className="absolute inset-0 bg-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex justify-between items-start relative z-10">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                    <Wallet className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
                  </div>
                  <TrendingUp className="w-3 h-3 sm:w-4 h-4 text-emerald-500/30 group-hover:text-emerald-400 transition-colors" />
                </div>
                <div className="relative z-10">
                  <p className="label-ethereal text-[7px] sm:text-[8px]">Balanță Curentă</p>
                  <p className="text-xl sm:text-3xl font-black tracking-tighter tabular-nums">{finance?.balance || 0} <span className="text-[8px] sm:text-[10px] font-bold opacity-30">LEI</span></p>
                </div>
                <svg className="w-full h-6 sm:h-8 relative z-10 opacity-30 group-hover:opacity-100 transition-all duration-700">
                  <path 
                    d={`M0,15 Q15,5 30,12 T60,8 T90,18 T120,10 T150,5 T180,15`} 
                    fill="none" 
                    stroke="#10b981" 
                    strokeWidth="2" 
                    strokeLinecap="round" 
                  />
                </svg>
              </GlassCard>
              
              <GlassCard className="min-w-[180px] sm:min-w-[220px] p-4 sm:p-6 space-y-4 sm:space-y-6 group overflow-hidden relative" onClick={() => setView('health')}>
                <div className="absolute inset-0 bg-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex justify-between items-start relative z-10">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-pink-500/10 flex items-center justify-center">
                    <Heart className="w-4 h-4 sm:w-5 sm:h-5 text-pink-400" />
                  </div>
                  <Droplets className="w-3 h-3 sm:w-4 h-4 text-blue-400/30 group-hover:text-blue-400 transition-colors" />
                </div>
                <div className="relative z-10">
                  <p className="label-ethereal text-[7px] sm:text-[8px]">Vitals Azi</p>
                  <p className="text-xl sm:text-2xl font-black">{healthLogs[0]?.sleep_hours || '—'}h Somn</p>
                  <div className="flex gap-2 mt-1 sm:mt-2">
                    <div className="w-1 h-1 rounded-full bg-blue-500" />
                    <p className="text-[7px] sm:text-[9px] font-black uppercase text-gray-500">{healthLogs[0]?.water_ml || 0}ml apă</p>
                  </div>
                </div>
              </GlassCard>

              <GlassCard className="min-w-[180px] sm:min-w-[220px] p-4 sm:p-6 space-y-4 sm:space-y-6 group overflow-hidden relative" onClick={() => setView('gym')}>
                <div className="absolute inset-0 bg-red-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex justify-between items-start relative z-10">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <Dumbbell className="w-4 h-4 sm:w-5 sm:h-5 text-red-400" />
                  </div>
                  <Flame className="w-3 h-3 sm:w-4 h-4 text-orange-400/30 group-hover:text-orange-400 transition-colors" />
                </div>
                <div className="relative z-10">
                  <p className="label-ethereal text-[7px] sm:text-[8px]">Antrenament</p>
                  <p className="text-xl sm:text-2xl font-black">{gymStats?.summary?.total_sessions || 0} Sesiuni</p>
                  <p className="text-[7px] sm:text-[9px] font-black uppercase text-gray-500 mt-1 sm:mt-2">Level Up: {Math.round((gymStats?.summary?.total_sessions || 0) / 10)}</p>
                </div>
              </GlassCard>
            </div>
            
            {/* Weather Bento - Ultra Refined & Responsive */}
            {weather && weather.main && (
              <section className="mt-4 sm:mt-8 mb-4">
                <TiltCard className="p-6 sm:p-8 border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-all" onClick={() => setView('map')}>
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-8">
                    <div className="space-y-4 sm:space-y-6">
                      <div className="flex items-center gap-3">
                        <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                           <MapPin className="w-3 h-3 sm:w-4 h-4 text-blue-400" />
                        </div>
                        <span className="text-[8px] sm:text-[10px] font-black uppercase tracking-[0.2em] text-[#adc6ff] kinetic-text">{weather.name}</span>
                      </div>
                      <div className="flex items-end gap-4 sm:gap-6">
                        <h3 className="text-5xl sm:text-7xl font-thin tracking-tighter text-white">{Math.round(weather.main?.temp)}°</h3>
                        <div className="pb-1 sm:pb-3 space-y-0.5 sm:space-y-1">
                          <p className="label-ethereal text-white text-xs sm:text-sm">{weather.weather?.[0]?.description}</p>
                          <p className="text-[7px] sm:text-[9px] font-bold text-gray-600 uppercase">H {weather.main?.humidity}% • V {weather.wind?.speed}m/s</p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex justify-center sm:justify-end">
                      <motion.div 
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                        className="p-4 sm:p-6 rounded-[30px] sm:rounded-[40px] bg-white/5 backdrop-blur-3xl border border-white/10 shadow-2xl"
                      >
                        {weather.weather?.[0]?.main === 'Clear' && <Sun className="w-12 h-12 sm:w-20 sm:h-20 text-yellow-500 drop-shadow-[0_0_30px_rgba(234,179,8,0.6)]" />}
                        {weather.weather?.[0]?.main === 'Clouds' && <Cloud className="w-12 h-12 sm:w-20 sm:h-20 text-blue-300 drop-shadow-[0_0_30px_rgba(147,197,253,0.6)]" />}
                        {weather.weather?.[0]?.main === 'Rain' && <CloudRain className="w-12 h-12 sm:w-20 sm:h-20 text-blue-500" />}
                        {weather.weather?.[0]?.main === 'Drizzle' && <CloudDrizzle className="w-12 h-12 sm:w-20 sm:h-20 text-blue-400" />}
                        {weather.weather?.[0]?.main === 'Snow' && <CloudSnow className="w-12 h-12 sm:w-20 sm:h-20 text-white" />}
                        {['Thunderstorm', 'Mist', 'Fog', 'Haze'].includes(weather.weather?.[0]?.main) && <CloudLightning className="w-12 h-12 sm:w-20 sm:h-20 text-purple-400" />}
                      </motion.div>
                    </div>
                  </div>
                </TiltCard>
              </section>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 sm:gap-8 items-start">
              
              {/* Left Column: Systems & Focus OS */}
              <div className="lg:col-span-4 space-y-6 sm:space-y-8">
                <section className="space-y-4">
                  <h3 className="label-ethereal ml-2">Sisteme Nucleu</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-3 sm:gap-4">
                    {[
                      { id: 'tasks', icon: CheckCircle2, label: 'Tasks', color: 'text-emerald-400' },
                      { id: 'projects', icon: Briefcase, label: 'Proiecte', color: 'text-indigo-400' },
                      { id: 'map', icon: MapPin, label: 'Hartă', color: 'text-blue-500' },
                      { id: 'finance', icon: Wallet, label: 'Bani', color: 'text-emerald-500' },
                      { id: 'uni', icon: GraduationCap, label: 'Academic', color: 'text-orange-500' },
                      { id: 'gym', icon: Dumbbell, label: 'Sală', color: 'text-red-500' },
                      { id: 'skills', icon: Flame, label: 'Skills', color: 'text-yellow-500' },
                      { id: 'shop', icon: ShoppingCart, label: 'Shop', color: 'text-purple-500' },
                      { id: 'reading', icon: BookOpen, label: 'Cărți', color: 'text-orange-400' },
                      { id: 'nutrition', icon: Apple, label: 'Nutriție', color: 'text-rose-400' }
                    ].map(m => (
                      <button key={m.id} onClick={() => setView(m.id as View)} className="flex lg:flex-row flex-col items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-white/[0.02] border border-white/5 rounded-2xl hover:bg-white/10 transition-all hover:scale-[1.02] active:scale-[0.98] group">
                        <div className="w-8 h-8 sm:w-10 sm:h-10 lg:w-8 lg:h-8 rounded-xl bg-white/[0.05] flex items-center justify-center group-hover:bg-white/10 transition-colors">
                          <m.icon className={`w-4 h-4 sm:w-5 sm:h-5 lg:w-4 lg:h-4 ${m.color}`} />
                        </div>
                        <span className="text-[7px] sm:text-[8px] lg:text-[10px] font-black uppercase tracking-widest text-gray-500 group-hover:text-white transition-colors text-center">{m.label}</span>
                      </button>
                    ))}
                  </div>
                </section>

                <TiltCard className="h-64 sm:h-72 flex flex-col items-center justify-center border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent relative group">
                  <p className="absolute top-6 left-6 sm:top-8 left-8 label-ethereal text-[7px] sm:text-[8px]">Focus OS</p>
                  
                  <div className="relative w-28 h-28 sm:w-36 sm:h-36 flex items-center justify-center">
                    <svg className="absolute inset-0 w-full h-full -rotate-90">
                      <circle cx="56" cy="56" r="52" className="sm:hidden" fill="none" stroke="rgba(255,255,255,0.02)" strokeWidth="4" />
                      <circle cx="72" cy="72" r="68" className="hidden sm:block" fill="none" stroke="rgba(255,255,255,0.02)" strokeWidth="4" />
                      <motion.circle 
                        cx="72" cy="72" r="68" 
                        fill="none" 
                        stroke="#3b82f6" 
                        strokeWidth="4" 
                        strokeLinecap="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: timeLeft / (25 * 60) }}
                        transition={{ duration: 1 }}
                        style={{ filter: 'drop-shadow(0 0 8px rgba(59,130,246,0.5))' }}
                        className="hidden sm:block"
                      />
                      <motion.circle 
                        cx="56" cy="56" r="52" 
                        fill="none" 
                        stroke="#3b82f6" 
                        strokeWidth="4" 
                        strokeLinecap="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: timeLeft / (25 * 60) }}
                        transition={{ duration: 1 }}
                        style={{ filter: 'drop-shadow(0 0 8px rgba(59,130,246,0.5))' }}
                        className="sm:hidden"
                      />
                    </svg>
                    <p className="text-2xl sm:text-4xl font-black tracking-tighter kinetic-text">{formatTime(timeLeft)}</p>
                  </div>
                  
                  <div className="mt-8 flex justify-center gap-4 relative z-10">
                    <button onClick={(e) => { e.stopPropagation(); setTimerActive(!timerActive); }} className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center hover:bg-blue-500/20 transition-all border border-blue-500/20 group">
                      {timerActive ? <Pause className="w-5 h-5 text-blue-400" /> : <Play className="w-5 h-5 text-blue-400 pl-0.5" />}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setTimeLeft(25 * 60); }} className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-all border border-white/10">
                      <RotateCcw className="w-5 h-5 text-gray-500" />
                    </button>
                  </div>
                </TiltCard>
              </div>

              {/* Middle Column: Project Pulse & Intelligence */}
              <div className="lg:col-span-5 space-y-6 sm:space-y-8">
                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2 flex justify-between items-center">
                    <span>Proiecte Active</span>
                    <div className="flex items-center gap-2">
                       <div className="w-1 h-1 rounded-full bg-blue-400" />
                       <span className="text-[8px] sm:text-[9px] text-gray-500 uppercase tracking-widest">{tasks.filter(t => t.status !== 'done').length} Priorități</span>
                    </div>
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
                        <div key={proj} className="liquid-panel p-4 sm:p-6 flex justify-between items-center hover:bg-white/[0.05] transition-all group cursor-pointer" onClick={() => setView('tasks')}>
                          <div className="flex items-center gap-4 sm:gap-5">
                             <div className="w-1 sm:w-1.5 h-6 sm:h-8 bg-blue-500 rounded-full group-hover:scale-y-125 transition-transform shadow-[0_0_15px_rgba(59,130,246,0.5)]" />
                             <div>
                                <p className="font-medium text-lg sm:text-xl tracking-tight">{proj}</p>
                                <p className="label-ethereal text-[7px] sm:text-[8px] opacity-40 mt-0.5 sm:mt-1">Sincronizat</p>
                             </div>
                          </div>
                          <div className="flex items-center gap-3 sm:gap-4">
                             <span className="text-2xl sm:text-3xl font-thin text-[#adc6ff]">{count}</span>
                             <ArrowLeft className="w-3 h-3 sm:w-4 h-4 text-gray-700 rotate-180 group-hover:translate-x-1 transition-transform" />
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="py-16 sm:py-24 text-center space-y-6 sm:space-y-8 liquid-panel border-dashed border-white/10 rounded-[30px] sm:rounded-[40px]">
                         <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 4 }}>
                            <CheckCircle2 className="w-12 h-12 sm:w-16 sm:h-16 text-emerald-500/20 mx-auto" />
                         </motion.div>
                         <div className="space-y-1 sm:space-y-2">
                           <p className="label-ethereal text-[8px] sm:text-[10px] text-emerald-400">Sistem Nominal</p>
                           <p className="text-[10px] sm:text-xs text-gray-500">Toate fluxurile de lucru sunt completate</p>
                         </div>
                      </div>
                    )}
                  </div>
                </section>
              </div>

              {/* Right Column: Intelligence & Vitals */}
              <div className="lg:col-span-3 space-y-8 sm:space-y-12">
                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2">Program Azi</h3>
                  <div className="space-y-4">
                    {calendarToday?.schedule?.map((s: any) => (
                      <div key={s.id} className="liquid-panel p-4 sm:p-6 flex gap-4 sm:gap-6 items-center hover:bg-white/[0.04] transition-all rounded-[20px] sm:rounded-[24px]">
                        <div className="w-12 sm:w-14 text-center space-y-1 sm:space-y-2">
                           <p className="text-[8px] sm:text-[10px] font-black text-[#adc6ff] tabular-nums">{s.start_time.slice(0, 5)}</p>
                           <div className="w-4 sm:w-6 h-[1px] bg-blue-500/20 mx-auto" />
                        </div>
                        <div className="flex-1 space-y-0.5 sm:space-y-1">
                          <p className="font-bold text-xs sm:text-sm tracking-tight">{s.subject_name}</p>
                          <p className="label-ethereal text-[7px] sm:text-[8px] opacity-40">{s.room}</p>
                        </div>
                        <Navigation className="w-3 h-3 sm:w-4 h-4 text-gray-700 group-hover:text-blue-400 transition-colors" />
                      </div>
                    ))}
                    {(!calendarToday?.schedule || calendarToday.schedule.length === 0) && (
                       <div className="py-12 sm:py-16 text-center liquid-panel border-dashed border-white/5 rounded-[24px] sm:rounded-[32px]">
                          <p className="label-ethereal text-[8px] sm:text-[9px]">Weekend Mode</p>
                          <p className="text-[8px] sm:text-[9px] text-gray-600 font-bold mt-1 sm:mt-2 uppercase tracking-tighter sm:tracking-normal">Niciun eveniment detectat</p>
                       </div>
                    )}
                  </div>
                </section>

                <section className="space-y-6">
                  <h3 className="label-ethereal ml-2">Vitals</h3>
                  <div className="space-y-4">
                    <GlassCard className="flex gap-4 sm:gap-6 items-center group relative overflow-hidden p-4 sm:p-6" onClick={() => setView('health')}>
                      <div className="absolute top-0 right-0 w-16 sm:w-24 h-16 sm:h-24 bg-pink-500/5 rounded-full blur-2xl -mr-8 sm:-mr-12 -mt-8 sm:-mt-12" />
                      <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-pink-500/10 flex items-center justify-center group-hover:bg-pink-500/20 transition-colors">
                        <Heart className="w-5 h-5 sm:w-6 sm:h-6 text-pink-400" />
                      </div>
                      <div className="flex-1">
                        <p className="label-ethereal text-[7px] sm:text-[8px]">Health Score</p>
                        <p className="text-lg sm:text-xl font-bold tracking-tight">{healthLogs[0]?.sleep_hours || '8'}h Somn</p>
                      </div>
                    </GlassCard>
                    
                    <GlassCard className="flex gap-4 sm:gap-6 items-center group relative overflow-hidden p-4 sm:p-6" onClick={() => setView('gym')}>
                      <div className="absolute top-0 right-0 w-16 sm:w-24 h-16 sm:h-24 bg-red-500/5 rounded-full blur-2xl -mr-8 sm:-mr-12 -mt-8 sm:-mt-12" />
                      <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-red-500/10 flex items-center justify-center group-hover:bg-red-500/20 transition-colors">
                        <Dumbbell className="w-5 h-5 sm:w-6 sm:h-6 text-red-400" />
                      </div>
                      <div className="flex-1">
                        <p className="label-ethereal text-[7px] sm:text-[8px]">Antrenament</p>
                        <p className="text-lg sm:text-xl font-bold tracking-tight">{gymStats?.summary?.total_sessions || 0} Sesiuni</p>
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

        {view === 'reading' && (
          <ViewContainer title="Lectură & Knowledge" onBack={() => setView('home')}>
            <div className="space-y-12 pb-32">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {readingList.map((book: any) => (
                  <GlassCard key={book.id} className="space-y-6">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <h4 className="text-xl font-bold tracking-tight">{book.title}</h4>
                        <p className="label-ethereal text-[8px] opacity-40">{book.author}</p>
                      </div>
                      <BookOpen className="w-5 h-5 text-orange-400 opacity-40" />
                    </div>
                    <div className="space-y-2">
                       <div className="flex justify-between text-[9px] label-ethereal opacity-40">
                          <span>Progres</span>
                          <span>{book.progress_pct}%</span>
                       </div>
                       <div className="w-full h-[2px] bg-white/5 rounded-full overflow-hidden">
                          <motion.div initial={{ width: 0 }} animate={{ width: `${book.progress_pct}%` }} className="h-full bg-orange-400 opacity-40" />
                       </div>
                    </div>
                  </GlassCard>
                ))}
                {readingList.length === 0 && (
                  <div className="col-span-full py-24 text-center liquid-panel border-dashed border-white/5">
                    <p className="label-ethereal text-[10px]">Nicio carte în curs de lectură</p>
                  </div>
                )}
              </div>
            </div>
          </ViewContainer>
        )}

        {view === 'nutrition' && (
          <ViewContainer title="Sistem Nutriție" onBack={() => setView('home')}>
            <div className="space-y-12 pb-32">
               <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <GlassCard className="text-center p-8 border-rose-500/10">
                     <p className="text-3xl font-black text-rose-400">{nutritionLogs.reduce((acc, n) => acc + (n.calories || 0), 0)}</p>
                     <p className="label-ethereal text-[8px] mt-2">Kcal Azi</p>
                  </GlassCard>
                  <GlassCard className="text-center p-8">
                     <p className="text-3xl font-black text-blue-400">{nutritionLogs.reduce((acc, n) => acc + (n.protein || 0), 0)}g</p>
                     <p className="label-ethereal text-[8px] mt-2">Proteine</p>
                  </GlassCard>
                  <GlassCard className="text-center p-8">
                     <p className="text-3xl font-black text-emerald-400">{nutritionLogs.reduce((acc, n) => acc + (n.water_ml || 0), 0)}ml</p>
                     <p className="label-ethereal text-[8px] mt-2">Apă</p>
                  </GlassCard>
               </div>

               <div className="space-y-6">
                 <h3 className="label-ethereal ml-2">Jurnal Alimentar</h3>
                 <div className="space-y-4">
                   {nutritionLogs.map((log: any) => (
                     <div key={log.id} className="liquid-panel p-6 flex justify-between items-center hover:bg-white/5 transition-all">
                        <div className="space-y-1">
                          <p className="font-bold text-lg">{log.food_item}</p>
                          <p className="label-ethereal text-[8px] opacity-40 uppercase tracking-widest">{log.meal_type}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-black text-rose-400">{log.calories} kcal</p>
                          <p className="label-ethereal text-[8px] opacity-40">{log.log_time?.slice(11, 16)}</p>
                        </div>
                     </div>
                   ))}
                 </div>
               </div>
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
