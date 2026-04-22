"use client";

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickData, Time } from 'lightweight-charts';
import { BarChart2, TrendingUp, Cpu, Activity, ArrowRight } from 'lucide-react';
import { cn } from '../telemetry/utils';

export function TechnicalHub({ className }: { className?: string }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.4)', style: 1 },
        horzLines: { color: 'rgba(30, 41, 59, 0.4)', style: 1 },
      },
      width: chartContainerRef.current.clientWidth,
      height: 320,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: 'rgba(30, 41, 59, 0.8)',
      },
      rightPriceScale: {
        borderColor: 'rgba(30, 41, 59, 0.8)',
      },
      crosshair: {
        vertLine: { color: '#64748b', labelBackgroundColor: '#1e293b' },
        horzLine: { color: '#64748b', labelBackgroundColor: '#1e293b' },
      }
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    });

    // Dummy XAUUSD Data
    const data: CandlestickData<Time>[] = [
      { time: '2026-04-15', open: 2330.1, high: 2335.5, low: 2325.2, close: 2332.8 },
      { time: '2026-04-16', open: 2332.8, high: 2340.0, low: 2330.5, close: 2338.2 },
      { time: '2026-04-17', open: 2338.2, high: 2345.5, low: 2335.0, close: 2342.1 },
      { time: '2026-04-18', open: 2342.1, high: 2350.0, low: 2340.2, close: 2348.5 },
      { time: '2026-04-19', open: 2348.5, high: 2355.2, low: 2345.0, close: 2350.8 },
      { time: '2026-04-20', open: 2350.8, high: 2352.0, low: 2342.5, close: 2345.3 },
      { time: '2026-04-21', open: 2345.3, high: 2358.5, low: 2344.0, close: 2356.9 },
      { time: '2026-04-22', open: 2356.9, high: 2362.0, low: 2355.5, close: 2360.2 },
    ];
    
    candlestickSeries.setData(data);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  return (
    <div className={cn("flex flex-col h-full bg-slate-900/60 rounded-xl border border-slate-800/80 backdrop-blur-md overflow-hidden", className)}>
      
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80 bg-slate-950/50">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-indigo-400" />
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Technical Hub (XAUUSD)</h3>
        </div>
        <div className="flex items-center gap-2">
           <span className="text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">D1</span>
           <span className="text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">H4</span>
           <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">M15</span>
        </div>
      </div>

      {/* Chart Container */}
      <div className="relative w-full h-[320px] bg-[#0a0f18]" ref={chartContainerRef}>
         {/* Live price overlay */}
         <div className="absolute top-4 left-4 z-10 flex items-baseline gap-2 pointer-events-none">
            <span className="text-2xl font-black font-mono text-emerald-400 drop-shadow-md">2360.20</span>
            <span className="text-xs font-bold text-emerald-500 flex items-center"><TrendingUp className="w-3 h-3 mr-0.5"/> +0.14%</span>
         </div>
      </div>

      {/* AI Technical Summary Panel */}
      <div className="flex-1 p-4 bg-slate-950/50 border-t border-slate-800/80">
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">AI Technical Summary</h4>
        </div>
        
        <div className="grid grid-cols-3 gap-4">
          {/* Trend */}
          <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-800/50">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Primary Trend</p>
            <div className="flex items-center gap-1.5 text-emerald-400">
               <TrendingUp className="w-4 h-4" />
               <span className="text-sm font-bold tracking-wide">BULLISH</span>
            </div>
          </div>
          
          {/* S/R Levels */}
          <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-800/50 flex flex-col justify-center">
             <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Resistance</span>
                <span className="text-xs font-mono font-bold text-rose-400">2365.00</span>
             </div>
             <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Support</span>
                <span className="text-xs font-mono font-bold text-emerald-400">2345.50</span>
             </div>
          </div>

          {/* RSI Status */}
          <div className="p-3 bg-slate-900/50 rounded-lg border border-slate-800/50">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">RSI (14)</p>
            <div className="flex items-center gap-2">
               <span className="text-lg font-black font-mono text-amber-400 tracking-tighter">68.5</span>
               <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500" style={{ width: '68.5%' }} />
               </div>
            </div>
            <p className="text-[9px] text-amber-500/80 uppercase font-bold mt-1 text-right tracking-widest">Approaching OB</p>
          </div>
        </div>
      </div>

    </div>
  );
}
