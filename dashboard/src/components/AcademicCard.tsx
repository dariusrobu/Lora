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
        <h3 className="label-ethereal">Program Azi</h3>
        <GraduationCap className="w-4 h-4 text-amber-400 opacity-30" />
      </div>

      <div className="space-y-3">
        {schedule?.length > 0 ? (
          schedule.map((s) => (
            <div key={s.id} className="liquid-panel p-4 flex gap-4 items-center hover:bg-white/[0.04] transition-all rounded-xl border-none">
              <div className="w-12 text-center">
                <p className="text-[10px] font-black text-amber-400 tabular-nums">{s.start_time.slice(0, 5)}</p>
                <Clock className="w-2 h-2 text-amber-400/20 mx-auto mt-1" />
              </div>
              <div className="flex-1">
                <p className="font-bold text-xs tracking-tight">{s.subject_name}</p>
                <p className="text-[8px] opacity-40 uppercase tracking-widest">{s.room}</p>
              </div>
              <Navigation className="w-3 h-3 text-gray-700" />
            </div>
          ))
        ) : (
          <div className="py-8 text-center liquid-panel border-dashed border-white/5 rounded-2xl bg-transparent">
            <p className="label-ethereal text-[8px] opacity-40">Liber azi</p>
            <p className="text-[8px] text-gray-600 font-bold mt-2 uppercase">Niciun curs detectat</p>
          </div>
        )}
      </div>
    </GlassCard>
  );
};
