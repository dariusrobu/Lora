import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, Navigation, Plus, GraduationCap, 
  Dumbbell, Wallet, ArrowLeft, Loader2,
  Heart, Flame, Brain, Play, Pause, RotateCcw,
  TrendingUp, Star, Moon, Droplets, Scale,
  Pin, MapPin, Search, Sun, Cloud, CloudRain, CloudDrizzle, CloudSnow, CloudLightning,
  Briefcase, Zap, BookOpen, Apple, Calendar, Database, ShoppingBag, Plane,
  Target, Timer, BarChart3, Newspaper, Layout, Bell, Cpu, Smile
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

type View = 'home' | 'map' | 'uni' | 'gym' | 'skills' | 'shop' | 'notes' | 'health' | 'calendar' | 'finance' | 'tasks' | 'projects' | 'memory' | 'reading' | 'nutrition' | 'travel' | 'goals' | 'mood' | 'focus' | 'insights' | 'news' | 'weather' | 'planner' | 'events' | 'system';

// --- Shared Components ---
const GlassCard = ({ children, className = "", onClick }: any) => (
  <div onClick={onClick} className={`liquid-panel rounded-2xl p-6 ${className} ${onClick ? 'cursor-pointer hover:bg-white/[0.05]' : ''}`}>
    {children}
  </div>
);

const ViewContainer = ({ children, title, onBack }: any) => (
  <motion.div 
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 1.05 }}
    className="fixed inset-0 bg-gradient-to-br from-[#050505] via-[#080808] to-[#050505] backdrop-blur-3xl z-[100] p-6 lg:p-16 overflow-y-auto no-scrollbar"
  >
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-8 sm:mb-12">
        <button onClick={onBack} className="w-10 h-10 sm:w-12 sm:h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-all hover:scale-110 active:scale-90">
          <ArrowLeft className="w-5 h-5 text-[#adc6ff]" />
        </button>
        <h2 className="label-ethereal kinetic-text text-xs sm:text-sm">{title}</h2>
        <div className="w-10 sm:w-12" />
      </div>
      {children}
    </div>
  </motion.div>
);

const moduleGroups = [
  // Page 1: Productivity & Core
  [
    { id: 'tasks', icon: CheckCircle2, label: 'Tasks', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { id: 'projects', icon: Briefcase, label: 'Proiecte', color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
    { id: 'calendar', icon: Calendar, label: 'Planificare', color: 'text-sky-400', bg: 'bg-sky-400/10' },
    { id: 'finance', icon: Wallet, label: 'Tezaur', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
    { id: 'uni', icon: GraduationCap, label: 'Academic', color: 'text-amber-400', bg: 'bg-amber-400/10' },
    { id: 'skills', icon: Zap, label: 'Skills', color: 'text-purple-400', bg: 'bg-purple-400/10' },
    { id: 'notes', icon: Brain, label: 'Note', color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { id: 'goals', icon: Target, label: 'Obiective', color: 'text-orange-400', bg: 'bg-orange-400/10' }
  ],
  // Page 2: Health & Lifestyle
  [
    { id: 'health', icon: Heart, label: 'Vitals', color: 'text-pink-400', bg: 'bg-pink-400/10' },
    { id: 'nutrition', icon: Apple, label: 'Nutriție', color: 'text-rose-400', bg: 'bg-rose-400/10' },
    { id: 'gym', icon: Dumbbell, label: 'Workout', color: 'text-red-400', bg: 'bg-red-400/10' },
    { id: 'reading', icon: BookOpen, label: 'Lectură', color: 'text-orange-300', bg: 'bg-orange-300/10' },
    { id: 'shop', icon: ShoppingBag, label: 'Shop', color: 'text-pink-400', bg: 'bg-pink-400/10' },
    { id: 'travel', icon: Plane, label: 'Travel', color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { id: 'mood', icon: Smile, label: 'Stare', color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
    { id: 'focus', icon: Timer, label: 'Focus', color: 'text-cyan-400', bg: 'bg-cyan-400/10' }
  ],
  // Page 3: Intelligence & System
  [
    { id: 'insights', icon: BarChart3, label: 'Insights', color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
    { id: 'memory', icon: Database, label: 'Memorie', color: 'text-purple-500', bg: 'bg-purple-500/10' },
    { id: 'news', icon: Newspaper, label: 'Știri', color: 'text-gray-400', bg: 'bg-gray-400/10' },
    { id: 'weather', icon: Sun, label: 'Meteo', color: 'text-yellow-500', bg: 'bg-yellow-500/10' },
    { id: 'map', icon: MapPin, label: 'Hartă', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { id: 'planner', icon: Layout, label: 'Planner', color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { id: 'events', icon: Bell, label: 'Evenimente', color: 'text-amber-500', bg: 'bg-amber-500/10' },
    { id: 'system', icon: Cpu, label: 'Sistem', color: 'text-slate-400', bg: 'bg-slate-400/10' }
  ]
];

function App() {
  const [view, setView] = useState<View>('home');
  const [modulePage, setModulePage] = useState(0);
  const [taskFilter, setTaskFilter] = useState<'active' | 'done'>('active');
  const [noteSearch, setNoteSearch] = useState('');
  const [selectedTag, setSelectedTag] = useState('toate');
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
  const [goals, setGoals] = useState<any[]>([]);
  const [moodLogs, setMoodLogs] = useState<any[]>([]);
  const [insights, setInsights] = useState<any>(null);
  const [news, setNews] = useState<any[]>([]);
  const [systemStats, setSystemStats] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [readingList, setReadingList] = useState<any[]>([]);
  const [nutritionLogs, setNutritionLogs] = useState<any[]>([]);
  const [travelLists, setTravelLists] = useState<string[]>([]);
  const [travelItems, setTravelItems] = useState<any[]>([]);
  const [selectedTravelList, setSelectedTravelList] = useState<string | null>(null);
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


  const fetchTravelItems = async (listName: string) => {
    const r = await fetch(`${BASE_URL}/api/travel/items?list_name=${listName}`, { headers: HEADERS });
    if (r.ok) {
      const data = await r.json();
      setTravelItems(data);
    }
  };

  const toggleTravelItem = async (itemId: number, isPacked: boolean) => {
    const r = await fetch(`${BASE_URL}/api/travel/items/${itemId}`, {
      method: 'PATCH',
      headers: HEADERS,
      body: JSON.stringify({ is_packed: isPacked })
    });
    if (r.ok && selectedTravelList) {
      fetchTravelItems(selectedTravelList);
    }
  };

  const fetchData = async () => {
    const fetchModule = async (url: string, defaultValue: any = null) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      try {
        const fullUrl = `${url.startsWith('http') ? url : BASE_URL + url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`;
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
      const [t, f, u, g, s, shop, n, h, c, f_hist, prof, w, projs, mems, read, nutr, travel, goalsData, moodData, insightsData, newsData, systemData] = await Promise.all([
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
        fetchModule('/api/nutrition', []),
        fetchModule('/api/travel/lists', []),
        fetchModule('/api/goals', []),
        fetchModule('/api/mood', []),
        fetchModule('/api/insights'),
        fetchModule('/api/news', []),
        fetchModule('/api/system/stats')
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
      setTravelLists(travel);
      setGoals(goalsData || []);
      setMoodLogs(moodData || []);
      setInsights(insightsData);
      setNews(newsData || []);
      setSystemStats(systemData);
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
              <div className="flex gap-2 sm:gap-4" />
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
                <section className="space-y-6">
                  <div className="flex justify-between items-center px-2">
                    <h3 className="label-ethereal">Sisteme Lora</h3>
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map(i => (
                        <div 
                          key={i} 
                          className={`w-1 h-1 rounded-full transition-all duration-500 ${modulePage === i ? 'w-4 bg-blue-500' : 'bg-white/10'}`} 
                        />
                      ))}
                    </div>
                  </div>

                  <div className="relative overflow-hidden min-h-[480px]">
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={modulePage}
                        initial={{ opacity: 0, x: 50 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -50 }}
                        drag="x"
                        dragConstraints={{ left: 0, right: 0 }}
                        onDragEnd={(_, info) => {
                          if (info.offset.x < -50 && modulePage < 2) setModulePage(p => p + 1);
                          if (info.offset.x > 50 && modulePage > 0) setModulePage(p => p - 1);
                        }}
                        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-3 cursor-grab active:cursor-grabbing"
                      >
                        {moduleGroups[modulePage].map(m => (
                          <button 
                            key={m.id} 
                            onClick={() => setView(m.id as any)} 
                            className="liquid-panel flex items-center gap-4 p-3 hover:bg-white/[0.05] transition-all group hover:translate-x-1 active:scale-[0.98]"
                          >
                            <div className={`w-10 h-10 rounded-xl ${m.bg} flex items-center justify-center transition-all group-hover:scale-110`}>
                              <m.icon className={`w-5 h-5 ${m.color}`} />
                            </div>
                            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#8c909f] group-hover:text-white transition-colors">
                              {m.label}
                            </span>
                          </button>
                        ))}
                      </motion.div>
                    </AnimatePresence>
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
          <ViewContainer key="uni" title="Sistem Academic" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <GlassCard className="bg-gradient-to-br from-[#ffb786]/10 to-transparent p-10 relative overflow-hidden group">
                   <div className="absolute top-0 right-0 w-64 h-64 bg-[#ffb786]/5 rounded-full blur-[100px] -mr-32 -mt-32" />
                   <div className="flex justify-between items-center relative z-10">
                      <p className="text-7xl font-thin tracking-tighter text-white">{uniSummary?.average_grade || '—'}</p>
                      <div className="w-16 h-16 rounded-2xl bg-[#ffb786]/10 flex items-center justify-center">
                         <TrendingUp className="text-[#ffb786] w-8 h-8" />
                      </div>
                   </div>
                   <p className="label-ethereal mt-6 tracking-[0.3em] opacity-40">Media Generală • Sesiune Curentă</p>
                </GlassCard>
                
                {/* Upcoming Exams */}
                {uniSummary?.exams?.length > 0 && (
                  <div className="space-y-8">
                     <div className="flex items-center gap-3 ml-2">
                        <div className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_10px_#fbbf24]" />
                        <h3 className="label-ethereal tracking-[0.3em]">Calendar Examene</h3>
                        <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                     </div>
                     <div className="grid gap-3">
                        {uniSummary.exams.map((e: any) => (
                          <div key={e.id} className="liquid-panel p-5 flex justify-between items-center bg-gradient-to-r from-amber-500/5 to-transparent">
                             <div className="space-y-1">
                                <p className="font-bold">{e.subject_name}</p>
                                <p className="label-ethereal text-[8px] opacity-40">{e.exam_type || 'Examen'}</p>
                             </div>
                             <div className="text-right">
                                <p className="text-xl font-thin">{new Date(e.exam_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</p>
                                <p className="label-ethereal text-[8px] opacity-40">{e.exam_time || '--:--'}</p>
                             </div>
                          </div>
                        ))}
                     </div>
                  </div>
                )}

                <div className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-red-400 shadow-[0_0_10px_rgba(248,113,113,0.5)]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Discipline Active</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>

                   <div className="grid gap-4">
                      {uniSummary?.subjects?.map((s: any) => {
                         const attPct = s.total_logged > 0 ? Math.round((s.attended_count / s.total_logged) * 100) : 0;
                         const isLowAtt = s.total_logged > 0 && attPct < (s.min_attendance_pct || 70);
                         return (
                           <div key={s.id} className="liquid-panel p-6 space-y-6 hover:bg-white/[0.05] transition-all group">
                              <div className="flex justify-between items-start">
                                 <div className="flex items-center gap-5">
                                    <div className="w-12 h-12 rounded-xl bg-[#ffb786]/5 flex items-center justify-center">
                                       <GraduationCap className="w-6 h-6 text-[#ffb786]" />
                                    </div>
                                    <div className="space-y-1">
                                       <p className="font-light text-2xl tracking-tight">{s.name}</p>
                                       <p className="label-ethereal text-[8px] opacity-30 uppercase tracking-widest">{s.class_type || 'Curs / Seminar'}</p>
                                    </div>
                                 </div>
                                 <div className="text-right space-y-1">
                                    <p className={`text-3xl font-thin ${isLowAtt ? 'text-red-400' : 'text-[#ffb786]'}`}>{attPct}%</p>
                                    <p className="label-ethereal text-[8px] opacity-20">Prezență</p>
                                 </div>
                              </div>
                              
                              <div className="w-full h-[1px] bg-white/5 rounded-full overflow-hidden">
                                 <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${attPct}%` }}
                                    className={`h-full ${isLowAtt ? 'bg-red-500' : 'bg-[#ffb786]'} opacity-40`}
                                 />
                              </div>

                              <div className="flex justify-between items-center">
                                 <div className="flex gap-2">
                                    {s.grades?.map((g: any, i: number) => (
                                      <span key={i} className="px-3 py-1 liquid-panel text-[10px] font-black text-[#ffb786] bg-[#ffb786]/5">{g.grade}</span>
                                    ))}
                                    {(!s.grades || s.grades.length === 0) && <span className="label-ethereal text-[8px] opacity-20 italic">Fără note</span>}
                                 </div>
                                 <span className="label-ethereal text-[8px] opacity-20">{s.credits || 0} Credite</span>
                              </div>
                           </div>
                         );
                      })}
                   </div>
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'shop' && (
          <ViewContainer key="shop" title="Shopping List" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="flex justify-between items-center px-2">
                   <div className="space-y-1">
                     <p className="text-4xl font-thin tracking-tight">{shopping.filter(i => !i.is_bought).length}</p>
                     <p className="label-ethereal text-[8px]">Produse de achiziționat</p>
                   </div>
                   <button 
                     onClick={() => fetch(`${BASE_URL}/api/shopping/clear`, { method: 'DELETE', headers: HEADERS }).then(fetchData)} 
                     className="label-ethereal text-red-400 hover:text-red-300 transition-colors p-4 liquid-panel"
                   >
                     Arhivează
                   </button>
                </div>

                <div className="space-y-12">
                   {Object.entries(
                     shopping.reduce((acc: any, i) => {
                       const cat = i.category || 'Altele';
                       if (!acc[cat]) acc[cat] = [];
                       acc[cat].push(i);
                       return acc;
                     }, {})
                   ).map(([cat, items]: [string, any]) => (
                     <section key={cat} className="space-y-6">
                        <div className="flex items-center gap-3 ml-2">
                           <div className="w-2 h-2 rounded-full bg-pink-400 shadow-[0_0_10px_#f472b6]" />
                           <h3 className="label-ethereal tracking-[0.3em]">{cat}</h3>
                           <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                        </div>
                        <div className="grid gap-3">
                           {items.map((i: any) => (
                             <div 
                               key={i.id} 
                               className={`liquid-panel p-6 flex items-center justify-between transition-all cursor-pointer group ${i.is_bought ? 'opacity-40 grayscale' : 'hover:bg-white/5'}`}
                               onClick={() => fetch(`${BASE_URL}/api/shopping/${i.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ is_bought: !i.is_bought }) }).then(fetchData)}
                             >
                                <div className="flex items-center gap-6">
                                   <div className={`w-6 h-6 rounded-lg border-[0.5px] transition-all flex items-center justify-center ${i.is_bought ? 'bg-[#4cd7f6] border-[#4cd7f6]' : 'border-white/20 group-hover:border-white/40'}`}>
                                      {i.is_bought && <CheckCircle2 className="w-4 h-4 text-black" />}
                                   </div>
                                   <p className={`text-lg font-light tracking-tight ${i.is_bought ? 'line-through' : ''}`}>{i.item}</p>
                                </div>
                             </div>
                           ))}
                        </div>
                     </section>
                   ))}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'notes' && (
          <ViewContainer key="notes" title="Creier / Note" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <div className="liquid-panel p-4 flex items-center gap-4 group mx-2">
                   <Search className="w-5 h-5 opacity-20 group-focus-within:opacity-100 transition-opacity" />
                   <input 
                     type="text" 
                     placeholder="Caută în memorie..." 
                     className="bg-transparent border-none outline-none flex-grow label-ethereal tracking-widest text-white placeholder:opacity-20"
                     onChange={(e) => setNoteSearch(e.target.value)}
                   />
                </div>

                <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2 px-2">
                   {['toate', 'idei', 'jurnal', 'lucru'].map(tag => (
                     <button 
                       key={tag}
                       onClick={(e) => { e.stopPropagation(); setSelectedTag(tag); }}
                       className={`px-4 py-2 rounded-full text-[8px] label-ethereal border-[0.5px] transition-all whitespace-nowrap ${selectedTag === tag ? 'bg-[#adc6ff] text-black border-[#adc6ff]' : 'border-white/10 opacity-40 hover:opacity-100'}`}
                     >
                       {tag.toUpperCase()}
                     </button>
                   ))}
                </div>

                <div className="grid gap-4 px-2">
                   {notes
                     .filter(n => (selectedTag === 'toate' || (n.tags && n.tags.includes(selectedTag))))
                     .filter(n => (n.title?.toLowerCase() || '').includes(noteSearch.toLowerCase()) || n.content.toLowerCase().includes(noteSearch.toLowerCase()))
                     .map(n => (
                      <div key={n.id} className="liquid-panel p-6 space-y-4 hover:bg-white/[0.05] transition-all group relative overflow-hidden">
                         <div className="flex justify-between items-start relative z-10">
                            <div className="space-y-1">
                               <h4 className="text-xl font-light tracking-tight text-white group-hover:text-[#adc6ff] transition-colors">{n.title || 'Notă fără titlu'}</h4>
                               <p className="label-ethereal text-[8px] opacity-30">{new Date(n.created_at).toLocaleDateString()}</p>
                            </div>
                            <div className={`w-10 h-10 rounded-xl ${n.is_pinned ? 'bg-blue-500/20' : 'bg-white/5'} flex items-center justify-center`}>
                               <Pin className={`w-4 h-4 ${n.is_pinned ? 'text-blue-400' : 'text-gray-600'}`} />
                            </div>
                         </div>
                         <p className="text-sm font-light leading-relaxed text-white/50 line-clamp-3 group-hover:text-white/70 transition-colors">{n.content}</p>
                      </div>
                   ))}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'memory' && (
          <ViewContainer title="Memorie Core" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <GlassCard className="bg-gradient-to-br from-emerald-500/10 to-transparent p-10 relative overflow-hidden group">
                   <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[100px] -mr-32 -mt-32" />
                   <div className="flex justify-between items-center relative z-10">
                      <p className="text-7xl font-thin tracking-tighter text-white">{memories.length}</p>
                      <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                         <Brain className="text-emerald-500 w-8 h-8" />
                      </div>
                   </div>
                   <p className="label-ethereal mt-6 tracking-[0.3em] opacity-40 uppercase">Fragmente de Memorie Extrase</p>
                </GlassCard>
                
                <div className="space-y-12">
                   {['personal', 'preference', 'pattern', 'achievement', 'relationship', 'goal'].map(cat => {
                      const catMems = memories.filter(m => m.category === cat);
                      if (catMems.length === 0) return null;
                      return (
                        <section key={cat} className="space-y-6">
                           <div className="flex items-center gap-3 ml-2">
                              <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_#10b981]" />
                              <h4 className="label-ethereal tracking-[0.3em]">{cat}</h4>
                              <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                           </div>
                           <div className="grid gap-4">
                              {catMems.map(m => (
                                <div key={m.id} className="liquid-panel p-6 space-y-4 hover:bg-white/[0.05] transition-all">
                                   <p className="text-xl font-light leading-relaxed text-white/90">{m.fact}</p>
                                   <div className="flex justify-between items-center pt-2 border-t border-white/5">
                                      <span className="label-ethereal text-[8px] opacity-20 uppercase tracking-widest">{new Date(m.created_at).toLocaleDateString('ro-RO')}</span>
                                      <div className="flex items-center gap-2">
                                         <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/30" />
                                         <span className="label-ethereal text-[8px] text-emerald-500/50 uppercase font-black">Confidență: {Math.round(m.confidence * 100)}%</span>
                                      </div>
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
          <ViewContainer title="Status Vital" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="grid grid-cols-3 gap-4">
                   {[
                     { icon: Moon, val: healthLogs[0]?.sleep_hours || '—', label: 'Somn', color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
                     { icon: Droplets, val: healthLogs[0]?.water_ml || 0, label: 'Apă', color: 'text-blue-400', bg: 'bg-blue-400/10' },
                     { icon: Scale, val: healthLogs[0]?.weight_kg || '—', label: 'Greutate', color: 'text-emerald-400', bg: 'bg-emerald-400/10' }
                   ].map((stat, i) => (
                     <div key={i} className="liquid-panel p-6 text-center space-y-4 group hover:bg-white/[0.05] transition-all">
                        <div className={`w-10 h-10 rounded-xl ${stat.bg} mx-auto flex items-center justify-center group-hover:scale-110 transition-transform`}>
                           <stat.icon className={`w-5 h-5 ${stat.color}`} />
                        </div>
                        <div>
                           <p className="text-2xl font-light tracking-tighter">{stat.val}</p>
                           <p className="label-ethereal text-[8px] opacity-30 uppercase tracking-widest mt-1">{stat.label}</p>
                        </div>
                     </div>
                   ))}
                </div>

                <div className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.5)]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Istoric Vital</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>
                   <div className="grid gap-3">
                      {healthLogs.map(l => (
                        <div key={l.id} className="liquid-panel p-5 flex justify-between items-center hover:bg-white/[0.05] transition-all group">
                           <div className="flex items-center gap-5">
                              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center group-hover:rotate-12 transition-transform">
                                 <Heart className="w-6 h-6 text-rose-400 opacity-50 group-hover:opacity-100" />
                              </div>
                              <div>
                                 <p className="text-xl font-light tracking-tight">{new Date(l.log_date).toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'short' })}</p>
                                 <p className="label-ethereal text-[8px] opacity-30 uppercase tracking-widest mt-1">Calitate somn: {l.sleep_quality || '—'}</p>
                              </div>
                           </div>
                           <div className={`px-4 py-2 rounded-xl text-[9px] font-black uppercase tracking-[0.2em] liquid-panel border-none ${l.nutrition === 'great' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-orange-500/10 text-orange-400'}`}>
                              {l.nutrition}
                           </div>
                        </div>
                      ))}
                   </div>
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'calendar' && (
          <ViewContainer title="Planificare" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <section className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Evenimente Azi</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>
                   
                   <div className="grid gap-4">
                      {calendarToday?.events?.map((e: any) => (
                        <div key={e.id} className="liquid-panel p-6 flex items-center gap-6 group hover:bg-white/[0.05] transition-all">
                           <div className="w-14 h-14 rounded-2xl bg-blue-500/10 flex flex-col items-center justify-center border border-blue-500/20">
                              <span className="text-[10px] font-black text-blue-400 uppercase tracking-tighter">{e.event_time?.slice(0, 5) || 'All'}</span>
                              <span className="text-[8px] font-black text-blue-400/40 uppercase">Day</span>
                           </div>
                           <div className="flex-grow space-y-1">
                              <p className="text-2xl font-light tracking-tight text-white group-hover:text-[#adc6ff] transition-colors">{e.title}</p>
                              <p className="label-ethereal text-[10px] opacity-30 leading-relaxed line-clamp-1">{e.description || 'Nicio descriere definită.'}</p>
                           </div>
                        </div>
                      ))}
                      {(!calendarToday?.events || calendarToday.events.length === 0) && (
                        <div className="py-12 text-center liquid-panel border-dashed border-white/5 opacity-40">
                           <p className="label-ethereal text-[10px] tracking-[0.3em]">Liniște Digitală • Fără Evenimente</p>
                        </div>
                      )}
                   </div>
                </section>

                <section className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-orange-400 shadow-[0_0_10px_rgba(251,146,60,0.5)]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Orar Academic</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>
                   <div className="grid gap-3">
                      {calendarToday?.schedule?.map((s: any) => (
                        <div key={s.id} className="liquid-panel p-5 flex items-center gap-6 hover:bg-white/[0.05] transition-all group">
                           <div className="w-14 h-14 rounded-2xl bg-orange-400/10 flex items-center justify-center border border-orange-400/20">
                              <p className="text-xl font-thin text-orange-400">{s.start_time.slice(0, 5)}</p>
                           </div>
                           <div className="flex-grow space-y-1">
                              <p className="text-xl font-light tracking-tight">{s.subject_name}</p>
                              <div className="flex items-center gap-3 opacity-30">
                                 <span className="text-[9px] label-ethereal tracking-widest uppercase">{s.class_type}</span>
                                 <span className="w-1 h-1 rounded-full bg-white/20" />
                                 <span className="text-[9px] label-ethereal tracking-widest uppercase">{s.room}</span>
                              </div>
                           </div>
                        </div>
                      ))}
                   </div>
                </section>
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
                  <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-12">
                     <div className="text-center space-y-6">
                        <p className="label-ethereal tracking-[0.4em] opacity-40">Progres Nou</p>
                        <h2 className="text-6xl font-thin tracking-tighter text-[#adc6ff]">{selectedSkill.name}</h2>
                     </div>
                     
                     <div className="relative group">
                        <div className="absolute -inset-10 bg-blue-500/5 blur-3xl rounded-full group-hover:bg-blue-500/10 transition-all" />
                        <div className="relative flex items-center justify-center gap-4">
                           <input 
                             type="number" 
                             value={logValue} 
                             onChange={(e) => setLogValue(e.target.value)}
                             placeholder="0"
                             className="bg-transparent text-8xl font-thin w-48 text-center outline-none border-b-[0.5px] border-[#3b82f6]/20 focus:border-[#3b82f6] transition-all placeholder:opacity-5"
                             autoFocus
                           />
                           <span className="label-ethereal text-xl pb-6 opacity-30 tracking-widest">{selectedSkill.unit}</span>
                        </div>
                     </div>

                     <button 
                       onClick={async () => {
                         await fetch(`${BASE_URL}/api/skills/log`, { method: 'POST', headers: HEADERS, body: JSON.stringify({ skill_id: selectedSkill.id, value: logValue, metric: selectedSkill.unit }) });
                         setSelectedSkill(null); setLogValue(''); fetchData();
                       }}
                       className="px-12 py-6 liquid-panel border-blue-500/20 text-[#adc6ff] text-xs uppercase tracking-[0.4em] font-black hover:bg-blue-500/10 hover:scale-105 active:scale-95 transition-all"
                     >
                       Sincronizează
                     </button>
                  </div>
                ) : (
                  <div className="space-y-16">
                    {Array.from(new Set(skills.map(s => s.category || 'Personal'))).sort().map(cat => {
                      const catSkills = skills.filter(s => (s.category || 'Personal') === cat);
                      if (catSkills.length === 0) return null;
                      
                      let CatIcon = Zap;
                      if (cat.toLowerCase().includes('academic') || cat.toLowerCase().includes('uni')) CatIcon = GraduationCap;
                      if (cat.toLowerCase().includes('sport') || cat.toLowerCase().includes('fizic')) CatIcon = Dumbbell;
                      if (cat.toLowerCase().includes('lectur')) CatIcon = BookOpen;
                      if (cat.toLowerCase().includes('finan')) CatIcon = Wallet;

                      return (
                        <section key={cat} className="space-y-8">
                           <div className="flex items-center gap-4 ml-2">
                              <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                                 <CatIcon className="w-4 h-4 text-[#adc6ff]" />
                              </div>
                              <h4 className="label-ethereal tracking-[0.3em]">{cat}</h4>
                           </div>

                           <div className="grid gap-4">
                              {catSkills.map(s => (
                                <div 
                                  key={s.id} 
                                  className="liquid-panel p-6 space-y-6 hover:bg-white/[0.05] transition-all cursor-pointer group" 
                                  onClick={() => { setSelectedSkill(s); setLogValue(''); }}
                                >
                                   <div className="flex justify-between items-start">
                                      <div className="flex items-center gap-5">
                                         <div className="w-12 h-12 rounded-xl bg-[#adc6ff]/5 flex items-center justify-center group-hover:scale-110 transition-transform">
                                            <TrendingUp className="w-5 h-5 text-[#adc6ff]" />
                                         </div>
                                         <div className="space-y-1">
                                            <p className="font-light text-2xl tracking-tight text-white/90 group-hover:text-white transition-colors">{s.name}</p>
                                            <div className="flex items-center gap-3">
                                               <span className="label-ethereal text-[8px] opacity-40 uppercase tracking-widest">Nivel {s.level || 1}</span>
                                               {s.streak > 0 && (
                                                  <div className="flex items-center gap-1.5 text-orange-400">
                                                     <Flame className="w-2.5 h-2.5" />
                                                     <span className="text-[9px] font-black">{s.streak}d</span>
                                                  </div>
                                               )}
                                            </div>
                                         </div>
                                      </div>
                                      <p className="text-4xl font-thin text-[#4cd7f6] opacity-80">{s.progress || 0}%</p>
                                   </div>
                                   
                                   <div className="w-full h-[2px] bg-white/5 rounded-full overflow-hidden">
                                      <motion.div 
                                         initial={{ width: 0 }}
                                         animate={{ width: `${s.progress || 0}%` }}
                                         className="h-full bg-gradient-to-r from-[#4cd7f6]/20 to-[#4cd7f6] shadow-[0_0_15px_rgba(76,215,246,0.5)]"
                                      />
                                   </div>

                                   <div className="flex justify-between items-center pt-2">
                                      <span className="label-ethereal text-[8px] opacity-20 uppercase tracking-widest">XP {s.total_exp || 0} • {s.last_log_date ? new Date(s.last_log_date).toLocaleDateString('ro-RO') : 'No data'}</span>
                                      {s.last_value && <span className="text-[10px] font-bold text-[#adc6ff]/60">+{s.last_value} {s.unit}</span>}
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
          <ViewContainer key="finance" title="Tezaur & Fluxuri" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="liquid-panel p-12 text-center relative overflow-hidden group bg-gradient-to-br from-emerald-500/5 to-transparent">
                   <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[100px] -mr-32 -mt-32" />
                   <p className="label-ethereal mb-6 tracking-[0.4em] opacity-40">Lichiditate Totală</p>
                   <p className="text-8xl font-thin tracking-tighter text-white">
                      {finance?.balance || 0} <span className="text-2xl font-light text-emerald-400/40 tracking-normal ml-2">RON</span>
                   </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                   <div className="liquid-panel p-8 space-y-3 bg-gradient-to-br from-emerald-500/5 to-transparent">
                      <p className="label-ethereal text-[9px] tracking-widest text-emerald-400">Flux Intrare</p>
                      <p className="text-4xl font-thin text-white">+{finance?.total_income || 0}</p>
                   </div>
                   <div className="liquid-panel p-8 space-y-3 bg-gradient-to-br from-red-500/5 to-transparent">
                      <p className="label-ethereal text-[9px] tracking-widest text-red-400">Flux Ieșire</p>
                      <p className="text-4xl font-thin text-white">-{finance?.total_expenses || 0}</p>
                   </div>
                </div>

                {/* Category Breakdown */}
                <div className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_#10b981]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Distribuție Categorii</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>
                   <div className="grid gap-6">
                      {Object.entries(
                        financeHistory.filter(t => t.type === 'expense').reduce((acc: any, t) => {
                          acc[t.category] = (acc[t.category] || 0) + Number(t.amount);
                          return acc;
                        }, {})
                      ).sort((a: any, b: any) => b[1] - a[1]).slice(0, 5).map(([cat, amt]: [string, any]) => {
                        const pct = finance?.total_expenses > 0 ? Math.round((amt / finance.total_expenses) * 100) : 0;
                        return (
                          <div key={cat} className="space-y-3">
                             <div className="flex justify-between text-[10px] label-ethereal tracking-widest">
                                <span>{cat}</span>
                                <span className="opacity-40">{amt} RON • {pct}%</span>
                             </div>
                             <div className="h-[2px] bg-white/5 rounded-full overflow-hidden">
                                <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} className="h-full bg-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.3)]" />
                             </div>
                          </div>
                        );
                      })}
                   </div>
                </div>

                <div className="space-y-8">
                   <div className="flex items-center gap-3 ml-2">
                      <div className="w-2 h-2 rounded-full bg-[#adc6ff] shadow-[0_0_10px_#adc6ff]" />
                      <h3 className="label-ethereal tracking-[0.3em]">Istoric Recent</h3>
                      <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                   </div>

                   <div className="grid gap-3">
                      {financeHistory.slice(0, 15).map((tx: any) => (
                        <div key={tx.id} className="liquid-panel p-4 flex items-center gap-5 hover:bg-white/[0.05] transition-all group">
                           <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${tx.type === 'income' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-400/10 text-red-400'} group-hover:scale-110`}>
                              {tx.type === 'income' ? <TrendingUp className="w-6 h-6" /> : <Wallet className="w-6 h-6" />}
                           </div>
                           <div className="flex-grow space-y-1">
                              <p className="text-xl font-light tracking-tight text-white/90 group-hover:text-white transition-colors">{tx.description || tx.category}</p>
                              <div className="flex items-center gap-4">
                                 <span className="text-[9px] label-ethereal tracking-widest opacity-30 uppercase">{tx.category}</span>
                                 <span className="w-1 h-1 rounded-full bg-white/10" />
                                 <span className="text-[9px] label-ethereal tracking-widest opacity-30">{new Date(tx.tx_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</span>
                              </div>
                           </div>
                           <p className={`text-2xl font-thin tabular-nums ${tx.type === 'income' ? 'text-emerald-400' : 'text-white'}`}>
                              {tx.type === 'income' ? '+' : '-'}{tx.amount}
                           </p>
                        </div>
                      ))}
                   </div>
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'tasks' && (
          <ViewContainer key="tasks" title="Task-uri & Operativ" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="flex gap-4 p-1 liquid-panel rounded-2xl mx-2">
                   {['active', 'done'].map(s => (
                     <button 
                       key={s}
                       onClick={(e) => { e.stopPropagation(); setTaskFilter(s as any); }}
                       className={`flex-1 py-3 rounded-xl text-[10px] label-ethereal transition-all ${taskFilter === s ? 'bg-white/10 text-white shadow-xl' : 'opacity-30'}`}
                     >
                       {s === 'active' ? 'În Lucru' : 'Finalizate'}
                     </button>
                   ))}
                </div>

                {Object.entries(
                  (tasks || []).filter(t => t && (taskFilter === 'done' ? t.status === 'done' : t.status !== 'done')).reduce((acc: any, t) => {
                    if (!t) return acc;
                    const p = t.project_name || 'Fără proiect';
                    if (!acc[p]) acc[p] = [];
                    acc[p].push(t);
                    return acc;
                  }, {})
                ).map(([proj, projTasks]: [string, any]) => (
                  <section key={proj} className="space-y-6">
                     <div className="flex items-center gap-3 ml-2">
                        <div className={`w-2 h-2 rounded-full ${taskFilter === 'done' ? 'bg-emerald-500' : 'bg-[#adc6ff]'} shadow-[0_0_10px_rgba(173,198,255,0.5)]`} />
                        <h3 className="label-ethereal tracking-[0.3em]">{proj}</h3>
                        <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                        <span className="text-[10px] font-bold opacity-20">{projTasks.length}</span>
                     </div>
                     <div className="grid gap-3">
                        {projTasks.map((t: any) => (
                          <div 
                            key={t.id} 
                            className={`liquid-panel p-4 flex items-center gap-5 group cursor-pointer hover:bg-white/[0.05] transition-all relative overflow-hidden ${t.priority === 'high' ? 'border-r-rose-500/20 border-r-2' : ''}`}
                            onClick={() => fetch(`${BASE_URL}/api/tasks/${t.id}`, { 
                              method: 'PATCH', 
                              headers: HEADERS, 
                              body: JSON.stringify({ action: taskFilter === 'done' ? 'reopen' : 'complete' }) 
                            }).then(fetchData)}
                          >
                            <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${t.priority === 'high' ? 'bg-rose-500/10 text-rose-400' : 'bg-white/5 text-gray-500'} group-hover:scale-110`}>
                               {t.status === 'done' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : (t.priority === 'high' ? <Zap className="w-5 h-5 fill-rose-400/20" /> : <CheckCircle2 className="w-5 h-5 opacity-20 group-hover:opacity-100 transition-opacity" />)}
                            </div>
                            <div className="flex-grow space-y-1">
                               <p className={`font-light text-xl tracking-tight transition-all ${t.status === 'done' ? 'text-white/30 line-through' : 'text-white/90 group-hover:text-white'}`}>{t.title}</p>
                               <div className="flex items-center gap-4">
                                 {t.due_date && (
                                   <div className="flex items-center gap-1.5 opacity-40">
                                     <Calendar className="w-3 h-3" />
                                     <span className="text-[10px] label-ethereal tracking-wider">{new Date(t.due_date).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}</span>
                                   </div>
                                 )}
                                 {t.priority === 'high' && <span className="text-[8px] font-black text-rose-400 uppercase tracking-[0.2em]">Priority High</span>}
                               </div>
                            </div>
                          </div>
                        ))}
                     </div>
                  </section>
                ))}

                {(tasks || []).filter(t => t && (taskFilter === 'done' ? t.status === 'done' : t.status !== 'done')).length === 0 && (
                  <div className="py-32 text-center space-y-6">
                     <CheckCircle2 className="w-12 h-12 text-blue-500/10 mx-auto" />
                     <p className="label-ethereal opacity-40 italic">Sistem optimizat • Nicio înregistrare în această categorie</p>
                  </div>
                )}
             </div>
             
             <button onClick={() => setIsAddingTask(true)} className="fixed bottom-12 right-12 w-16 h-16 rounded-full bg-[#3b82f6]/20 border-[0.5px] border-[#3b82f6]/40 backdrop-blur-xl flex items-center justify-center hover:scale-110 active:scale-95 transition-all z-[110] shadow-[0_0_40px_rgba(59,130,246,0.2)]">
                <Plus className="w-8 h-8 text-[#adc6ff]" />
             </button>
          </ViewContainer>
        )}

        {view === 'projects' && (
          <ViewContainer title="Arhivă Proiecte" onBack={() => setView('home')}>
             <div className="space-y-12 pb-32">
                <div className="grid gap-4">
                   {projects.map((p: any) => {
                     const total = (p.pending_tasks || 0) + (p.completed_tasks || 0);
                     const progress = total > 0 ? Math.round((p.completed_tasks / total) * 100) : 0;
                     
                     return (
                       <div key={p.id} className="liquid-panel p-6 space-y-6 group hover:bg-white/[0.05] transition-all cursor-pointer">
                          <div className="flex justify-between items-start">
                             <div className="flex items-center gap-5">
                                <div className="w-14 h-14 rounded-2xl bg-[#adc6ff]/5 flex items-center justify-center group-hover:rotate-6 transition-transform">
                                   <Database className="w-7 h-7 text-[#adc6ff] opacity-40 group-hover:opacity-100" />
                                </div>
                                <div className="space-y-1">
                                   <div className="flex items-center gap-3">
                                      <h3 className="text-2xl font-light tracking-tight text-white">{p.name}</h3>
                                      {p.priority === 'high' && <Zap className="w-3 h-3 text-rose-400 animate-pulse" />}
                                   </div>
                                   <p className="label-ethereal text-[8px] opacity-30 tracking-[0.2em] uppercase">{p.category || 'General'}</p>
                                </div>
                             </div>
                             <div className="text-right">
                                <p className="text-3xl font-thin text-[#adc6ff]">{progress}%</p>
                                <p className="label-ethereal text-[8px] opacity-20">Progres</p>
                             </div>
                          </div>

                          <div className="w-full h-[2px] bg-white/5 rounded-full overflow-hidden">
                             <motion.div 
                               initial={{ width: 0 }}
                               animate={{ width: `${progress}%` }}
                               className={`h-full ${progress === 100 ? 'bg-emerald-500' : p.overdue_tasks > 0 ? 'bg-red-500' : 'bg-[#adc6ff]'} opacity-40 shadow-[0_0_15px_rgba(173,198,255,0.3)]`}
                             />
                          </div>

                          <div className="flex justify-between items-center pt-2">
                             <p className="text-[10px] font-light text-white/40 leading-relaxed max-w-md line-clamp-1">{p.description || 'Nicio descriere definită.'}</p>
                             <span className="label-ethereal text-[8px] opacity-20">{p.completed_tasks}/{total} Tasks</span>
                          </div>
                       </div>
                     );
                   })}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'reading' && (
          <ViewContainer title="Lectură & Knowledge" onBack={() => setView('home')}>
            <div className="space-y-12 pb-32">
              <div className="grid gap-4">
                {readingList.map((book: any) => (
                  <div key={book.id} className="liquid-panel p-6 space-y-6 hover:bg-white/[0.05] transition-all group">
                    <div className="flex justify-between items-start">
                      <div className="flex items-center gap-5">
                         <div className="w-14 h-14 rounded-2xl bg-orange-400/5 flex items-center justify-center group-hover:scale-110 transition-transform">
                            <BookOpen className="w-7 h-7 text-orange-400 opacity-40 group-hover:opacity-100" />
                         </div>
                         <div className="space-y-1">
                            <h4 className="text-2xl font-light tracking-tight text-white">{book.title}</h4>
                            <p className="label-ethereal text-[8px] opacity-30 tracking-[0.2em] uppercase">{book.author}</p>
                         </div>
                      </div>
                      <div className="text-right">
                         <p className="text-3xl font-thin text-orange-400">{book.progress_pct}%</p>
                         <p className="label-ethereal text-[8px] opacity-20">Lecturat</p>
                      </div>
                    </div>
                    
                    <div className="w-full h-[2px] bg-white/5 rounded-full overflow-hidden">
                       <motion.div 
                          initial={{ width: 0 }} 
                          animate={{ width: `${book.progress_pct}%` }} 
                          className="h-full bg-orange-400 opacity-40 shadow-[0_0_10px_rgba(251,146,60,0.3)]" 
                       />
                    </div>

                    <div className="flex justify-between items-center text-[9px] label-ethereal opacity-20">
                       <span>Ultima sesiune: {book.last_read ? new Date(book.last_read).toLocaleDateString('ro-RO') : 'N/A'}</span>
                       <span>{book.total_pages ? `${book.current_page}/${book.total_pages} pag` : 'Progres digital'}</span>
                    </div>
                  </div>
                ))}
                {readingList.length === 0 && (
                  <div className="py-24 text-center liquid-panel border-dashed border-white/5 opacity-40">
                    <p className="label-ethereal text-[10px] tracking-[0.3em]">Bibliotecă în așeptare</p>
                  </div>
                )}
              </div>
            </div>
          </ViewContainer>
        )}

        {view === 'travel' && (
          <ViewContainer title="Sistem Travel" onBack={() => {
            if (selectedTravelList) setSelectedTravelList(null);
            else setView('home');
          }}>
             <div className="space-y-12 pb-32">
                {selectedTravelList ? (
                  <div className="space-y-8">
                     <div className="flex items-center gap-3 ml-2">
                        <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_10px_#60a5fa]" />
                        <h3 className="label-ethereal tracking-[0.3em]">{selectedTravelList}</h3>
                        <div className="h-[1px] flex-grow bg-white/5 ml-2" />
                     </div>
                     <div className="grid gap-4">
                        {travelItems.map(i => (
                          <div 
                            key={i.id} 
                            className={`liquid-panel p-6 flex items-center justify-between transition-all cursor-pointer group ${i.is_packed ? 'opacity-40 grayscale' : 'hover:bg-white/5'}`}
                            onClick={() => toggleTravelItem(i.id, !i.is_packed)}
                          >
                             <div className="flex items-center gap-6">
                                <div className={`w-6 h-6 rounded-lg border-[0.5px] transition-all flex items-center justify-center ${i.is_packed ? 'bg-[#3b82f6] border-[#3b82f6]' : 'border-white/20 group-hover:border-white/40'}`}>
                                   {i.is_packed && <CheckCircle2 className="w-4 h-4 text-white" />}
                                </div>
                                <p className={`text-lg font-light tracking-tight ${i.is_packed ? 'line-through' : ''}`}>{i.item}</p>
                             </div>
                             <span className="label-ethereal text-[8px] opacity-40 px-3 py-1 liquid-panel border-none">
                                {i.trip_type === 'departure' ? 'Plec' : i.trip_type === 'return' ? 'Întors' : 'Ambele'}
                             </span>
                          </div>
                        ))}
                        {travelItems.length === 0 && (
                          <div className="py-24 text-center liquid-panel border-dashed border-white/5 opacity-40">
                             <p className="label-ethereal text-[10px] tracking-[0.3em]">Lista este goală</p>
                          </div>
                        )}
                     </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                     {travelLists.map(listName => (
                        <GlassCard key={listName} className="p-8 group" onClick={() => {
                          setSelectedTravelList(listName);
                          fetchTravelItems(listName);
                        }}>
                           <div className="flex justify-between items-center">
                              <div className="space-y-1">
                                 <h4 className="text-2xl font-light tracking-tight text-white group-hover:text-[#adc6ff] transition-colors">{listName}</h4>
                                 <p className="label-ethereal text-[8px] opacity-30 uppercase tracking-[0.2em]">Vezi Bagaj</p>
                              </div>
                              <Plane className="w-6 h-6 text-blue-400/20 group-hover:text-blue-400 group-hover:scale-125 transition-all" />
                           </div>
                        </GlassCard>
                     ))}
                     {travelLists.length === 0 && (
                       <div className="col-span-2 py-32 text-center liquid-panel border-dashed border-white/5 opacity-40">
                          <p className="label-ethereal text-[10px] tracking-[0.3em]">Nicio listă de travel detectată</p>
                       </div>
                     )}
                  </div>
                )}
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

        {view === 'goals' && (
          <ViewContainer title="Obiective Strategice" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                {goals.length > 0 ? (
                  <div className="grid gap-4">
                    {goals.map((g: any) => (
                      <GlassCard key={g.id} className="p-6">
                        <div className="flex justify-between items-center">
                          <h4 className="text-xl font-light">{g.title}</h4>
                          <span className="label-ethereal text-[8px]">{g.status}</span>
                        </div>
                        <div className="mt-4 h-1 bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-orange-400 opacity-40" style={{ width: `${g.progress || 0}%` }} />
                        </div>
                      </GlassCard>
                    ))}
                  </div>
                ) : (
                  <div className="py-24 text-center opacity-30">
                    <Target className="w-12 h-12 mx-auto mb-4" />
                    <p className="label-ethereal">Niciun obiectiv activ</p>
                  </div>
                )}
             </div>
          </ViewContainer>
        )}

        {view === 'mood' && (
          <ViewContainer title="Stare & Energie" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <div className="grid grid-cols-2 gap-4">
                  {['Excited', 'Balanced', 'Tired', 'Low'].map(m => (
                    <GlassCard key={m} className="p-8 text-center hover:bg-white/5 cursor-pointer transition-all">
                      <p className="text-sm font-light">{m}</p>
                    </GlassCard>
                  ))}
                </div>
                <div className="space-y-4">
                   <h3 className="label-ethereal ml-2">Istoric Stări</h3>
                   {moodLogs.map((log: any, i) => (
                     <div key={i} className="liquid-panel p-4 flex justify-between">
                        <span className="opacity-40">{new Date(log.created_at).toLocaleDateString()}</span>
                        <span className="font-bold">{log.mood_score}/10</span>
                     </div>
                   ))}
                </div>
             </div>
          </ViewContainer>
        )}

        {view === 'focus' && (
          <ViewContainer title="Deep Work OS" onBack={() => setView('home')}>
             <div className="flex flex-col items-center justify-center py-20 space-y-12">
                <div className="relative w-64 h-64 flex items-center justify-center">
                   <div className="absolute inset-0 rounded-full border-4 border-white/5" />
                   <p className="text-7xl font-thin tracking-tighter kinetic-text">{formatTime(timeLeft)}</p>
                </div>
                <button onClick={() => setTimerActive(!timerActive)} className="primary-button px-12 py-5 text-lg">
                   {timerActive ? 'Pause Session' : 'Start Focus'}
                </button>
             </div>
          </ViewContainer>
        )}

        {view === 'insights' && (
          <ViewContainer title="AI Patterns" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <GlassCard className="p-8 bg-indigo-500/5 border-indigo-500/10">
                   <Brain className="w-8 h-8 text-indigo-400 mb-6" />
                   <p className="text-lg font-light leading-relaxed">
                     {insights?.summary || "Analizând datele tale pentru a genera tipare comportamentale... Revino peste câteva ore."}
                   </p>
                </GlassCard>
             </div>
          </ViewContainer>
        )}

        {view === 'news' && (
          <ViewContainer title="Tech & Global News" onBack={() => setView('home')}>
             <div className="space-y-6 pb-32">
                {news.map((n: any, i) => (
                  <GlassCard key={i} className="p-6">
                    <h4 className="font-bold mb-2">{n.title}</h4>
                    <p className="text-xs opacity-50">{n.source}</p>
                  </GlassCard>
                ))}
                {news.length === 0 && <p className="text-center py-20 opacity-30 label-ethereal">Nicio știre nouă</p>}
             </div>
          </ViewContainer>
        )}

        {view === 'planner' && (
          <ViewContainer title="Daily Planner" onBack={() => setView('home')}>
             <div className="space-y-4 pb-32">
                {['09:00', '12:00', '15:00', '18:00', '21:00'].map(t => (
                  <div key={t} className="flex gap-6 items-center">
                    <span className="label-ethereal w-12">{t}</span>
                    <div className="flex-grow h-[1px] bg-white/5" />
                    <div className="w-3/4 liquid-panel p-4 min-h-[60px] opacity-20 border-dashed">
                       <span className="text-[10px] uppercase tracking-widest">Liber</span>
                    </div>
                  </div>
                ))}
             </div>
          </ViewContainer>
        )}

        {view === 'system' && (
          <ViewContainer title="Lora Core OS" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <div className="grid grid-cols-2 gap-4">
                   <GlassCard className="p-6">
                      <p className="label-ethereal">Uptime</p>
                      <p className="text-2xl font-black">99.9%</p>
                   </GlassCard>
                   <GlassCard className="p-6">
                      <p className="label-ethereal">Memorie AI</p>
                      <p className="text-2xl font-black">{systemStats?.memory_usage || '4.2'} GB</p>
                   </GlassCard>
                </div>
                <div className="liquid-panel p-6">
                   <div className="flex items-center gap-3 mb-6">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="label-ethereal">Toate sistemele nominale</span>
                   </div>
                   <div className="space-y-2 opacity-40 text-[10px] font-mono">
                      <p>{'>'} Sincronizare baza de date... OK</p>
                      <p>{'>'} Verificare vector embeddings... OK</p>
                      <p>{'>'} Rulare analize euristice... OK</p>
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
