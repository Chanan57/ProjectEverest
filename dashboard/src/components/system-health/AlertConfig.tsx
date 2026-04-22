"use client";

import React, { useState } from 'react';
import { Bell, Key, MessageSquare, Save, Check } from 'lucide-react';
import { cn } from '../telemetry/utils';

export function AlertConfig({ className }: { className?: string }) {
  const [apiKey, setApiKey] = useState('');
  const [chatId, setChatId] = useState('');
  const [saved, setSaved] = useState(false);
  const [toggles, setToggles] = useState({
    tradeExecuted: true,
    connectionLost: true,
    riskLimit: true,
  });

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className={cn("flex flex-col p-4 bg-slate-900/40 rounded-xl border border-slate-800/50 backdrop-blur-sm", className)}>
      <div className="flex items-center gap-2 mb-4">
        <Bell className="w-4 h-4 text-indigo-400" />
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Telegram Alert Config</h3>
      </div>

      <div className="space-y-4">
        {/* API Key */}
        <div>
          <label className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 ml-1">
            <Key className="w-3 h-3" /> Bot API Key
          </label>
          <input 
            type="password" 
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="123456789:ABCdefGHIjklMNO..." 
            className="w-full bg-slate-950/50 border border-slate-800 rounded-md px-3 py-2 text-sm text-slate-300 placeholder:text-slate-700 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all font-mono"
          />
        </div>

        {/* Chat ID */}
        <div>
          <label className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 ml-1">
            <MessageSquare className="w-3 h-3" /> Chat ID
          </label>
          <input 
            type="text" 
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            placeholder="-100123456789" 
            className="w-full bg-slate-950/50 border border-slate-800 rounded-md px-3 py-2 text-sm text-slate-300 placeholder:text-slate-700 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition-all font-mono"
          />
        </div>

        {/* Toggles */}
        <div className="space-y-2 pt-2 border-t border-slate-800/50">
          {[
            { id: 'tradeExecuted', label: 'Trade Executed', desc: 'Entries, Exits, SL/TP triggers' },
            { id: 'connectionLost', label: 'Connection Lost', desc: 'MT5 or Data Bridge disconnects' },
            { id: 'riskLimit', label: 'Risk Limit Approached', desc: 'Drawdown or exposure alerts' },
          ].map((item) => {
            const isActive = toggles[item.id as keyof typeof toggles];
            return (
              <label key={item.id} className="flex items-center justify-between group cursor-pointer p-2 hover:bg-slate-800/30 rounded-lg transition-colors">
                <div>
                  <div className="text-sm text-slate-300 font-medium">{item.label}</div>
                  <div className="text-[10px] text-slate-500">{item.desc}</div>
                </div>
                <div 
                  className={cn(
                    "w-8 h-4 rounded-full relative transition-colors duration-300",
                    isActive ? "bg-indigo-500" : "bg-slate-700"
                  )}
                  onClick={() => setToggles(prev => ({...prev, [item.id]: !isActive}))}
                >
                  <div className={cn(
                    "absolute top-0.5 left-0.5 bg-white w-3 h-3 rounded-full transition-transform duration-300 shadow-sm",
                    isActive ? "transform translate-x-4" : ""
                  )} />
                </div>
              </label>
            )
          })}
        </div>

        {/* Save Button */}
        <button 
          onClick={handleSave}
          className={cn(
            "w-full flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-bold tracking-wider uppercase transition-all duration-300",
            saved 
              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" 
              : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
          )}
        >
          {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Saved' : 'Save Config'}
        </button>
      </div>
    </div>
  );
}
