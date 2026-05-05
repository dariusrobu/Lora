import { useState, useEffect } from 'react';
import { 
  CheckCircle2, Navigation, Zap, Plus, GraduationCap, 
  Dumbbell, Wallet, Clock, Loader2, Settings
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_SECRET = '73860b29fd5d087fd78a1e59fb23254ed1692139e933a9465de82ed709b7f70e';
const HEADERS = { 'X-Internal-Secret': API_SECRET, 'Content-Type': 'application/json' };

const Section = ({ title, children, action }: { title: string, children: React.ReactNode, action?: React.ReactNode }) => (
  <div className="space-y-4">
    <div className="flex justify-between items-center px-1">
      <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">{title}</h3>
      {action}
    </div>
    {children}
  </div>
);

const Card = ({ children, className = "" }: { children: React.ReactNode, className?: string }) => (
  <div className={`bg-[#111] border border-white/[0.05] rounded-[24px] p-6 ${className}`}>
    {children}
  </div>
);

function App() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [finance, setFinance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    try {
      const [t, f] = await Promise.all([
        fetch('/api/tasks', { headers: HEADERS }).then(r => r.json()),
        fetch('/api/finances/summary', { headers: HEADERS }).then(r => r.json())
      ]);
      setTasks(Array.isArray(t) ? t : []);
      setFinance(f);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleAddTask = async () => {
    if (!newTaskTitle) return;
    await fetch('/api/tasks', { method: 'POST', headers: HEADERS, body: JSON.stringify({ title: newTaskTitle, priority: 'medium' }) });
    setNewTaskTitle(''); setIsAddingTask(false);
    fetchInitialData();
  };

  if (loading) return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center space-y-4">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      <p className="text-[10px] font-black uppercase tracking-widest text-gray-500">Se încarcă Lora OS...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-white p-6 pb-32 font-sans selection:bg-blue-500/30 overflow-x-hidden">
      <div className="max-w-md mx-auto space-y-10">
        
        <header className="flex justify-between items-start">
          <div className="space-y-1">
            <h1 className="text-3xl font-black tracking-tighter uppercase">Lora OS<span className="text-blue-500">.</span></h1>
            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
              <Zap className="w-3 h-3 text-blue-500" /> {tasks.length} task-uri
            </div>
          </div>
        </header>

        <Section title="Task-uri Prioritare" action={<button onClick={() => setIsAddingTask(true)} className="text-blue-500 p-1"><Plus className="w-4 h-4" /></button>}>
          <div className="space-y-3">
            {tasks.slice(0, 3).map(t => (
              <div key={t.id} className="flex items-center justify-between bg-[#111] border border-white/[0.03] p-4 rounded-2xl">
                <div className="flex items-center gap-3">
                  <div className={`w-1 h-8 rounded-full ${t.priority === 'high' ? 'bg-red-500' : 'bg-blue-500'}`} />
                  <p className="font-bold text-sm">{t.title}</p>
                </div>
                <CheckCircle2 onClick={() => fetch(`/api/tasks/${t.id}`, { method: 'PATCH', headers: HEADERS, body: JSON.stringify({ action: 'complete' }) }).then(() => fetchInitialData())} className="w-5 h-5 text-gray-700 cursor-pointer" />
              </div>
            ))}
          </div>
        </Section>

        <div className="grid grid-cols-2 gap-4">
          <Card className="space-y-4">
            <div className="flex justify-between items-center">
              <Wallet className="w-5 h-5 text-emerald-500" />
              <div className="text-[8px] font-black uppercase text-gray-500 tracking-widest">Finanțe</div>
            </div>
            <p className="text-xl font-black">{finance?.balance || 0} Lei</p>
          </Card>
          
          <Card className="space-y-4">
            <div className="flex justify-between items-center">
              <Clock className="w-5 h-5 text-blue-500" />
              <div className="text-[8px] font-black uppercase text-gray-500 tracking-widest">Focus</div>
            </div>
            <p className="text-xl font-black">25:00</p>
          </Card>
        </div>

        <div className="grid grid-cols-4 gap-4 px-1">
          {[
            { id: 'map', icon: Navigation, label: 'Hartă' },
            { id: 'uni', icon: GraduationCap, label: 'Uni' },
            { id: 'gym', icon: Dumbbell, label: 'Sală' },
            { id: 'settings', icon: Settings, label: 'Setări' }
          ].map(m => (
            <button key={m.id} className="flex flex-col items-center gap-2">
              <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/10 flex items-center justify-center"><m.icon className="w-5 h-5 text-gray-600" /></div>
              <span className="text-[8px] font-black uppercase tracking-widest text-gray-500">{m.label}</span>
            </button>
          ))}
        </div>

      </div>

      <AnimatePresence>
        {isAddingTask && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/90 backdrop-blur-sm z-[2000] flex items-center justify-center p-6">
            <div className="w-full max-w-sm bg-[#111] border border-white/10 rounded-[32px] p-8 space-y-6">
               <h2 className="text-xl font-black uppercase tracking-widest">Task Nou</h2>
               <input autoFocus value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)} placeholder="Ce trebuie făcut?" className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 font-bold outline-none focus:border-blue-500" />
               <div className="flex gap-4">
                  <button onClick={() => setIsAddingTask(false)} className="flex-1 py-4 bg-white/5 rounded-2xl font-black text-gray-500 uppercase">Anulează</button>
                  <button onClick={handleAddTask} className="flex-1 py-4 bg-blue-500 rounded-2xl font-black uppercase">Salvează</button>
               </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
