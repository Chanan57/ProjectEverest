import asyncio
import json
import time
import MetaTrader5 as mt5
import zmq
import zmq.asyncio
import websockets

ZMQ_LISTEN_ADDR = "tcp://127.0.0.1:5556"
DATA_BRIDGE_WS_URL = "ws://127.0.0.1:3000/core-feed"

class MT5Executor:
    def __init__(self):
        # ZeroMQ context for pulling execution commands
        self.ctx = zmq.asyncio.Context()
        self.receiver = self.ctx.socket(zmq.PULL)
        self.receiver.bind(ZMQ_LISTEN_ADDR)
        
        self.bridge_ws = None
        self.max_retries = 3

    async def connect_bridge(self):
        """
        Maintains a persistent WebSocket connection to the Node.js Data Bridge
        strictly for sending execution telemetry and system logs back to the UI.
        """
        while True:
            try:
                self.bridge_ws = await websockets.connect(DATA_BRIDGE_WS_URL)
                print(f"[TELEMETRY] Connected to Data Bridge at {DATA_BRIDGE_WS_URL}")
                
                # Keep connection alive with pings
                while True:
                    await self.bridge_ws.ping()
                    await asyncio.sleep(10)
            except Exception as e:
                print(f"[TELEMETRY] Connection failed: {e}. Reconnecting in 5s...")
                self.bridge_ws = None
                await asyncio.sleep(5)

    async def send_telemetry(self, payload):
        """Helper to fire-and-forget JSON payloads to the bridge."""
        if self.bridge_ws and not self.bridge_ws.closed:
            try:
                await self.bridge_ws.send(json.dumps(payload))
            except Exception as e:
                print(f"[TELEMETRY] Failed to send: {e}")

    def initialize_mt5(self):
        print("[MT5] Initializing MetaTrader 5...")
        if not mt5.initialize():
            print(f"[MT5] initialize() failed, error code: {mt5.last_error()}")
            return False
            
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            print("[MT5] Failed to get terminal info.")
            return False
            
        # Strict pre-flight checks
        if not terminal_info.trade_allowed:
            print("[MT5] CRITICAL ERROR: Auto-trading is disabled in MT5!")
            return False
            
        if not terminal_info.connected:
            print("[MT5] CRITICAL ERROR: MT5 is not connected to the broker!")
            return False
            
        print("[MT5] Terminal initialized and connected securely.")
        return True

    def execute_order(self, command):
        """
        Synchronous MT5 execution logic heavily wrapped to handle 
        XAUUSD requotes, slippage, and immediate failures.
        """
        action = command.get("action")
        symbol = command.get("symbol", "XAUUSD")
        lot_size = command.get("lot_size", 0.1)
        sl = command.get("stop_loss", 0.0)
        tp = command.get("take_profit", 0.0)
        
        if not mt5.symbol_select(symbol, True):
            return {"status": "ERROR", "message": f"Symbol {symbol} not found or invisible in Market Watch"}

        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        
        start_time = time.time()

        for attempt in range(1, self.max_retries + 1):
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return {"status": "ERROR", "message": "Failed to retrieve tick data for pricing"}
                
            price = tick.ask if action == "BUY" else tick.bid
            
            print(f"[MT5] Attempt {attempt} to execute {action} on {symbol} at {price}...")
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lot_size),
                "type": order_type,
                "price": price,
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20, # Slippage tolerance in points
                "magic": 234000,
                "comment": "BullionHunter AI",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC, # Immediate or Cancel
            }

            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                latency = int((time.time() - start_time) * 1000)
                print(f"[MT5] SUCCESS! Ticket: {result.order}, Fill Price: {result.price}, Latency: {latency}ms")
                return {
                    "status": "SUCCESS",
                    "ticket": result.order,
                    "fill_price": result.price,
                    "latency_ms": latency,
                    "action": action,
                    "symbol": symbol,
                    "ruleTrigger": command.get("reason", "AI Strategy Execution")
                }
                
            # Handle standard slippage / requote failures by looping
            elif result.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED]:
                print(f"[MT5] Price moved (Retcode {result.retcode}). Recalculating...")
                time.sleep(0.5) 
                continue
                
            # Hard failures (insufficient margin, limits, etc.)
            else:
                print(f"[MT5] FAILED. Retcode: {result.retcode}, Comment: {result.comment}")
                return {
                    "status": "ERROR",
                    "retcode": result.retcode,
                    "message": result.comment
                }
                
        return {"status": "ERROR", "message": f"Max retries ({self.max_retries}) exceeded due to extreme slippage"}

    async def listen_for_commands(self):
        print(f"[ZMQ] Listening for execution commands on {ZMQ_LISTEN_ADDR}...")
        while True:
            try:
                # Blocks here until a JSON payload arrives via ZMQ PUSH from Core Engine
                msg = await self.receiver.recv_json()
                print(f"\n[ZMQ] Received Command: {msg}")
                
                # Execute (MT5 library must run synchronously in main thread)
                exec_result = self.execute_order(msg)
                
                # Push Telemetry back to Node.js Bridge -> React UI
                if exec_result["status"] == "SUCCESS":
                    strike_payload = {
                        "type": "STRIKE_CONFIRMATION",
                        "strike": {
                            "id": str(exec_result["ticket"]),
                            "type": exec_result["action"],
                            "entryPrice": exec_result["fill_price"],
                            "stopLoss": msg.get("stop_loss", 0.0),
                            "takeProfit": msg.get("take_profit", 0.0),
                            "ruleTrigger": exec_result["ruleTrigger"],
                            "timestamp": time.time(),
                            "latencyMs": exec_result["latency_ms"]
                        }
                    }
                    await self.send_telemetry(strike_payload)
                    
                    await self.send_telemetry({
                        "type": "SYSTEM_LOG",
                        "level": "SUCCESS",
                        "message": f"MT5: Order #{exec_result['ticket']} filled at {exec_result['fill_price']} in {exec_result['latency_ms']}ms"
                    })
                else:
                    await self.send_telemetry({
                        "type": "SYSTEM_LOG",
                        "level": "ERROR",
                        "message": f"MT5 Execution Failed: {exec_result['message']}"
                    })
                    
            except Exception as e:
                print(f"[CRITICAL] Failure in execution loop: {e}")
                await self.send_telemetry({
                    "type": "SYSTEM_LOG",
                    "level": "ERROR",
                    "message": f"MT5 Executor Crash: {str(e)}"
                })

    async def run(self):
        if not self.initialize_mt5():
            print("[MT5] Execution script halted due to failed initialization.")
            return
            
        await asyncio.gather(
            self.connect_bridge(),
            self.listen_for_commands()
        )

if __name__ == "__main__":
    print("Starting MT5 Executor Microservice...")
    executor = MT5Executor()
    try:
        asyncio.run(executor.run())
    except KeyboardInterrupt:
        print("\n[MT5] Shutting down executor gracefully...")
    finally:
        mt5.shutdown()
