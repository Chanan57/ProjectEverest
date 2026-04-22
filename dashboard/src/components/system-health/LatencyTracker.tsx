"use client";

import React, { useMemo } from 'react';
import { Activity, AlertTriangle } from 'lucide-react';
import { cn } from '../telemetry/utils';

interface LatencyTrackerProps {
  currentLatencyMs: number;
  history: number[]; // Array of recent latency values for sparkline
  thresholdMs?: number;
  className?: string;
}

export function LatencyTracker({ currentLatencyMs, history, thresholdMs = 200, className }: LatencyTrackerProps) {
  const isWarning = currentLatencyMs > thresholdMs;

  // Generate SVG path for sparkline
  const sparklinePath = useMemo(() => {
    if (history.length < 2) return '';
    const maxVal = Math.max(...history, thresholdMs * 1.5); // ensure threshold fits visually
    const minVal = 0;
    const range = maxVal - minVal || 1;
    
    const width = 100; // viewbox width
    const height = 40; // viewbox height
    
    const points = history.map((val, i) => {
      const x = (i / (history.length - 1)) * width;
      const y = height - ((val - minVal) / range) * height;
      return `${x},${y}`;
    });
    
    return `M ${points.join(' L ')}`;
  }, [history, thresholdMs]);

  // Calculate threshold line Y position
  const thresholdY = useMemo(() => {
    if (history.length < 2) return 0;
    const maxVal = Math.max(...history, thresholdMs * 1.5);
    return 40 - (thresholdMs / maxVal) * 40;
  }, [history, thresholdMs]);

  return (
    <div className={cn(
      "relative p-4 rounded-xl border backdrop-blur-sm overflow-hidden transition-colors duration-300",
      isWarning 
        ? "bg-rose-950/40 border-rose-500/50 shadow-[0_0_20px_rgba(244,63,94,0.1)]" 
        : "bg-slate-900/40 border-slate-800/50",
      className
    )}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Activity className={cn("w-4 h-4", isWarning ? "text-rose-400" : "text-indigo-400")} />
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-widest">XAUUSD Latency</h3>
        </div>
        {isWarning && (
          <div className="flex items-center gap-1 text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider animate-pulse border border-rose-500/20 shadow-[0_0_10px_rgba(244,63,94,0.2)]">
            <AlertTriangle className="w-3 h-3" />
            SPIKE
          </div>
        )}
      </div>

      <div className="flex items-end gap-6 mt-4">
        <div className="flex-shrink-0">
          <div className="flex items-baseline gap-1">
            <span className={cn(
              "text-4xl font-black font-mono tracking-tighter",
              isWarning ? "text-rose-400" : "text-emerald-400"
            )}>
              {currentLatencyMs}
            </span>
            <span className="text-xs text-slate-500 font-mono font-bold">ms</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-1 font-mono">Limit: {thresholdMs}ms</div>
        </div>
        
        {/* Sparkline Container */}
        <div className="flex-1 h-14 w-full">
          <svg className="w-full h-full overflow-visible" viewBox="0 0 100 40" preserveAspectRatio="none">
            {/* Threshold Line */}
            {history.length >= 2 && (
              <line 
                x1="0" y1={thresholdY} 
                x2="100" y2={thresholdY} 
                stroke="rgba(244,63,94,0.5)" strokeWidth="1" strokeDasharray="2 2" 
              />
            )}
            {/* Data Line */}
            <path
              d={sparklinePath}
              fill="none"
              stroke={isWarning ? "rgb(244,63,94)" : "rgb(16,185,129)"}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
            {/* Latest point dot */}
            {history.length >= 2 && (
               <circle 
                  cx="100" 
                  cy={40 - ((history[history.length - 1] - 0) / (Math.max(...history, thresholdMs * 1.5) || 1)) * 40} 
                  r="2" 
                  fill={isWarning ? "rgb(244,63,94)" : "rgb(16,185,129)"} 
               />
            )}
          </svg>
        </div>
      </div>
      
      {/* Warning Overlay pulse */}
      {isWarning && (
        <div className="absolute inset-0 bg-rose-500/5 mix-blend-overlay animate-pulse pointer-events-none" />
      )}
    </div>
  );
}
