/**
 * OpenClaw — AI Telemetry & Reasoning Hub Store
 *
 * Manages:
 *  - Streaming LLM text buffer (append-only, never triggers full re-renders)
 *  - Conviction score & market regime parsed from AI JSON blobs
 *  - Active execution ledger (cards that appear on trade execution)
 *
 * Performance notes:
 *  - `appendToken` is written so that consumers subscribing ONLY to `convictionScore`
 *    or `ledger` are NOT re-rendered on every token push.
 *  - The terminal component subscribes to a ref-based approach to avoid jitter.
 */

import { create } from 'zustand';

/* ================================================================
   Type Definitions
   ================================================================ */

export type MarketRegime =
  | 'TRENDING_BULL'
  | 'TRENDING_BEAR'
  | 'RANGING'
  | 'HIGH_VOLATILITY_BREAKOUT'
  | 'CONSOLIDATION'
  | 'UNKNOWN';

export interface ConvictionVector {
  score: number;           // 0-100
  regime: MarketRegime;
  rsiSignal: number;       // 0-100 normalised RSI
  adxStrength: number;     // 0-100 normalised ADX
  updatedAt: number;       // epoch ms
}

export interface LedgerEntry {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  sl: number;
  tp: number;
  volume: number;
  triggerRule: string;     // e.g. "Rule A: RSI + EMA Cross Confluence"
  timestamp: number;
  convictionAtEntry: number;
}

export interface StreamSession {
  id: string;
  startedAt: number;
  isActive: boolean;
}

export interface AITelemetryStore {
  // --- Streaming Terminal ---
  /** Full accumulated text of the current session */
  fullText: string;
  /** Whether the LLM is currently streaming */
  isStreaming: boolean;
  /** Current stream session metadata */
  session: StreamSession | null;

  // --- Conviction & Regime Vectors ---
  conviction: ConvictionVector;

  // --- Execution Ledger ---
  ledger: LedgerEntry[];

  // --- Actions ---
  startSession: (id: string) => void;
  appendToken: (token: string) => void;
  /** Called when a complete JSON telemetry blob is parsed from the stream */
  applyTelemetryBlob: (blob: Partial<ConvictionVector>) => void;
  endSession: () => void;
  addLedgerEntry: (entry: LedgerEntry) => void;
  clearLedger: () => void;
  resetSession: () => void;
}

/* ================================================================
   Store Implementation
   ================================================================ */

const DEFAULT_CONVICTION: ConvictionVector = {
  score: 0,
  regime: 'UNKNOWN',
  rsiSignal: 50,
  adxStrength: 20,
  updatedAt: 0,
};

export const useAITelemetryStore = create<AITelemetryStore>((set) => ({
  fullText: '',
  isStreaming: false,
  session: null,
  conviction: DEFAULT_CONVICTION,
  ledger: [],

  startSession: (id) =>
    set({
      session: { id, startedAt: Date.now(), isActive: true },
      isStreaming: true,
      fullText: '',
    }),

  // Core hot path — uses functional update to avoid closure capture issues
  appendToken: (token) =>
    set((state) => ({ fullText: state.fullText + token })),

  applyTelemetryBlob: (blob) =>
    set((state) => ({
      conviction: {
        ...state.conviction,
        ...blob,
        updatedAt: Date.now(),
      },
    })),

  endSession: () =>
    set((state) => ({
      isStreaming: false,
      session: state.session
        ? { ...state.session, isActive: false }
        : null,
    })),

  addLedgerEntry: (entry) =>
    set((state) => ({
      ledger: [entry, ...state.ledger].slice(0, 20), // cap at 20 entries
    })),

  clearLedger: () => set({ ledger: [] }),

  resetSession: () =>
    set({
      fullText: '',
      isStreaming: false,
      session: null,
    }),
}));
