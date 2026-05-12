import React from 'react';
import { Moon, Droplets, Scale, Cigarette, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { GlassCard } from './GlassCard';

interface HealthLog {
  log_date: string;
  sleep_hours: number | null;
  water_ml: number | null;
  weight_kg: number | null;
  cigarettes: number | null;
}

interface HealthCardProps {
  logs: HealthLog[];
  onClick?: () => void;
}

export const HealthCard: React.FC<HealthCardProps> = ({ logs, onClick }) => {
  const latest = logs[0] || {};
  const prev = logs[1] || {};

  const getTrend = (curr: number | null, p: number | null) => {
    if (curr === null || p === null) return <Minus className="w-3 h-3 opacity-20" />;
    if (curr > p) return <TrendingUp className="w-3 h-3 text-red-400" />;
    if (curr < p) return <TrendingDown className="w-3 h-3 text-emerald-400" />;
    return <Minus className="w-3 h-3 opacity-20" />;
  };

  return (
    <GlassCard className="group relative overflow-hidden" onClick={onClick}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl -mr-16 -mt-16 group-hover:bg-blue-500/10 transition-all" />
      
      <div className="flex justify-between items-start mb-6">
        <h3 className="label-ethereal">Status Vital</h3>
        <div className="flex gap-1">
          <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[8px] text-emerald-500/50 uppercase font-black">Live</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Sleep */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <Moon className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">Somn</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black">{latest.sleep_hours || '—'}<span className="text-[10px] opacity-30 ml-1">h</span></p>
                {getTrend(latest.sleep_hours, prev.sleep_hours)}
              </div>
            </div>
          </div>
        </div>

        {/* Water */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Droplets className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">Apă</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black">{latest.water_ml || 0}<span className="text-[10px] opacity-30 ml-1">ml</span></p>
              </div>
            </div>
          </div>
        </div>

        {/* Weight */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Scale className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">Greutate</p>
              <div className="flex items-center gap-2">
                <p className="text-xl font-black">{latest.weight_kg || '—'}<span className="text-[10px] opacity-30 ml-1">kg</span></p>
                {getTrend(latest.weight_kg, prev.weight_kg)}
              </div>
            </div>
          </div>
        </div>

        {/* Cigarettes */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Cigarette className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">Țigări</p>
              <div className="flex items-center gap-2">
                <p className={`text-xl font-black ${(latest.cigarettes || 0) > 10 ? 'text-red-400' : ''}`}>
                  {latest.cigarettes || 0}
                </p>
                {getTrend(latest.cigarettes, prev.cigarettes)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </GlassCard>
  );
};
