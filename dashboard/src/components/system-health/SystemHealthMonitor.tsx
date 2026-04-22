"use client";

import React, { useState, useEffect } from 'react';
import { ShieldCheck } from 'lucide-react';
import { HeartbeatGrid, Microservice } from './HeartbeatGrid';
import { LatencyTracker } from './LatencyTracker';
import { SystemLog, LogEntry } from './SystemLog';
import { AlertConfig } from './AlertConfig';
import { Server, Cpu, Database, Brain } from 'lucide-react';

const INITIAL_SERVICES: Microservice[] = [
  { id: '1', name: 'MT5 Terminal', icon: Server, status: 'Online' },
  { id: '2', name: 'Node Data Bridge', icon: Database, status: 'Online' },
  { id: '3', name: 'Python Engine', icon: Cpu, status: 'Online' },
  { id: '4', name: 'Vertex AI', icon: Brain, status: 'Degraded' },
];

export function SystemHealthMonitor() {
  const [latencyHistory, setLatencyHistory] = useState<number[]>(Array(40).fill(45));
  const [currentLatency, setCurrentLatency] = useState(45);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [services, setServices] = useState<Microservice[]>(INITIAL_SERVICES);

  // Simulate data feeds
  useEffect(() => {
    // Latency Simulation
    const latencyInterval = setInterval(() => {
      setCurrentLatency(prev => {
        // Occasionally spike
        const isSpike = Math.random() > 0.95;
        const newLat = isSpike ? Math.floor(Math.random() * 150) + 210 : Math.floor(Math.random() * 20) + 35;
        
        setLatencyHistory(curr => {
          const newHist = [...curr, newLat];
          if (newHist.length > 40) newHist.shift();
          return newHist;
        });
        
        return newLat;
      });
    }, 1000);

    // Logs Simulation
    const logInterval = setInterval(() => {
      const msgs = [
        { level: 'INFO', msg: 'DataBridge: Processed 45 tick events' },
        { level: 'SUCCESS', msg: 'MT5: Order #892415 executed successfully' },
        { level: 'WARN', msg: 'Vertex AI: Response latency elevated (850ms)' },
        { level: 'INFO', msg: 'CoreEngine: Sentiment recalculated' },
        { level: 'ERROR', msg: 'DataBridge: Connection dropped temporarily. Reconnecting...' }
      ] as const;
      
      const randomMsg = msgs[Math.floor(Math.random() * msgs.length)];
      
      setLogs(prev => {
        // Keeping up to 5000 logs to demonstrate virtualized list performance
        const newLogs = [...prev, {
          id: Math.random().toString(36).substr(2, 9),
          timestamp: new Date(),
          level: randomMsg.level,
          message: randomMsg.msg
        }];
        if (newLogs.length > 5000) newLogs.shift();
        return newLogs;
      });
    }, 800);

    return () => {
      clearInterval(latencyInterval);
      clearInterval(logInterval);
    };
  }, []);

  return (
    <div className="w-full bg-slate-950 text-slate-200 p-6 font-sans antialiased">
      <div className="max-w-7xl mx-auto space-y-6">
        
        <header className="flex items-center gap-3 pb-2 border-b border-slate-800/80">
          <ShieldCheck className="w-5 h-5 text-indigo-400" />
          <div>
            <h2 className="text-lg font-black tracking-tight text-white uppercase">Infrastructure & System Health</h2>
          </div>
        </header>

        {/* Compact Layout Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[500px]">
          
          {/* Left Column: Heartbeats, Latency & Config */}
          <div className="lg:col-span-4 flex flex-col gap-6 h-full overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
            <HeartbeatGrid services={services} />
            <LatencyTracker 
              currentLatencyMs={currentLatency} 
              history={latencyHistory} 
              thresholdMs={200} 
            />
            <AlertConfig />
          </div>

          {/* Right Column: Virtualized System Log */}
          <div className="lg:col-span-8 h-full min-h-[400px]">
            <SystemLog logs={logs} />
          </div>

        </div>
      </div>
    </div>
  );
}
