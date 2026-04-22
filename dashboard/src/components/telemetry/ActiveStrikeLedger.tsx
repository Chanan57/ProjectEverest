"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Crosshair, ArrowUpRight, ArrowDownRight, Shield, TrendingUp } from 'lucide-react';
import { cn } from './utils';

export interface TradeStrike {
  id: string;
  type: 'LONG' | 'SHORT';
  entryPrice: number;
  stopLoss: number;
  takeProfit: number;
  ruleTrigger: string;
  timestamp: Date;
}

interface ActiveStrikeLedgerProps {
  activeStrikes: TradeStrike[];
  className?: string;
}

export function ActiveStrikeLedger({ activeStrikes, className }: ActiveStrikeLedgerProps) {
  return (
    <div className={cn("flex flex-col h-full bg-slate-900/40 rounded-xl border border-slate-800/50 backdrop-blur-sm overflow-hidden", className)}>
      <div className="flex items-center px-6 py-4 border-b border-slate-800/50">
        <Crosshair className="w-5 h-5 text-indigo-400 mr-2" />
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">Active Strike Ledger</h3>
        <div className="ml-auto bg-indigo-500/10 text-indigo-400 text-xs font-bold px-2.5 py-1 rounded-full border border-indigo-500/20">
          {activeStrikes.length} ACTIVE
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        <AnimatePresence initial={false}>
          {activeStrikes.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center h-40 text-slate-500"
            >
              <Shield className="w-8 h-8 mb-3 opacity-20" />
              <p className="text-sm font-medium tracking-wide">NO ACTIVE STRIKES</p>
              <p className="text-xs mt-1 opacity-50">Monitoring for high-probability setups...</p>
            </motion.div>
          ) : (
            activeStrikes.map((strike) => {
              const isLong = strike.type === 'LONG';
              const themeColor = isLong ? 'emerald' : 'rose';

              return (
                <motion.div
                  key={strike.id}
                  initial={{ opacity: 0, y: -20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.2 } }}
                  layout
                  className={cn(
                    "relative p-5 rounded-lg border backdrop-blur-md overflow-hidden",
                    isLong 
                      ? "bg-emerald-500/5 border-emerald-500/20" 
                      : "bg-rose-500/5 border-rose-500/20"
                  )}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "p-1.5 rounded-md", 
                        isLong ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"
                      )}>
                        {isLong ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                      </div>
                      <div>
                        <span className={cn(
                          "text-sm font-bold tracking-widest",
                          isLong ? "text-emerald-400" : "text-rose-400"
                        )}>
                          {strike.type} XAUUSD
                        </span>
                        <p className="text-xs text-slate-400 font-mono mt-0.5">
                          {strike.timestamp.toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Entry Price</p>
                      <p className="text-lg font-black text-white font-mono tracking-tight">
                        {strike.entryPrice.toFixed(2)}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4 p-3 bg-slate-950/40 rounded-md border border-slate-800/50 shadow-inner">
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Stop Loss</p>
                      <p className="text-sm font-semibold text-rose-400 font-mono">{strike.stopLoss.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Take Profit</p>
                      <p className="text-sm font-semibold text-emerald-400 font-mono">{strike.takeProfit.toFixed(2)}</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 pt-3 border-t border-slate-800/50">
                    <TrendingUp className="w-3.5 h-3.5 text-indigo-400 mt-0.5" />
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">Trigger Rule</p>
                      <p className="text-xs text-slate-300 font-medium leading-relaxed mt-0.5">
                        {strike.ruleTrigger}
                      </p>
                    </div>
                  </div>
                  
                  {/* Subtle pulsing glow for active strike */}
                  <div className={cn(
                    "absolute -top-20 -right-20 w-40 h-40 blur-3xl opacity-10 rounded-full pointer-events-none",
                    isLong ? "bg-emerald-500" : "bg-rose-500"
                  )} />
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
