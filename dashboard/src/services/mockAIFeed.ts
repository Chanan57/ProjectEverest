/**
 * OpenClaw — AI Telemetry Mock Feed
 *
 * Simulates a streaming LLM response + telemetry JSON blobs + trade execution events.
 *
 * Stream Protocol:
 * ─────────────────
 * The LLM streams text tokens one-by-one. Embedded in the stream are JSON sentinel
 * blocks that the backend parser would normally intercept:
 *
 *   <<<TELEMETRY_VECTOR>>>
 *   {"score":82,"regime":"TRENDING_BULL","rsiSignal":71,"adxStrength":58}
 *   <<<END_TELEMETRY>>>
 *
 * In mock mode, we parse these client-side and dispatch to the store.
 *
 *   <<<EXECUTION_EVENT>>>
 *   {"direction":"LONG","entryPrice":3318.72,"sl":3298.00,"tp":3355.00,...}
 *   <<<END_EXECUTION>>>
 *
 * This exactly mirrors what the real Python engine + LLM gateway will emit.
 */

import { useAITelemetryStore } from '../store/useAITelemetryStore';
import type { LedgerEntry, ConvictionVector, MarketRegime } from '../store/useAITelemetryStore';

/* ── Scenario scripts ───────────────────────────────────────────────────────── */
interface StreamChunk {
  token?: string;
  delay: number;
  telemetry?: Partial<ConvictionVector>;
  execution?: Omit<LedgerEntry, 'id' | 'timestamp'>;
}

const MOCK_SCENARIOS: StreamChunk[][] = [
  // Scenario 1 — Long Setup
  [
    { token: '## XAUUSD Analysis\n\n', delay: 80 },
    { token: 'Scanning ', delay: 60 },
    { token: '**XAUUSD** on the H1 timeframe. ', delay: 70 },
    { token: 'Price currently at **3318.72**. ', delay: 60 },
    { token: '30-minute candle close is being evaluated.\n\n', delay: 90 },
    { token: '- RSI(14): **71.2** — approaching overbought territory. ', delay: 80 },
    { token: '\n- ADX: **54** — strong trend in progress. ', delay: 80 },
    { token: '\n- EMA Stack: **Bullish alignment confirmed** (EMA8 > EMA21 > EMA55).\n\n', delay: 100 },
    {
      telemetry: { score: 38, regime: 'TRENDING_BULL' as MarketRegime, rsiSignal: 71, adxStrength: 54 },
      delay: 150,
    },
    { token: 'Checking session gates…\n\n', delay: 120 },
    { token: '- **London Open**: ✓ Active\n', delay: 80 },
    { token: '- **NY Overlap**: ✓ Active\n', delay: 80 },
    { token: '- **News Blackout**: Clear\n\n', delay: 100 },
    { token: 'XAUUSD is approaching a known resistance cluster at **2350**. ', delay: 80 },
    { token: 'Checking for a pullback entry on the 15-minute timeframe...\n\n', delay: 100 },
    {
      telemetry: { score: 61, regime: 'TRENDING_BULL' as MarketRegime },
      delay: 200,
    },
    { token: 'Price action shows a **bullish pinbar** forming on support at **3310**. ', delay: 80 },
    { token: 'Volume surge detected. ', delay: 60 },
    { token: '**Institutional order block** visible at the H4 level.\n\n', delay: 90 },
    {
      telemetry: { score: 78, regime: 'TRENDING_BULL' as MarketRegime, rsiSignal: 68, adxStrength: 61 },
      delay: 180,
    },
    { token: '**CONVICTION THRESHOLD MET** (78% ≥ 75%).\n\n', delay: 100 },
    { token: 'Initiating **LONG** entry criteria check…\n', delay: 90 },
    { token: '- Entry Zone: **3318.50 – 3319.00**\n', delay: 80 },
    { token: '- Stop Loss: **ATR-based** at **3298.00** (20.72 points risk)\n', delay: 80 },
    { token: '- Take Profit: **2.1R target** → **3361.51**\n\n', delay: 100 },
    { token: '`EXECUTING LONG ORDER...`\n', delay: 120 },
    {
      execution: {
        symbol: 'XAUUSD',
        direction: 'LONG',
        entryPrice: 3318.72,
        sl: 3298.00,
        tp: 3361.51,
        volume: 0.05,
        triggerRule: 'Rule A: EMA Bull Stack + H4 OB Confluence + ADX > 50',
        convictionAtEntry: 78,
      },
      delay: 300,
    },
    { token: '\n✓ Order placed. Monitoring for SL/TP events.', delay: 80 },
  ],

  // Scenario 2 — Regime shift to Ranging/Short
  [
    { token: '## XAUUSD Regime Analysis\n\n', delay: 80 },
    { token: 'Significant **regime shift detected**. ', delay: 70 },
    { token: 'Price action has been compressing for 4 consecutive H1 candles.\n\n', delay: 90 },
    {
      telemetry: { score: 22, regime: 'RANGING' as MarketRegime, rsiSignal: 51, adxStrength: 18 },
      delay: 200,
    },
    { token: '- ADX: **18** — trend exhausted. Ranging market confirmed.\n', delay: 80 },
    { token: '- Bollinger Band squeeze in progress.\n', delay: 80 },
    { token: '- RSI oscillating between 45–55. No directional bias.\n\n', delay: 100 },
    { token: 'Standing down from entry signals. ', delay: 70 },
    { token: '**Conviction score below threshold** (22% < 75%).\n\n', delay: 90 },
    { token: 'Awaiting **breakout confirmation** or **news catalyst**…', delay: 100 },
  ],

  // Scenario 3 — High Volatility Breakout Short
  [
    { token: '## ⚡ Volatility Breakout Detected\n\n', delay: 80 },
    { token: '**XAUUSD** has broken out of the daily consolidation range. ', delay: 70 },
    { token: 'ATR has spiked to **6.2** (ceiling: 4.5). ', delay: 80 },
    { token: 'This exceeds our ATR ceiling gate.\n\n', delay: 90 },
    {
      telemetry: { score: 14, regime: 'HIGH_VOLATILITY_BREAKOUT' as MarketRegime, rsiSignal: 81, adxStrength: 72 },
      delay: 250,
    },
    { token: '⚠️ **Standby mode engaged**. ', delay: 80 },
    { token: 'RSI is extremly overbought at **81.4**. ', delay: 70 },
    { token: 'Risk of sharp reversal is elevated.\n\n', delay: 90 },
    { token: 'Monitoring for RSI divergence and pin bar reversal signal.\n\n', delay: 100 },
    {
      telemetry: { score: 67, regime: 'TRENDING_BEAR' as MarketRegime, rsiSignal: 76, adxStrength: 68 },
      delay: 400,
    },
    { token: 'Reversal signal forming. **Bearish engulfing** on 15M. ', delay: 80 },
    { token: 'RSI divergence confirmed.\n\n', delay: 70 },
    { token: '**Short entry criteria met.** Evaluating risk parameters…\n', delay: 90 },
    { token: '- Entry: **3352.10**\n- SL: **3372.00** (19.9 point risk)\n- TP: **3310.00** (2.1R)\n\n', delay: 120 },
    {
      telemetry: { score: 82, regime: 'TRENDING_BEAR' as MarketRegime, rsiSignal: 76, adxStrength: 71 },
      delay: 200,
    },
    { token: '`EXECUTING SHORT ORDER...`\n', delay: 100 },
    {
      execution: {
        symbol: 'XAUUSD',
        direction: 'SHORT',
        entryPrice: 3352.10,
        sl: 3372.00,
        tp: 3310.00,
        volume: 0.04,
        triggerRule: 'Rule C: RSI Divergence + Bearish Engulfing after ATR Spike',
        convictionAtEntry: 82,
      },
      delay: 300,
    },
    { token: '\n✓ Short order placed. Risk:Reward = 1:2.1', delay: 80 },
  ],
];

/* ── Mock feed runner ───────────────────────────────────────────────────────── */
let timeouts: ReturnType<typeof setTimeout>[] = [];
let currentScenario = 0;

function processChunk(chunks: StreamChunk[], index: number): void {
  if (index >= chunks.length) {
    // End of scenario
    useAITelemetryStore.getState().endSession();
    return;
  }

  const chunk = chunks[index];

  const tid = setTimeout(() => {
    const store = useAITelemetryStore.getState();

    if (chunk.token !== undefined) {
      store.appendToken(chunk.token);
    }

    if (chunk.telemetry) {
      store.applyTelemetryBlob(chunk.telemetry);
    }

    if (chunk.execution) {
      const entry: LedgerEntry = {
        ...chunk.execution,
        id: `exec_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        timestamp: Date.now(),
      };
      store.addLedgerEntry(entry);
    }

    processChunk(chunks, index + 1);
  }, chunk.delay);

  timeouts.push(tid);
}

export function startMockAIFeed(): void {
  const chunks = MOCK_SCENARIOS[currentScenario % MOCK_SCENARIOS.length];
  currentScenario++;

  const store = useAITelemetryStore.getState();
  store.startSession(`mock_${Date.now().toString(36)}`);

  processChunk(chunks, 0);
}

export function stopMockAIFeed(): void {
  timeouts.forEach(clearTimeout);
  timeouts = [];
  useAITelemetryStore.getState().endSession();
}

/**
 * Runs all three scenarios automatically cycling with a pause between them.
 * Returns a cleanup function.
 */
export function startCyclicMockFeed(intervalMs = 12000): () => void {
  startMockAIFeed(); // start immediately

  const cycleId = setInterval(() => {
    stopMockAIFeed();
    setTimeout(() => startMockAIFeed(), 1500); // 1.5s gap between runs
  }, intervalMs);

  return () => {
    clearInterval(cycleId);
    stopMockAIFeed();
  };
}
