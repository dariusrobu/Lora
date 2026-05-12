import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface DynamicIslandProps {
  active: boolean;
  message: string;
  icon: any;
}

export const DynamicIsland: React.FC<DynamicIslandProps> = ({ active, message, icon: Icon }) => (
  <AnimatePresence>
    {active && (
      <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[2000] pointer-events-none">
        <motion.div 
          initial={{ width: 120, height: 36, borderRadius: 100, opacity: 0, y: -20 }}
          animate={{ width: 'auto', height: 48, borderRadius: 24, opacity: 1, y: 0 }}
          exit={{ width: 80, height: 20, borderRadius: 100, opacity: 0, y: -20 }}
          className="bg-black/90 backdrop-blur-3xl border border-white/10 flex items-center gap-4 px-6 py-2 shadow-2xl overflow-hidden min-w-[200px]"
        >
          {Icon && <Icon className="w-4 h-4 text-blue-300 animate-pulse" />}
          <span className="text-[10px] font-black uppercase tracking-widest text-white whitespace-nowrap kinetic-text">{message}</span>
        </motion.div>
      </div>
    )}
  </AnimatePresence>
);
