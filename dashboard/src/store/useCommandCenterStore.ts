/**
 * OpenClaw — XAUUSD Command Center State Store
 * 
 * Zustand-based state management for the Command Center UI.
 * Uses selective subscriptions to prevent unnecessary re-renders
 * during high-frequency WebSocket updates.
 */

import { create } from 'zustand';

/* ================================================================
   Type Definitions
   ================================================================ */

export interface AccountState {
  equity: number;
  balance: number;
  margin: number;
  freeMargin: number;
  dailyPnl: number;
  currency: string;
}

export interface OpenPosition {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  priceOpen: number;
  priceCurrent: number;
  sl: number;
  tp: number;
  profit: number;
  swap: number;
  magic: number;
  comment: string;
}

export interface MarketHeatEntry {
  symbol: string;
  atr: number;
  atrCeiling: number;
  spreadPoints: number;
  dailyChange: number;
  volatilityRank: 'LOW' | 'MODERATE' | 'HIGH' | 'EXTREME';
  lastTick: number;
}

export interface SessionGates {
  londonOpen: boolean;
  nyOverlap: boolean;
  asiaSession: boolean;
  newsBlackout: boolean;
}

export interface EngineConfig {
  aiConfidenceThreshold: number;    // 0-100
  atrCeiling: number;              // e.g., 4.5 for XAUUSD
  sessionGates: SessionGates;
  isEngineHalted: boolean;
  isInStandbyMode: boolean;
  autonomousMode: boolean;
}

export interface CommandCenterStore {
  // --- Live Data ---
  account: AccountState;
  positions: OpenPosition[];
  marketHeat: MarketHeatEntry[];

  // --- Engine Configuration ---
  engineConfig: EngineConfig;

  // --- Connection State ---
  wsConnected: boolean;
  lastHeartbeat: number;

  // --- Actions: Live Data Updates ---
  updateAccount: (account: Partial<AccountState>) => void;
  setPositions: (positions: OpenPosition[]) => void;
  updatePositionPrice: (ticket: number, priceCurrent: number, profit: number) => void;
  setMarketHeat: (heat: MarketHeatEntry[]) => void;

  // --- Actions: Engine Config ---
  setAiConfidenceThreshold: (value: number) => void;
  setAtrCeiling: (value: number) => void;
  toggleSessionGate: (gate: keyof SessionGates) => void;
  setStandbyMode: (active: boolean) => void;

  // --- Actions: Critical ---
  triggerHardHalt: () => void;
  resetHalt: () => void;

  // --- Actions: Connection ---
  setWsConnected: (connected: boolean) => void;
  setLastHeartbeat: (ts: number) => void;
}

/* ================================================================
   Store Implementation
   ================================================================ */

export const useCommandCenterStore = create<CommandCenterStore>((set, get) => ({
  // --- Initial State ---
  account: {
    equity: 0,
    balance: 0,
    margin: 0,
    freeMargin: 0,
    dailyPnl: 0,
    currency: 'USD',
  },
  positions: [],
  marketHeat: [],

  engineConfig: {
    aiConfidenceThreshold: 75,
    atrCeiling: 4.5,
    sessionGates: {
      londonOpen: true,
      nyOverlap: true,
      asiaSession: false,
      newsBlackout: true,
    },
    isEngineHalted: false,
    isInStandbyMode: false,
    autonomousMode: true,
  },

  wsConnected: false,
  lastHeartbeat: 0,

  // --- Live Data Mutations ---
  updateAccount: (partial) =>
    set((state) => ({ account: { ...state.account, ...partial } })),

  setPositions: (positions) =>
    set({ positions }),

  // Granular price update — avoids replacing the entire positions array
  updatePositionPrice: (ticket, priceCurrent, profit) =>
    set((state) => ({
      positions: state.positions.map((p) =>
        p.ticket === ticket ? { ...p, priceCurrent, profit } : p
      ),
    })),

  setMarketHeat: (heat) =>
    set({ marketHeat: heat }),

  // --- Engine Config Mutations ---
  setAiConfidenceThreshold: (value) =>
    set((state) => ({
      engineConfig: { ...state.engineConfig, aiConfidenceThreshold: value },
    })),

  setAtrCeiling: (value) =>
    set((state) => ({
      engineConfig: { ...state.engineConfig, atrCeiling: value },
    })),

  toggleSessionGate: (gate) =>
    set((state) => ({
      engineConfig: {
        ...state.engineConfig,
        sessionGates: {
          ...state.engineConfig.sessionGates,
          [gate]: !state.engineConfig.sessionGates[gate],
        },
      },
    })),

  setStandbyMode: (active) =>
    set((state) => ({
      engineConfig: { ...state.engineConfig, isInStandbyMode: active },
    })),

  // --- Critical Actions ---
  triggerHardHalt: () => {
    set((state) => ({
      engineConfig: {
        ...state.engineConfig,
        isEngineHalted: true,
        isInStandbyMode: true,
      },
    }));
    // The WebSocket service will pick this up and dispatch the payload
  },

  resetHalt: () =>
    set((state) => ({
      engineConfig: {
        ...state.engineConfig,
        isEngineHalted: false,
        isInStandbyMode: false,
      },
    })),

  // --- Connection ---
  setWsConnected: (connected) => set({ wsConnected: connected }),
  setLastHeartbeat: (ts) => set({ lastHeartbeat: ts }),
}));
