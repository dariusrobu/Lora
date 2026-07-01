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
    pendingTasks.reduce((acc: Record<string, number>, t) => {
      const p = t.project_name || 'Altele';
      acc[p] = (acc[p] || 0) + 1;
      return acc;
    }, {})
  );

  return (
    <section className="space-y-6">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-widest ml-2 flex justify-between items-center">
        <span>Proiecte Active</span>
        <div className="flex items-center gap-2">
           <div className="w-1 h-1 rounded-full bg-border" />
           <span className="text-[9px] text-text-secondary uppercase tracking-widest">{pendingTasks.length} Priorități</span>
        </div>
      </h3>
      
      <div className="space-y-3">
        {projects.length > 0 ? (
          projects.map(([proj, count]: [string, number]) => (
            <GlassCard 
              key={proj} 
              className="p-4 flex justify-between items-center group cursor-pointer" 
              onClick={onClick}
            >
              <div className="flex items-center gap-4">
                 <div className="w-1 h-8 bg-surface rounded-full group-hover:scale-y-110 transition-transform" />
                 <div>
                    <p className="font-bold text-lg tracking-tight group-hover:text-text-primary transition-colors">{proj}</p>
                    <p className="text-[7px] text-text-muted mt-0.5">Sincronizat</p>
                 </div>
              </div>
              <div className="flex items-center gap-4">
                 <span className="text-2xl font-thin text-text-secondary">{count}</span>
                 <ArrowRight className="w-4 h-4 text-text-muted group-hover:translate-x-1 transition-transform" />
              </div>
            </GlassCard>
          ))
        ) : (
          <div className="py-16 text-center border border-dashed border-border rounded-[32px] bg-transparent">
             <CheckCircle2 className="w-12 h-12 text-text-muted mx-auto mb-4" />
             <p className="text-xs font-semibold text-text-secondary">Sistem Nominal</p>
             <p className="text-[9px] text-text-muted mt-2">Toate fluxurile de lucru sunt completate</p>
          </div>
        )}
      </div>
    </section>
  );
};
