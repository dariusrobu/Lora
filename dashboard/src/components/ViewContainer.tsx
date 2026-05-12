import React from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';

interface ViewContainerProps {
  children: React.ReactNode;
  title: string;
  onBack: () => void;
}

export const ViewContainer: React.FC<ViewContainerProps> = ({ children, title, onBack }) => (
  <motion.div 
    initial={{ opacity: 0, scale: 0.98 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 1.02 }}
    className="fixed inset-0 bg-[#030303] z-[100] p-6 lg:p-16 overflow-y-auto no-scrollbar"
  >
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-8 sm:mb-12">
        <button 
          onClick={onBack} 
          className="w-10 h-10 sm:w-12 sm:h-12 rounded-full liquid-panel flex items-center justify-center hover:bg-white/10 transition-all hover:scale-110 active:scale-90"
        >
          <ArrowLeft className="w-5 h-5 text-blue-400" />
        </button>
        <h2 className="label-ethereal kinetic-text text-xs sm:text-sm">{title}</h2>
        <div className="w-10 sm:w-12" />
      </div>
      {children}
    </div>
  </motion.div>
);
