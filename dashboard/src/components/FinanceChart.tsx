import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip, CartesianGrid } from 'recharts';
import { GlassCard } from './GlassCard';
import { Wallet, TrendingUp } from 'lucide-react';
import type { FinanceSummary } from '../types';

interface FinanceHistoryItem {
  date: string;
  amount: number;
}

interface FinanceChartProps {
  summary: FinanceSummary | null;
  history: FinanceHistoryItem[];
  onClick?: () => void;
}

export const FinanceChart: React.FC<FinanceChartProps> = ({ summary, history, onClick }) => {
  // Format history for recharts
  const chartData = history.slice(0, 7).reverse().map((h: FinanceHistoryItem) => ({
    date: new Date(h.date).toLocaleDateString('ro-RO', { weekday: 'short' }),
    amount: h.amount
  }));

  return (
    <GlassCard className="group overflow-hidden relative" onClick={onClick}>
      <div className="flex justify-between items-start relative z-10 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-surface flex items-center justify-center">
            <Wallet className="w-5 h-5 text-text-secondary" />
          </div>
          <div>
            <p className="text-[8px] text-text-secondary uppercase tracking-widest font-semibold">Balanță Curentă</p>
            <p className="text-2xl font-black tracking-tighter tabular-nums text-text-primary">
              {summary?.balance ?? 0} <span className="text-[10px] font-bold opacity-30 uppercase">Lei</span>
            </p>
          </div>
        </div>
        <TrendingUp className="w-4 h-4 text-text-muted" />
      </div>

      <div className="h-32 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffffff" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#ffffff" stopOpacity={0}/>
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
              contentStyle={{ backgroundColor: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '10px' }}
              itemStyle={{ color: '#fff' }}
            />
            <Area 
              type="monotone" 
              dataKey="amount" 
              stroke="rgba(255,255,255,0.4)" 
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
