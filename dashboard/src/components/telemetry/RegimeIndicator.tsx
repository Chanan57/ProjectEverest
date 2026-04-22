"use client";

import React from 'react';
import { Activity } from 'lucide-react';
import { cn } from './utils';
import { motion } from 'framer-motion';

export type RegimeType = 'Trending' | 'Ranging' | 'High Volatility Breakout';

interface RegimeIndicatorProps {
  currentRegime: RegimeType;
  className?: string;
}

export function RegimeIndicator({ currentRegime, className }: RegimeIndicatorProps) {
  const regimes: { id: RegimeType; label: string; activeColor: string }[] = [
    { id: 'Trending', label: 'Trending', activeColor: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.2)]' },
    { id: 'Ranging', label: 'Ranging', activeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.2)]' },
    { id: 'High Volatility Breakout', label: 'Volatility Breakout', activeColor: 'bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-[0_0_15px_rgba(244,63,94,0.2)]' },
  ];

  return (
    <div className={cn("flex flex-col p-6 bg-slate-900/40 rounded-xl border border-slate-800/50 backdrop-blur-sm", className)}>
      <div className="flex items-center gap-2 mb-6 text-slate-300">
        <Activity className="w-5 h-5" />
        <h3 className="text-sm font-semibold uppercase tracking-wider">Market Regime</h3>
      </div>

      <div className="flex flex-col gap-3">
        {regimes.map((regime) => {
          const isActive = currentRegime === regime.id;
          return (
            <div
              key={regime.id}
              className={cn(
                "relative px-4 py-3 rounded-lg border transition-all duration-500 flex items-center justify-between overflow-hidden",
                isActive 
                  ? regime.activeColor 
                  : "bg-slate-950/50 text-slate-500 border-slate-800/80"
              )}
            >
              {isActive && (
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent z-0"
                  initial={{ x: '-100%' }}
                  animate={{ x: '200%' }}
                  transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                />
              )}
              <span className="relative z-10 font-medium tracking-wide">{regime.label}</span>
              {isActive && (
                <span className="relative z-10 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-current"></span>
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
