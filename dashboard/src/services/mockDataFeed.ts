/**
 * OpenClaw — Mock Data Generator
 *
 * Simulates high-frequency WebSocket updates for development.
 * Fires account, position, and market heat data every 100-500ms
 * to stress test the Zustand subscription model.
 */

import { useCommandCenterStore } from '../store/useCommandCenterStore';

let intervalIds: ReturnType<typeof setInterval>[] = [];

function rand(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

export function startMockDataFeed(): void {
  const store = useCommandCenterStore.getState();

  // Seed the initial account state
  store.updateAccount({
    equity: 4827.35,
    balance: 4650.00,
    margin: 312.40,
    freeMargin: 4514.95,
    dailyPnl: 177.35,
    currency: 'USD',
  });

  // Seed initial positions
  store.setPositions([
    {
      ticket: 88401220,
      symbol: 'XAUUSD',
      type: 'BUY',
      volume: 0.05,
      priceOpen: 3312.45,
      priceCurrent: 3318.72,
      sl: 3298.00,
      tp: 3345.00,
      profit: 31.35,
      swap: -0.42,
      magic: 202604,
      comment: 'OpenClaw',
    },
    {
      ticket: 88401318,
      symbol: 'XAUUSD',
      type: 'BUY',
      volume: 0.03,
      priceOpen: 3315.90,
      priceCurrent: 3318.72,
      sl: 3302.00,
      tp: 3342.00,
      profit: 8.46,
      swap: -0.18,
      magic: 202604,
      comment: 'OpenClaw',
    },
    {
      ticket: 88401455,
      symbol: 'XAUUSD',
      type: 'SELL',
      volume: 0.02,
      priceOpen: 3320.10,
      priceCurrent: 3318.72,
      sl: 3335.00,
      tp: 3295.00,
      profit: 2.76,
      swap: -0.09,
      magic: 202604,
      comment: 'OpenClaw',
    },
  ]);

  // Seed market heat
  store.setMarketHeat([
    { symbol: 'XAUUSD', atr: 3.82, atrCeiling: 4.5, spreadPoints: 18, dailyChange: 0.48, volatilityRank: 'MODERATE', lastTick: 3318.72 },
    { symbol: 'EURUSD', atr: 0.0058, atrCeiling: 0.01, spreadPoints: 1.2, dailyChange: -0.12, volatilityRank: 'LOW', lastTick: 1.1347 },
    { symbol: 'GBPUSD', atr: 0.0072, atrCeiling: 0.012, spreadPoints: 1.8, dailyChange: 0.22, volatilityRank: 'MODERATE', lastTick: 1.3312 },
    { symbol: 'USDJPY', atr: 0.52, atrCeiling: 0.8, spreadPoints: 1.1, dailyChange: -0.31, volatilityRank: 'LOW', lastTick: 142.36 },
    { symbol: 'BTCUSD', atr: 1250, atrCeiling: 2000, spreadPoints: 450, dailyChange: 2.14, volatilityRank: 'HIGH', lastTick: 67245.00 },
  ]);

  // Simulate high-frequency position price ticks (every 150ms)
  const tickInterval = setInterval(() => {
    const { positions } = useCommandCenterStore.getState();
    positions.forEach((pos) => {
      const jitter = rand(-0.8, 0.8);
      const newPrice = +(pos.priceCurrent + jitter).toFixed(2);
      const priceDiff = pos.type === 'BUY'
        ? newPrice - pos.priceOpen
        : pos.priceOpen - newPrice;
      const newProfit = +(priceDiff * pos.volume * 100).toFixed(2);
      store.updatePositionPrice(pos.ticket, newPrice, newProfit);
    });
  }, 150);
  intervalIds.push(tickInterval);

  // Simulate account equity flutter (every 500ms)
  const accountInterval = setInterval(() => {
    const { positions } = useCommandCenterStore.getState();
    const totalProfit = positions.reduce((sum, p) => sum + p.profit, 0);
    store.updateAccount({
      equity: +(4650 + totalProfit).toFixed(2),
      dailyPnl: +totalProfit.toFixed(2),
      freeMargin: +(4650 + totalProfit - 312.40).toFixed(2),
    });
  }, 500);
  intervalIds.push(accountInterval);

  // Simulate market heat ATR jitter (every 800ms)
  const heatInterval = setInterval(() => {
    const { marketHeat } = useCommandCenterStore.getState();
    const updated = marketHeat.map((entry) => {
      const atrJitter = rand(-0.15, 0.15);
      const newAtr = +(entry.atr + atrJitter).toFixed(4);
      const newRank = newAtr > entry.atrCeiling
        ? 'EXTREME' as const
        : newAtr > entry.atrCeiling * 0.8
          ? 'HIGH' as const
          : newAtr > entry.atrCeiling * 0.5
            ? 'MODERATE' as const
            : 'LOW' as const;
      return { ...entry, atr: newAtr, volatilityRank: newRank };
    });
    store.setMarketHeat(updated);

    // Auto-detect standby for XAUUSD
    const gold = updated.find((e) => e.symbol === 'XAUUSD');
    if (gold) {
      const currentConfig = useCommandCenterStore.getState().engineConfig;
      store.setStandbyMode(gold.atr > currentConfig.atrCeiling);
    }
  }, 800);
  intervalIds.push(heatInterval);
}

export function stopMockDataFeed(): void {
  intervalIds.forEach(clearInterval);
  intervalIds = [];
}
