"use client";

import React from 'react';
import { Server, Cpu, Database, Brain } from 'lucide-react';
import { cn } from '../telemetry/utils';

export type ServiceStatus = 'Online' | 'Degraded' | 'Offline';

export interface Microservice {
  id: string;
  name: string;
  icon: React.ElementType;
  status: ServiceStatus;
  uptime?: string;
}

interface HeartbeatGridProps {
  services: Microservice[];
  className?: string;
}

export function HeartbeatGrid({ services, className }: HeartbeatGridProps) {
  const getStatusColor = (status: ServiceStatus) => {
    switch (status) {
      case 'Online': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.05)]';
      case 'Degraded': return 'text-amber-400 bg-amber-500/10 border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.05)]';
      case 'Offline': return 'text-rose-400 bg-rose-500/10 border-rose-500/20 shadow-[0_0_10px_rgba(244,63,94,0.05)]';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const getIndicatorColor = (status: ServiceStatus) => {
    switch (status) {
      case 'Online': return 'bg-emerald-500';
      case 'Degraded': return 'bg-amber-500';
      case 'Offline': return 'bg-rose-500';
      default: return 'bg-slate-500';
    }
  };

  return (
    <div className={cn("p-4 bg-slate-900/40 rounded-xl border border-slate-800/50 backdrop-blur-sm", className)}>
      <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-widest mb-4 flex items-center gap-2">
        <Server className="w-4 h-4 text-indigo-400" />
        Microservice Heartbeat
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {services.map((service) => (
          <div key={service.id} className={cn("p-3 rounded-lg border flex items-center gap-3 transition-colors", getStatusColor(service.status))}>
            <div className="p-2 rounded-md bg-slate-950/50">
              <service.icon className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold tracking-wide truncate">{service.name}</p>
              <p className="text-[10px] opacity-80 mt-0.5 font-mono uppercase">{service.status}</p>
            </div>
            <div className="relative flex h-2 w-2 shrink-0">
              {service.status === 'Online' && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-emerald-400"></span>
              )}
              {service.status === 'Degraded' && (
                <span className="animate-pulse absolute inline-flex h-full w-full rounded-full opacity-75 bg-amber-400"></span>
              )}
              <span className={cn("relative inline-flex rounded-full h-2 w-2", getIndicatorColor(service.status))}></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
