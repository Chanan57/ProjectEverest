/**
 * AccountStateBanner — Real-time account metrics strip
 */

import { useCommandCenterStore } from '../../store/useCommandCenterStore';

export default function AccountStateBanner() {
  const account = useCommandCenterStore((s) => s.account);
  const wsConnected = useCommandCenterStore((s) => s.wsConnected);
  const isHalted = useCommandCenterStore((s) => s.engineConfig.isEngineHalted);

  const pnlColor = account.dailyPnl >= 0 ? 'text-profit' : 'text-loss';
  const pnlBg = account.dailyPnl >= 0 ? 'bg-profit-dim' : 'bg-loss-dim';

  return (
    <div className="flex items-center justify-between px-6 py-3 bg-surface-panel border-b border-border-subtle">
      {/* Left — Brand & Connection */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-gold text-lg font-bold tracking-tight">OPENCLAW</span>
          <span className="text-text-muted text-xs font-mono">v1.0</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-profit animate-pulse-slow' : 'bg-loss'}`} />
          <span className="text-xs text-text-muted">{wsConnected ? 'LIVE' : 'OFFLINE'}</span>
        </div>
        {isHalted && (
          <span className="px-2 py-0.5 text-xs font-bold bg-danger-dim text-danger rounded animate-glow-danger">
            ENGINE HALTED
          </span>
        )}
      </div>

      {/* Center — Core Metrics */}
      <div className="flex items-center gap-8">
        <Metric label="EQUITY" value={`$${account.equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <Metric label="BALANCE" value={`$${account.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <Metric label="MARGIN" value={`$${account.margin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        <Metric label="FREE MARGIN" value={`$${account.freeMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
      </div>

      {/* Right — Daily PnL */}
      <div className={`flex items-center gap-2 px-4 py-1.5 rounded-lg ${pnlBg}`}>
        <span className="text-xs text-text-secondary">DAILY P&L</span>
        <span className={`text-mono font-bold text-sm ${pnlColor}`}>
          {account.dailyPnl >= 0 ? '+' : ''}{account.dailyPnl.toFixed(2)} {account.currency}
        </span>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-[10px] text-text-muted tracking-widest uppercase">{label}</span>
      <span className="text-mono text-sm font-semibold text-text-primary">{value}</span>
    </div>
  );
}
