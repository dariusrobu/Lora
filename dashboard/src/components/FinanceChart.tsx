import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip, CartesianGrid } from 'recharts';
import { GlassCard } from './GlassCard';
import { Wallet, TrendingUp, TrendingDown } from 'lucide-react';
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

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("ro-RO", { style: "currency", currency: "RON", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
}

export const FinanceChart: React.FC<FinanceChartProps> = ({ summary, history, onClick }) => {
  const isDeficit = (summary?.balance ?? 0) < 0;
  const strokeColor = isDeficit ? "#F43F5E" : "#6366F1";
  const glowColor = isDeficit ? "rgba(244, 63, 94, 0.3)" : "rgba(99, 102, 241, 0.3)";

  // Format history for recharts
  const chartData = history.slice(0, 7).reverse().map((h: FinanceHistoryItem) => ({
    date: new Date(h.date).toLocaleDateString('ro-RO', { weekday: 'short' }),
    amount: h.amount
  }));

  return (
    <GlassCard className="group overflow-hidden relative" onClick={onClick}>
      <div className="flex justify-between items-start relative z-10 mb-5">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
            isDeficit 
              ? "bg-rose-500/15 text-rose-400 border border-rose-500/25 shadow-glow-rose" 
              : "bg-primary/15 text-primary border border-primary/25 shadow-glow-indigo"
          }`}>
            <Wallet className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className={`text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.2 rounded-md ${
                isDeficit 
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" 
                  : "bg-primary/10 text-primary border border-primary/20"
              }`}>
                {isDeficit ? "Deficit (Pe Minus)" : "Balanță Curentă"}
              </span>
            </div>
            <p className={`text-3xl sm:text-4xl font-black tracking-tight tabular-nums ${
              isDeficit ? "text-rose-400" : "text-white"
            }`}>
              {summary ? fmtCurrency(summary.balance) : "—"}
            </p>
          </div>
        </div>
        <div className={`p-2 rounded-xl border ${
          isDeficit 
            ? "bg-rose-500/10 text-rose-400 border-rose-500/20" 
            : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
        }`}>
          {isDeficit ? <TrendingDown className="w-4 h-4" /> : <TrendingUp className="w-4 h-4" />}
        </div>
      </div>

      <div className="h-56 sm:h-64 w-full mt-3">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={strokeColor} stopOpacity={0.35} />
                <stop offset="95%" stopColor={strokeColor} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis 
              dataKey="date" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10, fontWeight: 500 }}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'rgba(12, 12, 20, 0.94)', 
                backdropFilter: 'blur(16px)',
                border: '1px solid rgba(255,255,255,0.08)', 
                borderRadius: '12px', 
                fontSize: '11px',
                color: '#fff',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              }}
              formatter={(val: any) => [`${val ?? 0} lei`, 'Cheltuit']}
            />
            <Area 
              type="monotone" 
              dataKey="amount" 
              stroke={strokeColor} 
              fillOpacity={1} 
              fill="url(#colorAmount)" 
              strokeWidth={1.8}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassCard>
  );
};
