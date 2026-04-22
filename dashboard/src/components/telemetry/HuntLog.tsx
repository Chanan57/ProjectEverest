"use client";

import React, { useEffect, useRef, useDeferredValue } from 'react';
import ReactMarkdown from 'react-markdown';
import { Terminal } from 'lucide-react';
import { cn } from './utils';

interface HuntLogProps {
  streamedText: string;
  className?: string;
}

export function HuntLog({ streamedText, className }: HuntLogProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // useDeferredValue keeps the UI responsive during high-frequency streaming
  const deferredText = useDeferredValue(streamedText);

  // Auto-scroll to the bottom whenever deferred text changes
  useEffect(() => {
    if (containerRef.current) {
      const scrollElement = containerRef.current;
      scrollElement.scrollTo({
        top: scrollElement.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [deferredText]);

  return (
    <div className={cn("flex flex-col h-full bg-slate-950 rounded-xl border border-slate-800 shadow-2xl overflow-hidden", className)}>
      <div className="flex items-center px-4 py-3 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md">
        <Terminal className="w-5 h-5 text-emerald-400 mr-2" />
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">Hunt Log - Brain Feed</h3>
        <div className="ml-auto flex gap-1.5 items-center">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs text-slate-400 font-mono">LIVE</span>
        </div>
      </div>
      
      <div 
        ref={containerRef}
        className="flex-1 p-4 overflow-y-auto font-mono text-sm leading-relaxed scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent"
      >
        <article className="prose prose-invert prose-sm max-w-none prose-p:text-emerald-50/80 prose-headings:text-emerald-400 prose-strong:text-emerald-300">
          <ReactMarkdown>
            {deferredText || "Awaiting LLM reasoning stream..."}
          </ReactMarkdown>
          {/* Pulsing cursor to show it's "thinking" */}
          {streamedText && (
            <span className="inline-block w-2 h-4 ml-1 align-middle bg-emerald-400 animate-pulse" />
          )}
        </article>
      </div>
    </div>
  );
}
