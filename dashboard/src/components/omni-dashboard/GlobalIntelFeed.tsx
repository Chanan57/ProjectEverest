"use client";

import React, { useState } from 'react';
import { Newspaper, MessageCircle, BrainCircuit, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '../telemetry/utils';
import { motion, AnimatePresence } from 'framer-motion';

export function GlobalIntelFeed({ className }: { className?: string }) {
  const [activeTab, setActiveTab] = useState<'NEWS' | 'SOCIAL'>('NEWS');

  // Dummy data
  const news = [
    { id: 1, source: 'Reuters', time: '10m ago', title: 'Fed Chair Powell signals potential pause in rate hikes next month.', impact: 'HIGH' },
    { id: 2, source: 'Bloomberg', time: '45m ago', title: 'US Retail Sales unexpectedly drop, signaling cooling consumer demand.', impact: 'MED' },
    { id: 3, source: 'WSJ', time: '1h ago', title: 'Gold surges past $2350 as geopolitical tensions escalate in the Middle East.', impact: 'HIGH' },
    { id: 4, source: 'Financial Times', time: '2h ago', title: 'Central banks continue aggressive gold purchasing strategy.', impact: 'HIGH' },
  ];

  const social = [
    { id: 1, source: 'X / @GoldMacro', time: '5m ago', text: 'Massive order block spotted at 2345. If we break this, 2360 is next. 🚀' },
    { id: 2, source: 'Reddit / r/Daytrading', time: '12m ago', text: 'Anyone else getting chopped up in this gold range? Waiting for London open.' },
    { id: 3, source: 'X / @FX_Whale', time: '22m ago', text: 'Adding to my XAUUSD longs here. Yields are dropping.' },
    { id: 4, source: 'X / @MacroTrader', time: '30m ago', text: 'DXY is looking incredibly weak today. Tailwind for precious metals.' },
  ];

  return (
    <div className={cn("flex flex-col h-full bg-slate-900/60 rounded-xl border border-slate-800/80 backdrop-blur-md overflow-hidden", className)}>
      
      {/* Header Tabs */}
      <div className="flex items-center border-b border-slate-800/80 bg-slate-950/50">
        <button 
          onClick={() => setActiveTab('NEWS')}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 text-xs font-bold tracking-widest uppercase transition-colors relative",
            activeTab === 'NEWS' ? "text-indigo-400" : "text-slate-500 hover:text-slate-300"
          )}
        >
          <Newspaper className="w-4 h-4" /> Top News
          {activeTab === 'NEWS' && <motion.div layoutId="intelTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
        </button>
        <div className="w-px h-6 bg-slate-800" />
        <button 
          onClick={() => setActiveTab('SOCIAL')}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 text-xs font-bold tracking-widest uppercase transition-colors relative",
            activeTab === 'SOCIAL' ? "text-indigo-400" : "text-slate-500 hover:text-slate-300"
          )}
        >
          <MessageCircle className="w-4 h-4" /> Social Chatter
          {activeTab === 'SOCIAL' && <motion.div layoutId="intelTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />}
        </button>
      </div>

      {/* AI Sentiment Summary Banner */}
      <div className="bg-gradient-to-r from-emerald-500/10 to-transparent border-b border-emerald-500/20 p-3 flex items-start gap-3 shrink-0">
        <div className="p-1.5 bg-emerald-500/20 rounded-md border border-emerald-500/30 text-emerald-400">
          <TrendingUp className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <BrainCircuit className="w-3 h-3 text-emerald-400" />
            <h4 className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">AI Sentiment: Bullish (78%)</h4>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Macro news strongly favors upside due to dropping yields and geopolitical risks. Retail sentiment on social aligns with buying the dip.
          </p>
        </div>
      </div>

      {/* Masonry / Feed List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        <AnimatePresence mode="wait">
          {activeTab === 'NEWS' ? (
            <motion.div
              key="news"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-3"
            >
              {news.map((item) => (
                <div key={item.id} className="p-3 bg-slate-950/50 border border-slate-800/80 rounded-lg hover:border-slate-700 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-indigo-400 tracking-wider uppercase">{item.source}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{item.time}</span>
                  </div>
                  <p className="text-sm text-slate-200 font-medium leading-snug mb-2">{item.title}</p>
                  <div className="flex items-center gap-1">
                    <span className={cn(
                      "text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded border",
                      item.impact === 'HIGH' ? "bg-rose-500/10 text-rose-400 border-rose-500/20" : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    )}>
                      {item.impact} IMPACT
                    </span>
                  </div>
                </div>
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="social"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-3"
            >
              {social.map((item) => (
                <div key={item.id} className="p-3 bg-slate-950/50 border border-slate-800/80 rounded-lg hover:border-slate-700 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-sky-400 tracking-wider uppercase">{item.source}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{item.time}</span>
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed">{item.text}</p>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
