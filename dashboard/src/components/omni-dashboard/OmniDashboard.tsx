"use client";

import React, { useState } from 'react';
import { GlobalIntelFeed } from './GlobalIntelFeed';
import { SessionClock } from './SessionClock';
import { TechnicalHub } from './TechnicalHub';
import { LayoutDashboard, Settings2, ChevronDown, ChevronUp, Bot, Activity } from 'lucide-react';
import { cn } from '../telemetry/utils';
import { motion, AnimatePresence } from 'framer-motion';

// Mock components that represent the previously built algorithmic modules
import { AiTelemetryHub } from '../telemetry/AiTelemetryHub';
import { SystemHealthMonitor } from '../system-health/SystemHealthMonitor';

export function OmniDashboard() {
  const [showBotControls, setShowBotControls] = useState(true);

  return (
    <div className="min-h-screen bg-[#020617] text-slate-200 font-sans antialiased selection:bg-indigo-500/30 selection:text-indigo-200">
      
      {/* Top Navbar / Header */}
      <header className="sticky top-0 z-50 bg-[#020617]/80 backdrop-blur-xl border-b border-slate-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
            <LayoutDashboard className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white drop-shadow-md">BullionHunter<span className="text-indigo-400 font-light">Omni</span></h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-[0.2em] uppercase">Hybrid Execution Dashboard</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
           {/* Algorithmic Toggle Button */}
           <button 
             onClick={() => setShowBotControls(!showBotControls)}
             className={cn(
               "flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-300 text-xs font-bold tracking-widest uppercase",
               showBotControls 
                 ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/30 shadow-[0_0_10px_rgba(99,102,241,0.1)]" 
                 : "bg-slate-900 text-slate-500 border-slate-800 hover:text-slate-300"
             )}
           >
             <Bot className="w-4 h-4" />
             Bot Engine
             {showBotControls ? <ChevronUp className="w-3 h-3 ml-1" /> : <ChevronDown className="w-3 h-3 ml-1" />}
           </button>
        </div>
      </header>

      <main className="p-6 max-w-[1600px] mx-auto space-y-6">
        
        {/* Session Clock (Full Width at Top) */}
        <SessionClock />

        {/* Collapsible Algorithmic Bot Controls */}
        <AnimatePresence initial={false}>
          {showBotControls && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.4, ease: [0.04, 0.62, 0.23, 0.98] }}
              className="overflow-hidden"
            >
              <div className="p-1 pb-6 space-y-6">
                 <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm font-bold text-white uppercase tracking-widest">Algorithmic Suite</h2>
                 </div>
                 {/* Mount the AI Telemetry Hub & System Health Monitor */}
                 <AiTelemetryHub />
                 <SystemHealthMonitor />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Divider if Bot Controls are open */}
        {showBotControls && (
          <div className="flex items-center gap-4 py-2">
             <div className="h-px bg-slate-800/80 flex-1" />
             <span className="text-[10px] text-slate-500 font-bold tracking-[0.2em] uppercase">Manual Intel Suite</span>
             <div className="h-px bg-slate-800/80 flex-1" />
          </div>
        )}

        {/* Manual Trading Research Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[800px]">
          
          {/* Left Column: Technical Analysis Hub */}
          <div className="lg:col-span-8 h-full">
            <TechnicalHub />
          </div>

          {/* Right Column: Global Intel Feed */}
          <div className="lg:col-span-4 h-full">
            <GlobalIntelFeed />
          </div>

        </div>

      </main>
    </div>
  );
}
