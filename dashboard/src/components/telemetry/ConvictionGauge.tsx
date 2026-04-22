"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Target } from 'lucide-react';
import { cn } from './utils';

interface ConvictionGaugeProps {
  score: number; // 0 to 100
  className?: string;
}

export function ConvictionGauge({ score, className }: ConvictionGaugeProps) {
  const normalizedScore = Math.min(Math.max(score, 0), 100);
  
  // Calculate SVG stroke dash array
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (normalizedScore / 100) * circumference;

  // Determine color based on conviction level
  const getColor = (s: number) => {
    if (s >= 80) return 'text-emerald-500';
    if (s >= 50) return 'text-amber-500';
    return 'text-rose-500';
  };

  return (
    <div className={cn("flex flex-col items-center justify-center p-6 bg-slate-900/40 rounded-xl border border-slate-800/50 backdrop-blur-sm", className)}>
      <div className="flex items-center gap-2 mb-4 text-slate-300">
        <Target className="w-5 h-5" />
        <h3 className="text-sm font-semibold uppercase tracking-wider">Conviction Score</h3>
      </div>
      
      <div className="relative flex items-center justify-center w-32 h-32">
        {/* Background track */}
        <svg className="absolute w-full h-full transform -rotate-90">
          <circle
            cx="64"
            cy="64"
            r={radius}
            stroke="currentColor"
            strokeWidth="8"
            fill="transparent"
            className="text-slate-800"
          />
          {/* Animated score indicator */}
          <motion.circle
            cx="64"
            cy="64"
            r={radius}
            stroke="currentColor"
            strokeWidth="8"
            fill="transparent"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 1, ease: "easeOut" }}
            className={cn(getColor(normalizedScore), "transition-colors duration-500")}
            strokeLinecap="round"
          />
        </svg>
        
        {/* Center Text */}
        <div className="absolute flex flex-col items-center justify-center">
          <span className="text-3xl font-black text-white tracking-tighter">
            {normalizedScore}
            <span className="text-lg text-slate-500">%</span>
          </span>
        </div>
      </div>
    </div>
  );
}
