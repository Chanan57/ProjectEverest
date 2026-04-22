/**
 * OpenClaw — Conviction & Vector Gauges
 *
 * Displays animated visual dials for:
 *  - Conviction Score (0-100%) — arc-style gauge
 *  - Market Regime — badge with contextual glow color
 *  - RSI Signal — horizontal bar
 *  - ADX Strength — horizontal bar
 *
 * Uses CSS custom property transitions for smooth animation without
 * triggering layout recalculations.
 */

import { useAITelemetryStore } from '../../store/useAITelemetryStore';
import type { MarketRegime } from '../../store/useAITelemetryStore';
import { useRef, useEffect } from 'react';

/* ── Regime display config ──────────────────────────────────────────────────── */
const REGIME_CONFIG: Record<MarketRegime, { label: string; color: string; icon: string }> = {
  TRENDING_BULL:           { label: 'Trending Bull',            color: '#22c55e', icon: '⬆' },
  TRENDING_BEAR:           { label: 'Trending Bear',            color: '#ef4444', icon: '⬇' },
  RANGING:                 { label: 'Ranging',                  color: '#fbbf24', icon: '↔' },
  HIGH_VOLATILITY_BREAKOUT:{ label: 'High Vol. Breakout',       color: '#a855f7', icon: '⚡' },
  CONSOLIDATION:           { label: 'Consolidation',            color: '#64748b', icon: '◈' },
  UNKNOWN:                 { label: 'Analysing…',               color: '#475569', icon: '?' },
};

/* ── Arc SVG Gauge ──────────────────────────────────────────────────────────── */
interface ArcGaugeProps {
  value: number;    // 0-100
  size?: number;
  label: string;
  color: string;
  subtitle?: string;
}

function ArcGauge({ value, size = 140, label, color, subtitle }: ArcGaugeProps) {
  const clampedValue = Math.max(0, Math.min(100, value));

  // SVG arc math
  const radius = 52;
  const cx = size / 2;
  const cy = size / 2;
  const strokeWidth = 8;
  const circumference = Math.PI * radius; // semi-circle = half circumference
  const offset = circumference - (clampedValue / 100) * circumference;

  // Colour based on conviction level
  const arcColor = value > 70 ? '#22c55e' : value > 40 ? '#fbbf24' : '#ef4444';
  const finalColor = color !== '' ? color : arcColor;

  // Animated ref for the number counter
  const numRef = useRef<HTMLSpanElement>(null);
  const prevVal = useRef(0);

  useEffect(() => {
    if (!numRef.current) return;
    const start = prevVal.current;
    const end = clampedValue;
    const duration = 600;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // cubic ease-out
      const current = Math.round(start + (end - start) * eased);
      if (numRef.current) numRef.current.textContent = `${current}`;
      if (progress < 1) requestAnimationFrame(animate);
      else prevVal.current = end;
    };

    requestAnimationFrame(animate);
  }, [clampedValue]);

  return (
    <div className="gauge-arc-wrapper">
      <svg width={size} height={size * 0.6} viewBox={`0 0 ${size} ${size * 0.6}`} className="gauge-arc-svg">
        {/* Background track */}
        <path
          d={`M ${strokeWidth} ${size * 0.55} A ${radius} ${radius} 0 0 1 ${size - strokeWidth} ${size * 0.55}`}
          fill="none"
          stroke="rgba(71,85,105,0.3)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d={`M ${strokeWidth} ${size * 0.55} A ${radius} ${radius} 0 0 1 ${size - strokeWidth} ${size * 0.55}`}
          fill="none"
          stroke={finalColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={`${offset}`}
          style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), stroke 0.4s ease' }}
          filter={`drop-shadow(0 0 6px ${finalColor}88)`}
        />
        {/* Centre value */}
        <foreignObject x={cx - 38} y={size * 0.18} width={76} height={50}>
          <div className="gauge-arc-center">
            <span ref={numRef} className="gauge-arc-value" style={{ color: finalColor }}>
              {clampedValue}
            </span>
            <span className="gauge-arc-pct">%</span>
          </div>
        </foreignObject>
      </svg>
      <div className="gauge-arc-label">{label}</div>
      {subtitle && <div className="gauge-arc-sub">{subtitle}</div>}
    </div>
  );
}

/* ── Linear Bar Gauge ───────────────────────────────────────────────────────── */
interface LinearGaugeProps {
  value: number;
  label: string;
  color: string;
  min?: number;
  max?: number;
  unit?: string;
}

function LinearGauge({ value, label, color, min = 0, max = 100, unit = '' }: LinearGaugeProps) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

  return (
    <div className="gauge-linear-wrapper">
      <div className="gauge-linear-header">
        <span className="gauge-linear-label">{label}</span>
        <span className="gauge-linear-value" style={{ color }}>
          {value.toFixed(0)}{unit}
        </span>
      </div>
      <div className="gauge-linear-track">
        <div
          className="gauge-linear-fill"
          style={{
            width: `${pct}%`,
            background: color,
            boxShadow: `0 0 8px ${color}66`,
            transition: 'width 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}
        />
        {/* Tick marks */}
        {[25, 50, 75].map((tick) => (
          <div
            key={tick}
            className="gauge-linear-tick"
            style={{ left: `${tick}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Regime Badge ───────────────────────────────────────────────────────────── */
function RegimeBadge({ regime }: { regime: MarketRegime }) {
  const cfg = REGIME_CONFIG[regime];

  return (
    <div className="regime-badge-wrapper">
      <div className="regime-badge-label">MARKET REGIME</div>
      <div
        className="regime-badge"
        style={{
          borderColor: `${cfg.color}44`,
          background: `${cfg.color}12`,
          boxShadow: `0 0 20px ${cfg.color}22`,
        }}
      >
        <span className="regime-badge-icon" style={{ color: cfg.color }}>
          {cfg.icon}
        </span>
        <span className="regime-badge-text" style={{ color: cfg.color }}>
          {cfg.label}
        </span>
        <div
          className="regime-badge-pulse"
          style={{ background: cfg.color }}
        />
      </div>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────────────────────── */
export default function ConvictionGauges() {
  const conviction = useAITelemetryStore((s) => s.conviction);
  const updatedAt = conviction.updatedAt;

  const ageMs = updatedAt > 0 ? Date.now() - updatedAt : null;
  const ageLabel = ageMs === null
    ? 'No signal'
    : ageMs < 2000
      ? 'Just now'
      : `${Math.round(ageMs / 1000)}s ago`;

  return (
    <div className="gauges-shell">
      {/* Header */}
      <div className="gauges-header">
        <span className="gauges-header-label">CONVICTION & VECTOR GAUGES</span>
        <span className="gauges-header-age">{ageLabel}</span>
      </div>

      {/* Arc gauge row */}
      <div className="gauges-arc-row">
        <ArcGauge
          value={conviction.score}
          label="Conviction Score"
          color=""
          subtitle="AI Confidence in Signal"
          size={150}
        />
        <div className="gauges-arc-divider" />
        <RegimeBadge regime={conviction.regime} />
      </div>

      {/* Linear gauges */}
      <div className="gauges-linear-stack">
        <LinearGauge
          value={conviction.rsiSignal}
          label="RSI Signal"
          color={conviction.rsiSignal > 70 ? '#ef4444' : conviction.rsiSignal < 30 ? '#22c55e' : '#fbbf24'}
          unit=""
        />
        <LinearGauge
          value={conviction.adxStrength}
          label="ADX Trend Strength"
          color={conviction.adxStrength > 50 ? '#00e5ff' : '#64748b'}
          unit=""
        />
      </div>
    </div>
  );
}
