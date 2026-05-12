import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip, CartesianGrid } from 'recharts';
import { GlassCard } from './GlassCard';
import { Wallet, TrendingUp } from 'lucide-react';

interface FinanceChartProps {
  summary: any;
  history: any[];
  onClick?: () => void;
}

export const FinanceChart: React.FC<FinanceChartProps> = ({ summary, history, onClick }) => {
  // Format history for recharts
  const chartData = history.slice(0, 7).reverse().map(h => ({
    date: new Date(h.date).toLocaleDateString('ro-RO', { weekday: 'short' }),
    amount: h.amount
  }));

  return (
    <GlassCard className="group overflow-hidden relative" onClick={onClick}>
      <div className="absolute inset-0 bg-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
      
      <div className="flex justify-between items-start relative z-10 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
            <Wallet className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="label-ethereal text-[8px]">Balanță Curentă</p>
            <p className="text-2xl font-black tracking-tighter tabular-nums text-emerald-400">
              {summary?.balance || 0} <span className="text-[10px] font-bold opacity-30 uppercase">Lei</span>
            </p>
          </div>
        </div>
        <TrendingUp className="w-4 h-4 text-emerald-500/30 group-hover:text-emerald-400 transition-colors" />
      </div>

      <div className="h-32 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis 
              dataKey="date" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 10 }}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', fontSize: '10px' }}
              itemStyle={{ color: '#10b981' }}
            />
            <Area 
              type="monotone" 
              dataKey="amount" 
              stroke="#10b981" 
              fillOpacity={1} 
              fill="url(#colorAmount)" 
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  );
};
