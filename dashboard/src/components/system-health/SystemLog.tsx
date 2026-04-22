"use client";

import React, { useRef, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { TerminalSquare } from 'lucide-react';
import { cn } from '../telemetry/utils';

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  message: string;
}

interface SystemLogProps {
  logs: LogEntry[];
  className?: string;
}

export function SystemLog({ logs, className }: SystemLogProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // The virtualizer calculates which items to render
  const rowVirtualizer = useVirtualizer({
    count: logs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 24, // Estimated row height in px
    overscan: 20, // Render items outside of the viewport to prevent tearing
  });

  // Auto-scroll to bottom when new logs arrive, but only if we're near the bottom
  useEffect(() => {
    if (logs.length > 0) {
      // Small timeout to let rendering catch up
      setTimeout(() => {
        rowVirtualizer.scrollToIndex(logs.length - 1, { align: 'end' });
      }, 0);
    }
  }, [logs.length, rowVirtualizer]);

  const getLogColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'INFO': return 'text-slate-300';
      case 'WARN': return 'text-amber-400';
      case 'ERROR': return 'text-rose-400 font-semibold bg-rose-500/10 px-1 rounded-sm';
      case 'SUCCESS': return 'text-emerald-400';
      default: return 'text-slate-300';
    }
  };

  return (
    <div className={cn("flex flex-col h-full bg-slate-950 rounded-xl border border-slate-800 shadow-2xl overflow-hidden", className)}>
      <div className="flex items-center px-4 py-3 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md">
        <TerminalSquare className="w-4 h-4 text-indigo-400 mr-2" />
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Raw System Log</h3>
        <div className="ml-auto text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20 tracking-wider">
          {logs.length.toLocaleString()} EVENTS
        </div>
      </div>
      
      <div 
        ref={parentRef}
        className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent bg-[#0a0f18]/80"
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualItem) => {
            const log = logs[virtualItem.index];
            if (!log) return null;
            return (
              <div
                key={virtualItem.key}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualItem.size}px`,
                  transform: `translateY(${virtualItem.start}px)`,
                }}
                className="flex items-center px-4 font-mono text-[11px] hover:bg-white/[0.03] transition-colors"
              >
                <span className="text-slate-600 mr-3 shrink-0">
                  [{log.timestamp.toISOString().substring(11, 23)}]
                </span>
                <span className={cn("font-bold w-14 shrink-0", getLogColor(log.level))}>
                  {log.level}
                </span>
                <span className={cn("truncate", getLogColor(log.level))}>
                  {log.message}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
