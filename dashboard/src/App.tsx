import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, GraduationCap, 
  Wallet, Loader2,
  Heart, Brain, Play, Pause, RotateCcw,
  Moon, Droplets, Scale,
  MapPin, Sun, ShoppingBag, Zap, Cigarette
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Components ---
import { GlassCard } from './components/GlassCard';
import { ViewContainer } from './components/ViewContainer';
import { HealthCard } from './components/HealthCard';
import { FinanceChart } from './components/FinanceChart';
import { TaskSection } from './components/TaskSection';
import { AcademicCard } from './components/AcademicCard';
import { DynamicIsland } from './components/DynamicIsland';
import { TiltCard } from './components/TiltCard';

// --- Types & Constants ---
const API_SECRET = import.meta.env.VITE_LORA_API_SECRET || '73860b29fd5d087fd78a1e59fb23254ed1692139e933a9465de82ed709b7f70e';
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://lora-bot-tgbi.onrender.com';
const BASE_URL = RAW_BASE_URL.endsWith('/') ? RAW_BASE_URL.slice(0, -1) : RAW_BASE_URL;

const HEADERS = { 
  'X-Internal-Secret': API_SECRET, 
  'Content-Type': 'application/json',
  'Bypass-Tunnel-Reminder': 'true'
};

type View = 'home' | 'health' | 'finance' | 'tasks' | 'uni' | 'gym' | 'notes' | 'shop' | 'map';

function App() {
  const [view, setView] = useState<View>('home');
  const [tasks, setTasks] = useState<any[]>([]);
  const [finance, setFinance] = useState<any>(null);
  const [healthLogs, setHealthLogs] = useState<any[]>([]);
  const [calendarToday, setCalendarToday] = useState<any>(null);
  const [financeHistory, setFinanceHistory] = useState<any[]>([]);
  const [weather, setWeather] = useState<any>(null);
  
  const [timerActive, setTimerActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const timerRef = useRef<any>(null);
  const [notification, setNotification] = useState<{message: string, active: boolean, icon: any}>({ message: '', active: false, icon: null });

  const [loading, setLoading] = useState(true);

  const showNotification = (message: string, icon: any) => {
    setNotification({ message, active: true, icon });
    setTimeout(() => setNotification(prev => ({ ...prev, active: false })), 5000);
  };

  useEffect(() => {
    fetchData();
    const safety = setTimeout(() => setLoading(false), 5000);
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
      try {
        const fullUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`;
        const r = await fetch(fullUrl, { headers: HEADERS });
        if (!r.ok) return defaultValue;
        return await r.json();
      } catch (e) {
        console.error(`Failed to fetch ${url}:`, e);
        return defaultValue;
      }
    };

    try {
      const [t, f, h, c, f_hist, w] = await Promise.all([
        fetchModule('/api/tasks?status=all', []),
        fetchModule('/api/finances/summary'),
        fetchModule('/api/health/summary', []),
        fetchModule('/api/calendar/today'),
        fetchModule('/api/finances/chart', []),
        fetchModule('/api/weather')
      ]);

      setTasks(t);
      setFinance(f);
      setHealthLogs(h);
      setCalendarToday(c);
      setFinanceHistory(f_hist);
      setWeather(w);
    } catch (e: any) {
      console.error("Sync error:", e);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (loading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#030303] space-y-8">
        <motion.div
           animate={{ scale: [0.9, 1.1, 0.9], opacity: [0.3, 0.7, 0.3] }}
           transition={{ duration: 2, repeat: Infinity }}
           className="w-16 h-16 liquid-panel rounded-full flex items-center justify-center"
        >
           <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
        </motion.div>
        <p className="label-ethereal animate-pulse">Sincronizare Core OS...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-white font-sans overflow-x-hidden selection:bg-blue-500/30">
      <div className="aura-container">
        <div className="aura-blob aura-1 opacity-10" />
        <div className="aura-blob aura-2 opacity-10" />
      </div>

      <DynamicIsland active={notification.active} message={notification.message} icon={notification.icon} />
      
      <AnimatePresence mode="wait">
        {view === 'home' && (
          <motion.div 
            key="home"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="p-8 lg:p-16 pb-32 space-y-12 max-w-7xl mx-auto"
          >
            <header className="flex justify-between items-start">
              <div className="space-y-4">
                <h1 className="text-5xl sm:text-7xl font-thin tracking-[-0.05em] text-white kinetic-text">LORA<span className="text-blue-500">.</span></h1>
                <p className="label-ethereal flex items-center gap-2">
                   <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                   Sistem Nominal • {tasks.filter(t => t.status !== 'done').length} Priorități
                </p>
              </div>
            </header>

            {/* Main Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <FinanceChart summary={finance} history={financeHistory} onClick={() => setView('finance')} />
              <HealthCard logs={healthLogs} onClick={() => setView('health')} />
              <AcademicCard schedule={calendarToday?.schedule || []} onClick={() => setView('uni')} />
            </div>
            
            {/* Weather Bento */}
            {weather && (
              <TiltCard className="bg-gradient-to-br from-blue-500/5 to-transparent" onClick={() => setView('map')}>
                <div className="flex justify-between items-center">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-blue-400" />
                      <span className="label-ethereal">{weather.name}</span>
                    </div>
                    <div className="flex items-end gap-4">
                      <h3 className="text-6xl font-thin">{Math.round(weather.main?.temp)}°</h3>
                      <p className="label-ethereal pb-2 opacity-60">{weather.weather?.[0]?.description}</p>
                    </div>
                  </div>
                  <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 4, repeat: Infinity }}>
                    <Sun className="w-16 h-16 text-yellow-500/80 blur-[2px]" />
                  </motion.div>
                </div>
              </TiltCard>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Sidebar: System Shortcuts */}
              <div className="lg:col-span-4 space-y-6">
                <section className="grid grid-cols-2 gap-3">
                  {[
                    { id: 'tasks', icon: CheckCircle2, label: 'Tasks', color: 'text-emerald-400' },
                    { id: 'finance', icon: Wallet, label: 'Finance', color: 'text-emerald-500' },
                    { id: 'uni', icon: GraduationCap, label: 'Academic', color: 'text-amber-400' },
                    { id: 'health', icon: Heart, label: 'Health', color: 'text-pink-400' },
                    { id: 'notes', icon: Brain, label: 'Brain', color: 'text-purple-400' },
                    { id: 'shop', icon: ShoppingBag, label: 'Shop', color: 'text-pink-400' }
                  ].map(m => (
                    <button key={m.id} onClick={() => setView(m.id as View)} className="liquid-panel flex items-center gap-3 p-4 hover:bg-white/5 active:scale-95 transition-all">
                      <m.icon className={`w-4 h-4 ${m.color}`} />
                      <span className="text-[10px] font-black uppercase tracking-widest">{m.label}</span>
                    </button>
                  ))}
                </section>

                <TiltCard className="flex flex-col items-center justify-center h-64 border-blue-500/10">
                   <p className="label-ethereal mb-4">Focus Timer</p>
                   <p className="text-5xl font-thin tracking-tighter mb-6">{formatTime(timeLeft)}</p>
                   <div className="flex gap-4">
                      <button onClick={() => setTimerActive(!timerActive)} className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center">
                        {timerActive ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 pl-1" />}
                      </button>
                      <button onClick={() => setTimeLeft(25 * 60)} className="w-12 h-12 rounded-full liquid-panel flex items-center justify-center">
                        <RotateCcw className="w-5 h-5" />
                      </button>
                   </div>
                </TiltCard>
              </div>

              {/* Main Feed: Projects */}
              <div className="lg:col-span-8">
                <TaskSection tasks={tasks} onClick={() => setView('tasks')} />
              </div>
            </div>
          </motion.div>
        )}

        {/* Health View Extension */}
        {view === 'health' && (
          <ViewContainer title="Vitals Dashboard" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                   {[
                     { icon: Moon, val: healthLogs[0]?.sleep_hours || '—', label: 'Sleep', unit: 'h' },
                     { icon: Droplets, val: healthLogs[0]?.water_ml || '0', label: 'Water', unit: 'ml' },
                     { icon: Scale, val: healthLogs[0]?.weight_kg || '—', label: 'Weight', unit: 'kg' },
                     { icon: Cigarette, val: healthLogs[0]?.cigarettes || '0', label: 'Cigarettes', unit: '' }
                   ].map((s, i) => (
                     <GlassCard key={i} className="text-center space-y-2">
                        <s.icon className="w-5 h-5 mx-auto opacity-30" />
                        <p className="text-2xl font-black">{s.val}<span className="text-[10px] opacity-20 ml-1">{s.unit}</span></p>
                        <p className="label-ethereal opacity-40">{s.label}</p>
                     </GlassCard>
                   ))}
                </div>

                <div className="space-y-4">
                   <h3 className="label-ethereal ml-2">History (14 Days)</h3>
                   <div className="space-y-2">
                      {healthLogs.map((log, i) => (
                        <div key={i} className="liquid-panel p-4 flex justify-between items-center text-[11px]">
                           <span className="font-bold opacity-40">{new Date(log.log_date).toLocaleDateString('ro-RO')}</span>
                           <div className="flex gap-6">
                              <span>🌙 {log.sleep_hours || '—'}h</span>
                              <span>💧 {log.water_ml || 0}ml</span>
                              <span className={(log.cigarettes || 0) > 0 ? 'text-red-400' : ''}>🚬 {log.cigarettes || 0}</span>
                           </div>
                        </div>
                      ))}
                   </div>
                </div>
             </div>
          </ViewContainer>
        )}

        {/* Re-using original logic for other views but with new ViewContainer */}
        {view === 'finance' && (
          <ViewContainer title="Tezaur / Finance" onBack={() => setView('home')}>
             <div className="space-y-8 pb-32">
                <GlassCard className="bg-emerald-500/5 p-10 flex justify-between items-center">
                   <div className="space-y-2">
                      <p className="label-ethereal">Total Balanță</p>
                      <p className="text-5xl font-thin tracking-tighter">{finance?.balance || 0} Lei</p>
                   </div>
                   <div className="text-right space-y-1">
                      <p className="text-emerald-400 text-sm">↑ {finance?.total_income || 0}</p>
                      <p className="text-red-400 text-sm">↓ {finance?.total_expenses || 0}</p>
                   </div>
                </GlassCard>
                
                <div className="space-y-4">
                   <h3 className="label-ethereal ml-2">Recent Transactions</h3>
                   <div className="space-y-2">
                      {financeHistory.map((h, i) => (
                        <div key={i} className="liquid-panel p-4 flex justify-between items-center">
                           <div className="flex items-center gap-4">
                              <div className={`w-2 h-2 rounded-full ${h.type === 'income' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                              <span className="text-xs font-bold">{h.category}</span>
                           </div>
                           <span className={`text-sm font-black ${h.type === 'income' ? 'text-emerald-400' : 'text-red-400'}`}>
                             {h.type === 'income' ? '+' : '-'}{h.amount}
                           </span>
                        </div>
                      ))}
                   </div>
                </div>
             </div>
          </ViewContainer>
        )}

        {/* ... Other views would go here following the same pattern ... */}
        {/* I'll stop here to verify the main layout first */}

      </AnimatePresence>

      {/* Navigation Dock */}
      <nav className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[500]">
        <div className="liquid-panel px-8 py-4 rounded-full flex gap-12 border-white/10 shadow-2xl">
          <button onClick={() => setView('home')} className={`transition-all ${view === 'home' ? 'text-blue-400 scale-125' : 'text-gray-600 hover:text-white'}`}>
            <Sun className="w-6 h-6" />
          </button>
          <button onClick={() => setView('tasks')} className={`transition-all ${view === 'tasks' ? 'text-blue-400 scale-125' : 'text-gray-600 hover:text-white'}`}>
            <CheckCircle2 className="w-6 h-6" />
          </button>
          <button onClick={() => setView('finance')} className={`transition-all ${view === 'finance' ? 'text-blue-400 scale-125' : 'text-gray-600 hover:text-white'}`}>
            <Wallet className="w-6 h-6" />
          </button>
        </div>
      </nav>
    </div>
  );
}

export default App;
