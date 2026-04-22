/**
 * XAUUSDCommandCenter — The core control panel for OpenClaw
 *
 * Contains:
 *  - Hard Halt mechanism (confirmation-gated)
 *  - Session & Volatility gates
 *  - ATR Ceiling input
 *  - AI Confidence threshold slider
 *  - Autonomous Mode lockout indicator
 */

import { useState, useCallback } from 'react';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { sendCommand } from '../../services/websocketClient';

export default function XAUUSDCommandCenter() {
  return (
    <div className="flex flex-col gap-4 flex-1 min-w-0">
      <AutonomousModeBanner />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SessionVolatilityGates />
        <AIConfidenceControl />
      </div>
      <ATRCeilingControl />
      <HardHaltControl />
    </div>
  );
}

/* ================================================================
   Autonomous Mode Lockout Banner
   ================================================================ */
function AutonomousModeBanner() {
  const autonomousMode = useCommandCenterStore((s) => s.engineConfig.autonomousMode);
  const isHalted = useCommandCenterStore((s) => s.engineConfig.isEngineHalted);

  if (isHalted) {
    return (
      <div className="flex items-center gap-3 px-5 py-3.5 rounded-xl bg-danger-dim border border-loss/30 animate-glow-danger">
        <svg className="w-5 h-5 text-loss flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
        </svg>
        <div className="flex flex-col">
          <span className="text-loss font-bold text-sm">ENGINE HALTED — ALL POSITIONS LIQUIDATED</span>
          <span className="text-loss/60 text-xs">Manual restart required. The engine will not resume automatically.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 px-5 py-3.5 rounded-xl bg-accent-primary-dim border border-accent-primary/20">
      <div className="relative flex-shrink-0">
        <div className="w-3 h-3 rounded-full bg-accent-primary animate-pulse-slow" />
        <div className="absolute inset-0 w-3 h-3 rounded-full bg-accent-primary/30 animate-ping" />
      </div>
      <div className="flex flex-col">
        <span className="text-accent-primary font-bold text-sm tracking-wide">
          {autonomousMode ? 'AUTONOMOUS MODE — ALGORITHMIC CONTROL ACTIVE' : 'ENGINE ACTIVE'}
        </span>
        <span className="text-accent-primary/50 text-xs">
          Manual execution is disabled. All trade decisions are routed through the AI pipeline and Risk Governor.
        </span>
      </div>
      <div className="ml-auto flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-card border border-border-subtle">
        <svg className="w-3.5 h-3.5 text-accent-primary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
        <span className="text-[10px] text-accent-primary font-bold tracking-wider">LOCKED</span>
      </div>
    </div>
  );
}

/* ================================================================
   Session & Volatility Gates
   ================================================================ */
function SessionVolatilityGates() {
  const sessionGates = useCommandCenterStore((s) => s.engineConfig.sessionGates);
  const toggleGate = useCommandCenterStore((s) => s.toggleSessionGate);

  const gates: { key: keyof typeof sessionGates; label: string; desc: string; time: string }[] = [
    { key: 'londonOpen', label: 'London Open', desc: 'High-impact session open', time: '08:00-10:00 GMT' },
    { key: 'nyOverlap', label: 'NY Overlap', desc: 'Peak volatility window', time: '13:00-17:00 GMT' },
    { key: 'asiaSession', label: 'Asia Session', desc: 'Low-liquidity hours', time: '00:00-07:00 GMT' },
    { key: 'newsBlackout', label: 'News Blackout', desc: 'Halt on high-impact events', time: 'Dynamic' },
  ];

  return (
    <div className="bg-surface-card rounded-xl border border-border-subtle p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-gold" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z" clipRule="evenodd" />
        </svg>
        <h3 className="text-sm font-semibold text-text-primary">Session & Volatility Gates</h3>
      </div>
      <p className="text-[11px] text-text-muted -mt-1">
        Control which trading sessions the engine is permitted to enter trades during.
      </p>

      <div className="flex flex-col gap-2">
        {gates.map((gate) => (
          <button
            key={gate.key}
            onClick={() => toggleGate(gate.key)}
            className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors cursor-pointer group"
          >
            <div className="flex flex-col items-start">
              <span className="text-xs font-semibold text-text-primary group-hover:text-accent-primary transition-colors">
                {gate.label}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-text-muted">{gate.desc}</span>
                <span className="text-[10px] text-text-muted text-mono">({gate.time})</span>
              </div>
            </div>
            <ToggleSwitch enabled={sessionGates[gate.key]} />
          </button>
        ))}
      </div>
    </div>
  );
}

/* ================================================================
   AI Confidence Threshold Slider
   ================================================================ */
function AIConfidenceControl() {
  const threshold = useCommandCenterStore((s) => s.engineConfig.aiConfidenceThreshold);
  const setThreshold = useCommandCenterStore((s) => s.setAiConfidenceThreshold);
  const isStandby = useCommandCenterStore((s) => s.engineConfig.isInStandbyMode);

  const getConfidenceColor = (val: number) => {
    if (val >= 80) return 'text-profit';
    if (val >= 50) return 'text-gold';
    return 'text-loss';
  };

  const getConfidenceLabel = (val: number) => {
    if (val >= 90) return 'ULTRA-SELECTIVE';
    if (val >= 75) return 'HIGH CONVICTION';
    if (val >= 50) return 'MODERATE';
    if (val >= 25) return 'PERMISSIVE';
    return 'UNRESTRICTED';
  };

  return (
    <div className="bg-surface-card rounded-xl border border-border-subtle p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-accent-primary" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 1a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 1zM5.05 3.05a.75.75 0 011.06 0l1.062 1.06A.75.75 0 016.11 5.173L5.05 4.11a.75.75 0 010-1.06zm9.9 0a.75.75 0 010 1.06l-1.06 1.062a.75.75 0 01-1.062-1.061l1.061-1.06a.75.75 0 011.06 0zM10 7a3 3 0 100 6 3 3 0 000-6zm-7.25 3a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5H3.5a.75.75 0 01-.75-.75zM15 10a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5h-1.5A.75.75 0 0115 10zm-3.89 4.89a.75.75 0 011.06 0l1.06 1.06a.75.75 0 01-1.06 1.06l-1.06-1.06a.75.75 0 010-1.06zm-4.22 0a.75.75 0 010 1.06l-1.06 1.06a.75.75 0 11-1.061-1.06l1.06-1.06a.75.75 0 011.06 0zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15z" />
        </svg>
        <h3 className="text-sm font-semibold text-text-primary">AI Confidence Gate</h3>
      </div>
      <p className="text-[11px] text-text-muted -mt-1">
        Minimum AI confidence score required before the engine will permit trade execution.
      </p>

      {/* Slider */}
      <div className="flex flex-col gap-3 mt-1">
        <div className="flex items-center justify-between">
          <span className={`text-[10px] font-bold tracking-widest uppercase ${getConfidenceColor(threshold)}`}>
            {getConfidenceLabel(threshold)}
          </span>
          <span className={`text-mono text-2xl font-bold ${getConfidenceColor(threshold)}`}>
            {threshold}%
          </span>
        </div>

        <input
          type="range"
          min="0"
          max="100"
          step="1"
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer
                     bg-surface-elevated
                     accent-accent-primary
                     [&::-webkit-slider-thumb]:appearance-none
                     [&::-webkit-slider-thumb]:w-5
                     [&::-webkit-slider-thumb]:h-5
                     [&::-webkit-slider-thumb]:rounded-full
                     [&::-webkit-slider-thumb]:bg-accent-primary
                     [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,229,255,0.4)]
                     [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-webkit-slider-thumb]:transition-shadow
                     [&::-webkit-slider-thumb]:duration-200
                     hover:[&::-webkit-slider-thumb]:shadow-[0_0_18px_rgba(0,229,255,0.6)]"
        />

        <div className="flex items-center justify-between text-[9px] text-text-muted">
          <span>0% — Execute All</span>
          <span>100% — Maximum Filter</span>
        </div>

        {/* Standby warning */}
        {isStandby && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gold-dim border border-gold/20 mt-1">
            <svg className="w-3.5 h-3.5 text-gold flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            <span className="text-[10px] text-gold">
              Engine is in Standby Mode — confidence gate is moot until ATR returns below ceiling.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ================================================================
   ATR Ceiling Control
   ================================================================ */
function ATRCeilingControl() {
  const atrCeiling = useCommandCenterStore((s) => s.engineConfig.atrCeiling);
  const setAtrCeiling = useCommandCenterStore((s) => s.setAtrCeiling);
  const isStandby = useCommandCenterStore((s) => s.engineConfig.isInStandbyMode);
  const goldHeat = useCommandCenterStore((s) => s.marketHeat.find((m) => m.symbol === 'XAUUSD'));

  const currentAtr = goldHeat?.atr ?? 0;
  const atrPercent = atrCeiling > 0 ? Math.min((currentAtr / atrCeiling) * 100, 120) : 0;

  return (
    <div className={`bg-surface-card rounded-xl border p-4 flex flex-col gap-3 transition-all duration-300 ${
      isStandby ? 'border-gold/30 animate-glow-danger' : 'border-border-subtle'
    }`}
    style={isStandby ? { '--tw-shadow-color': 'rgba(251,191,36,0.3)', animationName: 'glow-danger' } as React.CSSProperties : {}}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gold" fill="currentColor" viewBox="0 0 20 20">
            <path d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.869a.75.75 0 00-.75.75v3.363a.75.75 0 001.5 0v-2.554l.312.311a7 7 0 0011.712-3.138.75.75 0 00-1.449-.387zm1.07-7.078a.75.75 0 00-.75.75v2.554l-.312-.311a7 7 0 00-11.712 3.138.75.75 0 001.449.387 5.5 5.5 0 019.201-2.466l.312.311H12.97a.75.75 0 000 1.5h3.362a.75.75 0 00.75-.75V5.096a.75.75 0 00-.75-.75z" />
          </svg>
          <h3 className="text-sm font-semibold text-text-primary">ATR Volatility Ceiling</h3>
        </div>

        {isStandby && (
          <span className="px-2.5 py-1 text-[10px] font-bold bg-gold-dim text-gold rounded-full animate-pulse-slow tracking-wider">
            STANDBY ACTIVE
          </span>
        )}
      </div>

      <div className="flex items-center gap-6">
        {/* Current ATR Display */}
        <div className="flex flex-col items-center gap-1 min-w-[100px]">
          <span className="text-[10px] text-text-muted uppercase tracking-widest">Current ATR</span>
          <span className={`text-mono text-2xl font-bold ${isStandby ? 'text-gold' : 'text-text-primary'}`}>
            {currentAtr.toFixed(2)}
          </span>
        </div>

        {/* Progress Gauge */}
        <div className="flex-1 flex flex-col gap-1.5">
          <div className="w-full h-3 bg-surface-elevated rounded-full overflow-hidden relative">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                isStandby ? 'bg-gold' : atrPercent > 80 ? 'bg-[#f97316]' : 'bg-profit'
              }`}
              style={{ width: `${Math.min(atrPercent, 100)}%` }}
            />
            {/* Ceiling marker */}
            <div className="absolute right-0 top-0 h-full w-0.5 bg-loss/50" />
          </div>
          <div className="flex justify-between text-[9px] text-text-muted">
            <span>0</span>
            <span className="text-mono">{atrPercent.toFixed(0)}% of ceiling</span>
          </div>
        </div>

        {/* Ceiling Input */}
        <div className="flex flex-col items-center gap-1 min-w-[100px]">
          <span className="text-[10px] text-text-muted uppercase tracking-widest">Ceiling</span>
          <input
            type="number"
            step="0.1"
            min="0.1"
            value={atrCeiling}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val) && val > 0) setAtrCeiling(val);
            }}
            className="w-20 bg-surface-elevated border border-border-subtle rounded-lg px-2.5 py-1.5
                       text-mono text-center text-sm font-bold text-text-primary
                       focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/30
                       transition-all"
          />
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   Hard Halt — Confirmation-Gated Emergency Stop
   ================================================================ */
function HardHaltControl() {
  const isHalted = useCommandCenterStore((s) => s.engineConfig.isEngineHalted);
  const triggerHardHalt = useCommandCenterStore((s) => s.triggerHardHalt);
  const resetHalt = useCommandCenterStore((s) => s.resetHalt);
  const positionCount = useCommandCenterStore((s) => s.positions.filter((p) => p.symbol === 'XAUUSD').length);

  const [showConfirmation, setShowConfirmation] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const CONFIRM_PHRASE = 'LIQUIDATE';

  const handleHardHalt = useCallback(() => {
    if (confirmText !== CONFIRM_PHRASE) return;

    triggerHardHalt();
    sendCommand('HARD_HALT', {
      symbol: 'XAUUSD',
      action: 'LIQUIDATE_AND_HALT',
      timestamp: Date.now(),
    });
    setShowConfirmation(false);
    setConfirmText('');
  }, [confirmText, triggerHardHalt]);

  if (isHalted) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-subtle p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-danger-dim flex items-center justify-center">
              <svg className="w-5 h-5 text-loss" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-loss">Engine is Halted</span>
              <span className="text-xs text-text-muted">All XAUUSD positions have been liquidated.</span>
            </div>
          </div>
          <button
            onClick={resetHalt}
            className="px-4 py-2 text-xs font-bold text-accent-primary border border-accent-primary/30
                       rounded-lg hover:bg-accent-primary-dim transition-all cursor-pointer"
          >
            RESET & RESTART ENGINE
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-card rounded-xl border border-loss/10 p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-loss" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495z" clipRule="evenodd" />
        </svg>
        <h3 className="text-sm font-semibold text-loss">Emergency Hard Halt</h3>
      </div>

      {!showConfirmation ? (
        <button
          onClick={() => setShowConfirmation(true)}
          className="w-full py-3 rounded-xl bg-danger-dim border border-loss/20
                     text-loss font-bold text-sm tracking-wide
                     hover:bg-loss/20 hover:border-loss/40
                     active:scale-[0.98] transition-all cursor-pointer"
        >
          🛑 LIQUIDATE XAUUSD & HALT ENGINE
        </button>
      ) : (
        <div className="flex flex-col gap-3 p-4 rounded-xl bg-loss/5 border border-loss/20">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold text-loss">⚠️ CONFIRMATION REQUIRED</span>
            <span className="text-[11px] text-text-secondary">
              This will immediately close all {positionCount} XAUUSD position{positionCount !== 1 ? 's' : ''} at market price
              and halt the execution engine. This action sends a <span className="text-mono text-loss font-bold">CRITICAL</span> priority
              WebSocket payload to the core-engine.
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] text-text-muted uppercase tracking-widest">
              Type "{CONFIRM_PHRASE}" to confirm
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
              placeholder={CONFIRM_PHRASE}
              className="bg-surface-elevated border border-loss/20 rounded-lg px-3 py-2
                         text-mono text-sm text-text-primary text-center
                         focus:outline-none focus:border-loss focus:ring-1 focus:ring-loss/30
                         placeholder:text-text-muted/30"
              autoFocus
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => { setShowConfirmation(false); setConfirmText(''); }}
              className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border-subtle
                         text-text-secondary text-xs font-semibold
                         hover:bg-surface-card transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleHardHalt}
              disabled={confirmText !== CONFIRM_PHRASE}
              className={`flex-1 py-2 rounded-lg text-xs font-bold tracking-wide transition-all cursor-pointer ${
                confirmText === CONFIRM_PHRASE
                  ? 'bg-loss text-white hover:bg-loss/80 active:scale-[0.98]'
                  : 'bg-surface-elevated text-text-muted cursor-not-allowed'
              }`}
            >
              EXECUTE HARD HALT
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ================================================================
   Reusable Toggle Switch
   ================================================================ */
function ToggleSwitch({ enabled }: { enabled: boolean }) {
  return (
    <div className={`relative w-10 h-5 rounded-full transition-colors duration-200 flex-shrink-0 ${
      enabled ? 'bg-accent-primary/30' : 'bg-surface-elevated'
    }`}>
      <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all duration-200 shadow-sm ${
        enabled
          ? 'left-5.5 bg-accent-primary shadow-[0_0_8px_rgba(0,229,255,0.3)]'
          : 'left-0.5 bg-text-muted'
      }`} />
    </div>
  );
}
