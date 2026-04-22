/**
 * OpenClaw — WebSocket Client Service
 *
 * Singleton WebSocket connection to the data-bridge Node.js backend.
 * Routes incoming messages to the Zustand store and dispatches
 * high-priority commands (like HARD_HALT) back to the core-engine.
 */

import { useCommandCenterStore } from '../store/useCommandCenterStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:3000';
const RECONNECT_INTERVAL_MS = 3000;

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Initialize the WebSocket connection and bind message handlers.
 */
export function connectWebSocket(): void {
  if (socket?.readyState === WebSocket.OPEN) return;

  const store = useCommandCenterStore.getState();
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log('[WS] Connected to data-bridge');
    store.setWsConnected(true);
    store.setLastHeartbeat(Date.now());

    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      routeMessage(msg);
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  socket.onclose = () => {
    console.warn('[WS] Disconnected. Reconnecting...');
    store.setWsConnected(false);
    scheduleReconnect();
  };

  socket.onerror = (err) => {
    console.error('[WS] Error:', err);
    socket?.close();
  };
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, RECONNECT_INTERVAL_MS);
}

/**
 * Route incoming WebSocket messages to the correct store mutations.
 */
function routeMessage(msg: { type: string; payload: unknown }): void {
  const store = useCommandCenterStore.getState();

  switch (msg.type) {
    case 'account_update':
      store.updateAccount(msg.payload as Parameters<typeof store.updateAccount>[0]);
      break;

    case 'positions_snapshot':
      store.setPositions(msg.payload as Parameters<typeof store.setPositions>[0]);
      break;

    case 'position_tick': {
      const tick = msg.payload as { ticket: number; price: number; profit: number };
      store.updatePositionPrice(tick.ticket, tick.price, tick.profit);
      break;
    }

    case 'market_heat':
      store.setMarketHeat(msg.payload as Parameters<typeof store.setMarketHeat>[0]);
      break;

    case 'heartbeat':
      store.setLastHeartbeat(Date.now());
      break;

    case 'engine_status': {
      const status = msg.payload as { halted?: boolean; standby?: boolean };
      if (status.halted !== undefined) {
        status.halted ? store.triggerHardHalt() : store.resetHalt();
      }
      if (status.standby !== undefined) {
        store.setStandbyMode(status.standby);
      }
      break;
    }

    default:
      console.warn('[WS] Unknown message type:', msg.type);
  }
}

/**
 * Send a high-priority command to the core-engine via the data-bridge.
 */
export function sendCommand(type: string, payload: unknown = {}): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    console.error('[WS] Cannot send command — not connected');
    return;
  }

  const message = JSON.stringify({
    type,
    payload,
    timestamp: Date.now(),
    priority: type === 'HARD_HALT' ? 'CRITICAL' : 'NORMAL',
  });

  socket.send(message);
  console.log(`[WS] Sent command: ${type}`);
}

/**
 * Gracefully disconnect the WebSocket.
 */
export function disconnectWebSocket(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
}
