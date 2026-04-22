/**
 * ActiveExecutionGrid — Open positions table with real-time price flash
 */

import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useRef, useEffect } from 'react';

export default function ActiveExecutionGrid() {
  const positions = useCommandCenterStore((s) => s.positions);
  const isStandby = useCommandCenterStore((s) => s.engineConfig.isInStandbyMode);
  const xauPositions = positions.filter((p) => p.symbol === 'XAUUSD');

  return (
    <div className="flex flex-col gap-3 flex-1 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase">
            Active Executions
          </h2>
          <span className="px-2 py-0.5 text-xs text-mono font-bold bg-gold-dim text-gold rounded">
            XAUUSD
          </span>
          <span className="text-xs text-text-muted">
            {xauPositions.length} open position{xauPositions.length !== 1 ? 's' : ''}
          </span>
        </div>
        {isStandby && (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold bg-gold-dim text-gold rounded-full animate-pulse-slow">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            ATR STANDBY — New Entries Paused
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface-card rounded-xl border border-border-subtle overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted text-[10px] tracking-widest uppercase border-b border-border-subtle">
              <th className="text-left py-2.5 px-4 font-medium">Ticket</th>
              <th className="text-left py-2.5 px-4 font-medium">Side</th>
              <th className="text-right py-2.5 px-4 font-medium">Volume</th>
              <th className="text-right py-2.5 px-4 font-medium">Entry</th>
              <th className="text-right py-2.5 px-4 font-medium">Current</th>
              <th className="text-right py-2.5 px-4 font-medium">SL</th>
              <th className="text-right py-2.5 px-4 font-medium">TP</th>
              <th className="text-right py-2.5 px-4 font-medium">P&L</th>
            </tr>
          </thead>
          <tbody>
            {xauPositions.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-12 text-text-muted">
                  No open XAUUSD positions
                </td>
              </tr>
            ) : (
              xauPositions.map((pos) => (
                <PositionRow key={pos.ticket} position={pos} />
              ))
            )}
          </tbody>
        </table>

        {/* Footer PnL Summary */}
        {xauPositions.length > 0 && (
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-border-subtle bg-surface-panel/50">
            <span className="text-[10px] text-text-muted uppercase tracking-widest">
              Total Floating P&L
            </span>
            <FloatingTotal positions={xauPositions} />
          </div>
        )}
      </div>
    </div>
  );
}

function PositionRow({ position }: { position: ReturnType<typeof useCommandCenterStore.getState>['positions'][0] }) {
  const rowRef = useRef<HTMLTableRowElement>(null);
  const prevPriceRef = useRef(position.priceCurrent);

  // Flash the row edge on price change
  useEffect(() => {
    if (!rowRef.current) return;
    const direction = position.priceCurrent > prevPriceRef.current ? 'profit' : 'loss';
    prevPriceRef.current = position.priceCurrent;

    rowRef.current.style.borderLeftColor = direction === 'profit' ? '#22c55e' : '#ef4444';
    rowRef.current.style.borderLeftWidth = '3px';

    const timeout = setTimeout(() => {
      if (rowRef.current) {
        rowRef.current.style.borderLeftColor = 'transparent';
        rowRef.current.style.borderLeftWidth = '3px';
      }
    }, 200);

    return () => clearTimeout(timeout);
  }, [position.priceCurrent]);

  const isBuy = position.type === 'BUY';
  const pnlColor = position.profit >= 0 ? 'text-profit' : 'text-loss';
  const sideColor = isBuy ? 'text-profit' : 'text-loss';
  const sideBg = isBuy ? 'bg-profit-dim' : 'bg-loss-dim';

  return (
    <tr
      ref={rowRef}
      className="border-b border-border-subtle hover:bg-surface-elevated/30 transition-colors duration-100"
      style={{ borderLeftColor: 'transparent', borderLeftWidth: '3px', borderLeftStyle: 'solid' }}
    >
      <td className="py-2.5 px-4 text-mono text-text-secondary">#{position.ticket}</td>
      <td className="py-2.5 px-4">
        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${sideColor} ${sideBg}`}>
          {position.type}
        </span>
      </td>
      <td className="py-2.5 px-4 text-right text-mono text-text-primary">{position.volume.toFixed(2)}</td>
      <td className="py-2.5 px-4 text-right text-mono text-text-secondary">{position.priceOpen.toFixed(2)}</td>
      <td className="py-2.5 px-4 text-right text-mono text-text-primary font-semibold">{position.priceCurrent.toFixed(2)}</td>
      <td className="py-2.5 px-4 text-right text-mono text-loss/60">{position.sl.toFixed(2)}</td>
      <td className="py-2.5 px-4 text-right text-mono text-profit/60">{position.tp.toFixed(2)}</td>
      <td className={`py-2.5 px-4 text-right text-mono font-bold ${pnlColor}`}>
        {position.profit >= 0 ? '+' : ''}{position.profit.toFixed(2)}
      </td>
    </tr>
  );
}

function FloatingTotal({ positions }: { positions: ReturnType<typeof useCommandCenterStore.getState>['positions'] }) {
  const total = positions.reduce((sum, p) => sum + p.profit, 0);
  const color = total >= 0 ? 'text-profit' : 'text-loss';
  return (
    <span className={`text-mono text-sm font-bold ${color}`}>
      {total >= 0 ? '+' : ''}{total.toFixed(2)} USD
    </span>
  );
}
