import React from 'react';
import { CheckCircle2, ArrowRight } from 'lucide-react';
import { GlassCard } from './GlassCard';

interface Task {
  id: number;
  title: string;
  status: string;
  project_name?: string;
}

interface TaskSectionProps {
  tasks: Task[];
  onClick?: () => void;
}

export const TaskSection: React.FC<TaskSectionProps> = ({ tasks, onClick }) => {
  const pendingTasks = tasks.filter(t => t.status !== 'done');
  
  const projects = Object.entries(
    pendingTasks.reduce((acc: any, t) => {
      const p = t.project_name || 'Altele';
      acc[p] = (acc[p] || 0) + 1;
      return acc;
    }, {})
  );

  return (
    <section className="space-y-6">
      <h3 className="label-ethereal ml-2 flex justify-between items-center">
        <span>Proiecte Active</span>
        <div className="flex items-center gap-2">
           <div className="w-1 h-1 rounded-full bg-blue-400" />
           <span className="text-[9px] text-gray-500 uppercase tracking-widest">{pendingTasks.length} Priorități</span>
        </div>
      </h3>
      
      <div className="space-y-3">
        {projects.length > 0 ? (
          projects.map(([proj, count]: [string, any]) => (
            <GlassCard 
              key={proj} 
              className="p-4 flex justify-between items-center group cursor-pointer" 
              onClick={onClick}
            >
              <div className="flex items-center gap-4">
                 <div className="w-1 h-8 bg-blue-500 rounded-full group-hover:scale-y-110 transition-transform shadow-[0_0_15px_rgba(59,130,246,0.5)]" />
                 <div>
                    <p className="font-bold text-lg tracking-tight group-hover:text-blue-400 transition-colors">{proj}</p>
                    <p className="label-ethereal text-[7px] opacity-30 mt-0.5">Sincronizat</p>
                 </div>
              </div>
              <div className="flex items-center gap-4">
                 <span className="text-2xl font-thin text-blue-200">{count}</span>
                 <ArrowRight className="w-4 h-4 text-gray-700 group-hover:translate-x-1 transition-transform" />
              </div>
            </GlassCard>
          ))
        ) : (
          <div className="py-16 text-center liquid-panel border-dashed border-white/10 rounded-[32px] bg-transparent">
             <CheckCircle2 className="w-12 h-12 text-emerald-500/10 mx-auto mb-4" />
             <p className="label-ethereal text-emerald-400">Sistem Nominal</p>
             <p className="text-[9px] text-gray-600 mt-2">Toate fluxurile de lucru sunt completate</p>
          </div>
        )}
      </div>
    </section>
  );
};
