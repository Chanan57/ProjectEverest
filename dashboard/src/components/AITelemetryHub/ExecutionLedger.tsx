/**
 * OpenClaw — Active Execution Ledger
 *
 * Card-based display that renders a new card the moment a trade is executed.
 * Each card shows: Entry Price, SL, TP, AI Rule that triggered entry, and live PnL state.
 *
 * Cards animate in from the top using CSS keyframes.
 * Subscribes only to `ledger` slice — does not re-render when stream tokens arrive.
 */

import { useAITelemetryStore } from '../../store/useAITelemetryStore';
import type { LedgerEntry } from '../../store/useAITelemetryStore';

/* ── Helpers ────────────────────────────────────────────────────────────────── */
function formatPrice(v: number): string {
  return v.toFixed(2);
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function riskRewardRatio(entry: LedgerEntry): string {
  const risk = Math.abs(entry.entryPrice - entry.sl);
  const reward = Math.abs(entry.tp - entry.entryPrice);
  if (risk === 0) return '∞';
  return (reward / risk).toFixed(1);
}

/* ── Single Trade Card ──────────────────────────────────────────────────────── */
function TradeCard({ entry }: { entry: LedgerEntry }) {
  const isLong = entry.direction === 'LONG';
  const rrRatio = riskRewardRatio(entry);

  return (
    <div className={`ledger-card ${isLong ? 'card-long' : 'card-short'}`}>
      {/* ── Card header ──────────────────────────────────────────── */}
      <div className="ledger-card-header">
        <div className="ledger-card-header-left">
          <div className={`ledger-direction-badge ${isLong ? 'badge-long' : 'badge-short'}`}>
            {isLong ? '▲ LONG' : '▼ SHORT'}
          </div>
          <span className="ledger-symbol">{entry.symbol}</span>
          <span className="ledger-volume">{entry.volume.toFixed(2)} lot</span>
        </div>
        <div className="ledger-card-header-right">
          <span className="ledger-timestamp">{relativeTime(entry.timestamp)}</span>
        </div>
      </div>

      {/* ── Price grid ───────────────────────────────────────────── */}
      <div className="ledger-price-grid">
        <div className="ledger-price-cell">
          <span className="ledger-price-label">ENTRY</span>
          <span className="ledger-price-value ledger-price-entry">
            {formatPrice(entry.entryPrice)}
          </span>
        </div>
        <div className="ledger-price-divider" />
        <div className="ledger-price-cell">
          <span className="ledger-price-label">STOP LOSS</span>
          <span className="ledger-price-value ledger-price-sl">
            {formatPrice(entry.sl)}
          </span>
        </div>
        <div className="ledger-price-divider" />
        <div className="ledger-price-cell">
          <span className="ledger-price-label">TAKE PROFIT</span>
          <span className="ledger-price-value ledger-price-tp">
            {formatPrice(entry.tp)}
          </span>
        </div>
        <div className="ledger-price-divider" />
        <div className="ledger-price-cell">
          <span className="ledger-price-label">R:R RATIO</span>
          <span className="ledger-price-value ledger-price-rr">
            1:{rrRatio}
          </span>
        </div>
      </div>

      {/* ── AI Rule chip ─────────────────────────────────────────── */}
      <div className="ledger-rule-section">
        <span className="ledger-rule-icon">⬡</span>
        <div className="ledger-rule-content">
          <span className="ledger-rule-label">AI TRIGGER RULE</span>
          <span className="ledger-rule-text">{entry.triggerRule}</span>
        </div>
        <div className="ledger-conviction-chip">
          <span className="ledger-conviction-label">Conviction</span>
          <span
            className="ledger-conviction-value"
            style={{
              color: entry.convictionAtEntry > 70
                ? '#22c55e'
                : entry.convictionAtEntry > 40
                  ? '#fbbf24'
                  : '#ef4444',
            }}
          >
            {entry.convictionAtEntry}%
          </span>
        </div>
      </div>

      {/* ── SL/TP visual distance bar ────────────────────────────── */}
      <div className="ledger-range-bar">
        <div className="ledger-range-sl-label">SL</div>
        <div className="ledger-range-track">
          {/* Entry marker */}
          <div
            className="ledger-range-entry-marker"
            style={{
              left: isLong
                ? `${((entry.entryPrice - entry.sl) / (entry.tp - entry.sl)) * 100}%`
                : `${((entry.sl - entry.entryPrice) / (entry.sl - entry.tp)) * 100}%`,
            }}
          />
          {/* Fill from SL → Entry (risk zone) */}
          <div
            className="ledger-range-risk"
            style={{
              width: isLong
                ? `${((entry.entryPrice - entry.sl) / (entry.tp - entry.sl)) * 100}%`
                : `${((entry.sl - entry.entryPrice) / (entry.sl - entry.tp)) * 100}%`,
            }}
          />
        </div>
        <div className="ledger-range-tp-label">TP</div>
      </div>
    </div>
  );
}

/* ── Empty State ────────────────────────────────────────────────────────────── */
function EmptyLedger() {
  return (
    <div className="ledger-empty">
      <div className="ledger-empty-icon">◳</div>
      <p className="ledger-empty-title">No Active Executions</p>
      <p className="ledger-empty-sub">
        Trade cards will appear here the moment the AI engine triggers an entry signal.
      </p>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────────────────────── */
export default function ExecutionLedger() {
  const ledger = useAITelemetryStore((s) => s.ledger);
  const clearLedger = useAITelemetryStore((s) => s.clearLedger);

  return (
    <div className="ledger-shell">
      {/* Header */}
      <div className="ledger-header">
        <div className="ledger-header-left">
          <div className="ledger-status-dot" />
          <span className="ledger-header-label">ACTIVE EXECUTION LEDGER</span>
          {ledger.length > 0 && (
            <span className="ledger-count-badge">{ledger.length}</span>
          )}
        </div>
        {ledger.length > 0 && (
          <button
            className="ledger-clear-btn"
            onClick={clearLedger}
            aria-label="Clear execution ledger"
          >
            Clear
          </button>
        )}
      </div>

      {/* Card list */}
      <div className="ledger-card-list">
        {ledger.length === 0
          ? <EmptyLedger />
          : ledger.map((entry) => (
              <TradeCard key={entry.id} entry={entry} />
            ))
        }
      </div>
    </div>
  );
}
