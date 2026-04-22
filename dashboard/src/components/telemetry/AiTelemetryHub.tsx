"use client";

import React, { useState, useEffect } from 'react';
import { HuntLog } from './HuntLog';
import { ConvictionGauge } from './ConvictionGauge';
import { RegimeIndicator, RegimeType } from './RegimeIndicator';
import { ActiveStrikeLedger, TradeStrike } from './ActiveStrikeLedger';
import { BrainCircuit } from 'lucide-react';

// Dummy data generator for testing the UI
const DUMMY_STRIKES: TradeStrike[] = [
  {
    id: '1',
    type: 'SHORT',
    entryPrice: 2350.50,
    stopLoss: 2355.00,
    takeProfit: 2340.00,
    ruleTrigger: 'RSI overbought + Heavy Resistance + Bearish Engulfing',
    timestamp: new Date(),
  }
];

const DUMMY_MARKDOWN_STREAM = [
  "### Analyzing XAUUSD Market Structure\n\n",
  "**Current Price:** 2349.80\n",
  "**Trend:** Approaching heavy resistance zone.\n\n",
  "> RSI (14) is currently reading 78.5, indicating extremely overbought conditions on the 1H timeframe.\n\n",
  "Checking order block alignment...\n",
  "- H4 Order Block: Bearish\n",
  "- M15 Structure: Shifted bearish\n\n",
  "**Conclusion:** *High probability for reversal. Initiating short criteria check.*"
];

export function AiTelemetryHub() {
  const [streamedText, setStreamedText] = useState("");
  const [convictionScore, setConvictionScore] = useState(85);
  const [currentRegime, setCurrentRegime] = useState<RegimeType>('High Volatility Breakout');
  const [activeStrikes, setActiveStrikes] = useState<TradeStrike[]>([]);

  // Simulation of websocket streaming and data updates
  useEffect(() => {
    let currentText = "";
    let chunkIndex = 0;
    
    const interval = setInterval(() => {
      if (chunkIndex < DUMMY_MARKDOWN_STREAM.length) {
        currentText += DUMMY_MARKDOWN_STREAM[chunkIndex];
        setStreamedText(currentText);
        chunkIndex++;
      } else {
        // Once text is done, show the active strike
        if (activeStrikes.length === 0) {
          setActiveStrikes(DUMMY_STRIKES);
        }
        clearInterval(interval);
      }
    }, 800);

    // Randomly fluctuate conviction score
    const scoreInterval = setInterval(() => {
      setConvictionScore(prev => {
        const fluctuation = Math.floor(Math.random() * 5) - 2;
        return Math.min(Math.max(prev + fluctuation, 0), 100);
      });
    }, 2000);

    return () => {
      clearInterval(interval);
      clearInterval(scoreInterval);
    };
  }, [activeStrikes.length]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <header className="flex items-center justify-between pb-4 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20">
              <BrainCircuit className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tight text-white">BullionHunter<span className="text-indigo-400">XAUUSD</span></h1>
              <p className="text-xs text-slate-400 font-medium tracking-widest uppercase">AI Telemetry & Reasoning Hub</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end">
              <span className="text-xs text-slate-500 uppercase font-bold tracking-wider">System Status</span>
              <span className="text-sm text-emerald-400 font-mono font-semibold">ONLINE & HUNTING</span>
            </div>
            <div className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </div>
          </div>
        </header>

        {/* Main Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-140px)] min-h-[600px]">
          
          {/* Left Column: Hunt Log (Takes up more space) */}
          <div className="lg:col-span-8 h-full">
            <HuntLog streamedText={streamedText} />
          </div>

          {/* Right Column: Gauges and Ledger */}
          <div className="lg:col-span-4 flex flex-col gap-6 h-full">
            
            {/* Top Right: Conviction & Regime */}
            <div className="grid grid-cols-2 gap-4 shrink-0">
              <ConvictionGauge score={convictionScore} className="h-full" />
              <RegimeIndicator currentRegime={currentRegime} className="h-full" />
            </div>

            {/* Bottom Right: Active Strike Ledger */}
            <div className="flex-1 min-h-[300px]">
              <ActiveStrikeLedger activeStrikes={activeStrikes} />
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
