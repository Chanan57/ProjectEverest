/**
 * MarketHeatSidebar — Volatility metrics for tracked assets
 */

import { useCommandCenterStore, type MarketHeatEntry } from '../../store/useCommandCenterStore';

export default function MarketHeatSidebar() {
  const marketHeat = useCommandCenterStore((s) => s.marketHeat);

  return (
    <div className="w-72 flex-shrink-0 flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase px-1">
        Market Heat
      </h2>

      <div className="flex flex-col gap-2">
        {marketHeat.map((entry) => (
          <HeatCard key={entry.symbol} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function HeatCard({ entry }: { entry: MarketHeatEntry }) {
  const atrPercent = Math.min((entry.atr / entry.atrCeiling) * 100, 120);
  const isOverCeiling = entry.atr > entry.atrCeiling;
  const isGold = entry.symbol === 'XAUUSD';

  const rankColors: Record<string, string> = {
    LOW: 'text-profit bg-profit-dim',
    MODERATE: 'text-gold bg-gold-dim',
    HIGH: 'text-[#f97316] bg-[rgba(249,115,22,0.12)]',
    EXTREME: 'text-loss bg-loss-dim animate-pulse-slow',
  };

  const barColor = isOverCeiling
    ? 'bg-loss'
    : atrPercent > 80
      ? 'bg-[#f97316]'
      : atrPercent > 50
        ? 'bg-gold'
        : 'bg-profit';

  const changeColor = entry.dailyChange >= 0 ? 'text-profit' : 'text-loss';

  return (
    <div className={`bg-surface-card rounded-xl border p-3 flex flex-col gap-2.5 transition-all duration-300 ${
      isGold ? 'border-gold/20' : 'border-border-subtle'
    } ${isOverCeiling && isGold ? 'animate-glow-danger' : ''}`}>
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold text-mono ${isGold ? 'text-gold' : 'text-text-primary'}`}>
            {entry.symbol}
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider ${rankColors[entry.volatilityRank]}`}>
            {entry.volatilityRank}
          </span>
        </div>
        <span className={`text-mono text-xs font-semibold ${changeColor}`}>
          {entry.dailyChange >= 0 ? '▲' : '▼'} {Math.abs(entry.dailyChange).toFixed(2)}%
        </span>
      </div>

      {/* Price */}
      <div className="text-mono text-lg font-bold text-text-primary leading-none">
        {entry.lastTick.toLocaleString('en-US', { minimumFractionDigits: 2 })}
      </div>

      {/* ATR Gauge */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-muted">ATR</span>
          <span className={`text-mono font-semibold ${isOverCeiling ? 'text-loss' : 'text-text-secondary'}`}>
            {entry.atr.toFixed(entry.atr < 1 ? 4 : 2)} / {entry.atrCeiling}
          </span>
        </div>
        <div className="w-full h-1.5 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${barColor}`}
            style={{ width: `${Math.min(atrPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Spread */}
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-text-muted">Spread</span>
        <span className="text-mono text-text-secondary">{entry.spreadPoints} pts</span>
      </div>
    </div>
  );
}
