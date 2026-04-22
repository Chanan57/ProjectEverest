"use client";

import React, { useState, useEffect } from 'react';
import { Clock, Globe } from 'lucide-react';
import { cn } from '../telemetry/utils';

interface Session {
  name: string;
  start: number; // UTC hour 0-23
  end: number;
  color: string;
}

const SESSIONS: Session[] = [
  { name: 'Sydney', start: 22, end: 7, color: 'bg-indigo-500' },
  { name: 'Tokyo', start: 0, end: 9, color: 'bg-blue-500' },
  { name: 'London', start: 8, end: 16, color: 'bg-emerald-500' },
  { name: 'New York', start: 13, end: 22, color: 'bg-rose-500' },
];

export function SessionClock({ className }: { className?: string }) {
  const [utcHour, setUtcHour] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const updateTime = () => {
      const now = new Date();
      setUtcHour(now.getUTCHours() + now.getUTCMinutes() / 60);
    };
    updateTime();
    const interval = setInterval(updateTime, 60000); 
    return () => clearInterval(interval);
  }, []);

  const isOverlap = (hour: number) => {
    // London/NY overlap is approx 13:00 - 16:00 UTC, highest volume for XAUUSD
    return hour >= 13 && hour <= 16;
  };

  const currentOverlap = isOverlap(utcHour);

  if (!mounted) return null; // Prevent hydration mismatch

  return (
    <div className={cn("p-4 bg-slate-900/60 rounded-xl border border-slate-800/80 backdrop-blur-md", className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-slate-400" />
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Global Sessions (UTC)</h3>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
             <Clock className="w-3.5 h-3.5 text-indigo-400" />
             <span className="text-sm font-mono font-bold text-slate-200">
                {Math.floor(utcHour).toString().padStart(2, '0')}:{Math.floor((utcHour % 1) * 60).toString().padStart(2, '0')}
             </span>
          </div>
          {currentOverlap && (
             <span className="text-[10px] font-bold tracking-widest uppercase bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded border border-rose-500/30 animate-pulse">
                Volatile Overlap
             </span>
          )}
        </div>
      </div>

      <div className="relative h-12 w-full bg-slate-950/50 rounded-lg overflow-hidden border border-slate-800/50">
        {/* Timeline markers */}
        <div className="absolute inset-0 flex justify-between px-2 items-center opacity-30 pointer-events-none">
          {[0, 4, 8, 12, 16, 20, 24].map((h) => (
             <div key={h} className="h-full border-l border-slate-700 relative">
               <span className="absolute -bottom-1 -translate-x-1/2 text-[9px] text-slate-400 font-mono">{h}h</span>
             </div>
          ))}
        </div>

        {/* Sessions Blocks */}
        {SESSIONS.map((s, i) => {
           let blocks = [];
           if (s.start > s.end) {
              // Wrap around midnight
              blocks.push({ left: `${(s.start/24)*100}%`, width: `${((24-s.start)/24)*100}%` });
              blocks.push({ left: `0%`, width: `${(s.end/24)*100}%` });
           } else {
              blocks.push({ left: `${(s.start/24)*100}%`, width: `${((s.end-s.start)/24)*100}%` });
           }

           return blocks.map((b, idx) => (
              <div 
                key={`${s.name}-${idx}`}
                className={cn("absolute top-1 bottom-1 rounded-md opacity-25 border-t border-white/10 transition-all", s.color)}
                style={b}
              >
                {idx === 0 && <span className="absolute top-1 left-2 text-[9px] font-bold tracking-wider text-white opacity-90 drop-shadow-md">{s.name}</span>}
              </div>
           ));
        })}

        {/* Current Time Indicator */}
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-white z-10 shadow-[0_0_8px_rgba(255,255,255,0.8)] transition-all duration-1000"
          style={{ left: `${(utcHour / 24) * 100}%` }}
        >
          <div className="absolute -top-1 -translate-x-1/2 w-2 h-2 rounded-full bg-white shadow-[0_0_10px_rgba(255,255,255,1)]" />
        </div>
      </div>
    </div>
  );
}
