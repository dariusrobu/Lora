import React from 'react';
import { GraduationCap, Navigation, Clock } from 'lucide-react';
import { GlassCard } from './GlassCard';

interface ScheduleItem {
  id: number;
  subject_name: string;
  room: string;
  start_time: string;
}

interface AcademicCardProps {
  schedule: ScheduleItem[];
  onClick?: () => void;
}

export const AcademicCard: React.FC<AcademicCardProps> = ({ schedule, onClick }) => {
  return (
    <GlassCard className="space-y-6" onClick={onClick}>
      <div className="flex justify-between items-center">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-widest">Program Azi</h3>
        <GraduationCap className="w-4 h-4 text-text-muted" />
      </div>

      <div className="space-y-3">
        {schedule?.length > 0 ? (
          schedule.map((s) => (
            <div key={s.id} className="p-4 flex gap-4 items-center hover:bg-white/[0.04] transition-all rounded-xl bg-white/[0.02]">
              <div className="w-12 text-center">
                <p className="text-[10px] font-black text-text-primary tabular-nums">{s.start_time.slice(0, 5)}</p>
                <Clock className="w-2 h-2 text-text-muted mx-auto mt-1" />
              </div>
              <div className="flex-1">
                <p className="font-bold text-xs tracking-tight">{s.subject_name}</p>
                <p className="text-[8px] opacity-40 uppercase tracking-widest">{s.room}</p>
              </div>
              <Navigation className="w-3 h-3 text-text-muted" />
            </div>
          ))
        ) : (
          <div className="py-8 text-center border border-dashed border-border rounded-2xl bg-transparent">
            <p className="text-xs text-text-muted">Liber azi</p>
            <p className="text-[8px] text-text-muted font-bold mt-2 uppercase">Niciun curs detectat</p>
          </div>
        )}
      </div>
    </GlassCard>
  );
};
