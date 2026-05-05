import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle2, Navigation, Plus, GraduationCap, 
  Dumbbell, Wallet, ArrowLeft, Loader2, Settings,
  Calendar, ShoppingCart, Heart, Flame, Brain, Play, Pause, RotateCcw,
  TrendingUp, Star, AlertTriangle, Moon, Droplets, Scale,
  Pin, MapPin, Search
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// --- Types & Constants ---
const API_SECRET = '73860b29fd5d087fd78a1e59fb23254ed1692139e933a9465de82ed709b7f70e';
const HEADERS = { 'X-Internal-Secret': API_SECRET, 'Content-Type': 'application/json' };

type View = 'home' | 'map' | 'uni' | 'gym' | 'skills' | 'shop' | 'notes' | 'health' | 'calendar' | 'finance' | 'tasks';

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
    try {
      const [t, f, u, g, s, shop, n, h, c] = await Promise.all([
        fetch('/api/tasks?status=all', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/finances/summary', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/university/summary', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/workout/stats', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/skills', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/shopping', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/notes', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/health/summary', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/calendar/today', { headers: HEADERS }).then(r => r.json())
      ]);
      setTasks(Array.isArray(t) ? t : []);
      setFinance(f);
      setUniSummary(u);
      setGymStats(g);
      setSkills(Array.isArray(s) ? s : []);
      setShopping(Array.isArray(shop) ? shop : []);
      setNotes(Array.isArray(n) ? n : []);
      setHealthLogs(Array.isArray(h) ? h : []);
      setCalendarToday(c);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
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

  if (loading) return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-white font-sans overflow-x-hidden selection:bg-blue-500/30">
      
      <AnimatePresence mode="wait">
        {view === 'home' && (
          <motion.div 
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="p-6 pb-20 space-y-8 max-w-md mx-auto"
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

            {/* Focus & Add Task */}
            <div className="grid grid-cols-2 gap-4">
              <GlassCard className="h-44 flex flex-col justify-between border-blue-500/20">
                <p className="text-[8px] font-black uppercase tracking-widest text-gray-500">Focus OS</p>
                <div className="text-center space-y-2">
                  <p className="text-3xl font-black tracking-tighter">{formatTime(timeLeft)}</p>
                  <div className="flex justify-center gap-2">
                    <button onClick={() => setTimerActive(!timerActive)} className="p-2 bg-blue-500/10 rounded-full">{timerActive ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}</button>
                    <button onClick={() => setTimeLeft(25 * 60)} className="p-2 bg-white/5 rounded-full"><RotateCcw className="w-4 h-4" /></button>
                  </div>
                </div>
              </GlassCard>
              <GlassCard className="h-44 flex flex-col justify-between" onClick={() => setIsAddingTask(true)}>
                <p className="text-[8px] font-black uppercase tracking-widest text-gray-500">Flux Nou</p>
                <div className="flex flex-col items-center gap-2">
                   <div className="w-12 h-12 rounded-full bg-blue-500 flex items-center justify-center shadow-[0_0_20px_rgba(59,130,246,0.4)]"><Plus className="w-6 h-6" /></div>
                   <p className="text-[10px] font-black uppercase text-blue-500">Adaugă Task</p>
                </div>
              </GlassCard>
            </div>

            {/* High Priorities Section */}
            <div className="space-y-4">
              <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2 flex justify-between items-center">
                <span>Priorități Critice</span>
                <span className="bg-red-500/10 text-red-500 px-2 py-0.5 rounded text-[8px]">{tasks.filter(t => t.priority === 'high' && t.status !== 'done').length}</span>
              </h3>
              <div className="space-y-3">
                {tasks.filter(t => t.priority === 'high' && t.status !== 'done').slice(0, 3).map(t => (
                  <GlassCard key={t.id} className="p-4 flex items-center gap-4 border-l-4 border-l-red-500" onClick={() => fetch(`/api/tasks/${t.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ action: 'complete' }) }).then(fetchData)}>
                    <div className="w-5 h-5 rounded-full border-2 border-red-500/30 flex items-center justify-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_8px_#ef4444]" />
                    </div>
                    <div className="flex-1">
                      <p className="font-bold text-sm leading-tight">{t.title}</p>
                      {t.project_name && <p className="text-[9px] text-gray-500 font-bold uppercase mt-1">Proiect: {t.project_name}</p>}
                    </div>
                  </GlassCard>
                ))}
                {tasks.filter(t => t.priority === 'high' && t.status !== 'done').length === 0 && (
                  <p className="text-center text-xs text-gray-600 font-bold py-2 italic">Toate prioritățile sunt sub control. ✨</p>
                )}
              </div>
            </div>

            {/* Module Hub */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { id: 'tasks', icon: CheckCircle2, label: 'Tasks', color: 'text-emerald-400' },
                { id: 'map', icon: Navigation, label: 'Hartă', color: 'text-blue-500' },
                { id: 'uni', icon: GraduationCap, label: 'Academic', color: 'text-orange-500' },
                { id: 'gym', icon: Dumbbell, label: 'Sală', color: 'text-red-500' },
                { id: 'skills', icon: Flame, label: 'Skills', color: 'text-yellow-500' },
                { id: 'shop', icon: ShoppingCart, label: 'Shop', color: 'text-purple-500' },
                { id: 'notes', icon: Brain, label: 'Brain', color: 'text-emerald-500' },
                { id: 'health', icon: Heart, label: 'Sănătate', color: 'text-pink-500' },
                { id: 'calendar', icon: Calendar, label: 'Plan', color: 'text-blue-400' }
              ].map(m => (
                <button key={m.id} onClick={() => setView(m.id as View)} className="flex flex-col items-center gap-2">
                  <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/5 flex items-center justify-center hover:bg-white/10 transition-colors">
                    <m.icon className={`w-5 h-5 ${m.color}`} />
                  </div>
                  <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">{m.label}</span>
                </button>
              ))}
            </div>

            {/* Today's Plan Preview */}
            <div className="space-y-4">
              <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-gray-500 px-2">Program Azi</h3>
              <div className="space-y-3">
                {calendarToday?.schedule?.slice(0, 2).map((s: any) => (
                  <div key={s.id} className="flex gap-4 items-center bg-white/[0.03] border border-white/5 p-4 rounded-2xl">
                    <div className="w-12 text-center">
                       <p className="text-[10px] font-black text-blue-500">{s.start_time.slice(0, 5)}</p>
                    </div>
                    <div className="flex-1">
                      <p className="font-bold text-sm">{s.subject_name}</p>
                      <p className="text-[9px] text-gray-500 font-bold uppercase">{s.class_type} | {s.room}</p>
                    </div>
                  </div>
                ))}
                {(!calendarToday?.schedule || calendarToday.schedule.length === 0) && (
                   <p className="text-center text-xs text-gray-600 font-bold py-4">Fără cursuri azi. Enjoy! ☕</p>
                )}
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
           <ViewContainer title="Hartă Lora" onBack={() => setView('home')}>
              <div className="relative w-full h-[70vh] rounded-[36px] overflow-hidden border border-white/10 bg-white/[0.02]">
                 <div className="absolute inset-0 flex flex-col items-center justify-center space-y-4">
                    <MapPin className="w-12 h-12 text-blue-500 animate-bounce" />
                    <p className="text-[10px] font-black uppercase tracking-[0.4em] text-gray-500">Localizare Neurală Activă</p>
                    <div className="w-48 h-1 bg-white/5 rounded-full overflow-hidden">
                       <motion.div initial={{ x: -100 }} animate={{ x: 100 }} transition={{ repeat: Infinity, duration: 1.5 }} className="w-20 h-full bg-blue-500 shadow-[0_0_10px_#3b82f6]" />
                    </div>
                 </div>
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
          <ViewContainer title="Finanțe" onBack={() => setView('home')}>
             <div className="space-y-6">
                <GlassCard className="bg-emerald-500/5">
                   <p className="text-4xl font-black tabular-nums">{finance?.balance || 0} <span className="text-xs">Lei</span></p>
                   <p className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest mt-2">Fonduri Disponibile</p>
                </GlassCard>
                <div className="grid grid-cols-2 gap-4">
                   <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-xs font-bold text-emerald-400">Venituri (30z)</p>
                      <p className="text-lg font-black">{finance?.income_30d || 0} Lei</p>
                   </div>
                   <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                      <p className="text-xs font-bold text-red-400">Cheltuieli (30z)</p>
                      <p className="text-lg font-black">{finance?.expenses_30d || 0} Lei</p>
                   </div>
                </div>
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
