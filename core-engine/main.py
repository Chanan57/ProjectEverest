import asyncio
import json
import websockets
import zmq
import zmq.asyncio
from collections import deque
import time
from ai_engine import GeminiTradeEngine

DATA_BRIDGE_WS_URL = "ws://127.0.0.1:3000/core-feed"
ZMQ_EXECUTION_ADDR = "tcp://127.0.0.1:5556" # Push socket to MT5 executor

class CoreTradingEngine:
    def __init__(self):
        # Asyncio Queue buffers incoming ticks without blocking the event loop
        self.tick_queue = asyncio.Queue()
        self.ai_engine = GeminiTradeEngine()
        
        # Async ZMQ setup for executing trades to MT5
        self.ctx = zmq.asyncio.Context()
        self.exec_socket = self.ctx.socket(zmq.PUSH)
        self.exec_socket.bind(ZMQ_EXECUTION_ADDR)
        
        # State Aggregation
        self.tick_buffer = deque(maxlen=5000) # Rolling window of recent ticks
        self.last_analysis_time = time.time()
        self.ANALYSIS_INTERVAL_SEC = 60 # Only trigger AI every 60 seconds

        # Reference to WS connection to send telemetry back to UI
        self.bridge_ws = None

    async def ingest_ticks(self):
        """
        Connects to the Node.js Data Bridge and streams raw firehose ticks 
        into the asyncio.Queue. This entirely isolates ingestion from AI processing.
        """
        while True:
            try:
                print(f"[INGEST] Connecting to Data Bridge at {DATA_BRIDGE_WS_URL}...")
                async with websockets.connect(DATA_BRIDGE_WS_URL) as ws:
                    self.bridge_ws = ws
                    print("[INGEST] Connected to Data Bridge core-feed.")
                    
                    async for message in ws:
                        try:
                            tick = json.loads(message)
                            if tick.get("type") == "TICK":
                                # Place tick in queue immediately. Non-blocking.
                                await self.tick_queue.put(tick)
                        except json.JSONDecodeError:
                            pass
                            
            except Exception as e:
                print(f"[INGEST] Connection lost: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def process_ticks(self):
        """
        Consumes ticks from the queue sequentially, aggregates them into a state, 
        and decides whether to trigger an AI Analysis check.
        """
        print("[PROCESS] Ready to process ticks.")
        while True:
            # Await blocks until a tick is available, yielding control to the event loop
            tick = await self.tick_queue.get()
            self.tick_buffer.append(tick)
            
            # Non-blocking trigger condition logic
            # E.g. trigger if 60 seconds have passed since last analysis
            current_time = time.time()
            if current_time - self.last_analysis_time >= self.ANALYSIS_INTERVAL_SEC:
                # Trigger analysis in the background via create_task!
                # This guarantees the loop immediately goes back to processing the next tick.
                asyncio.create_task(self.trigger_ai_analysis())
                self.last_analysis_time = current_time
            
            # Mark the tick as processed
            self.tick_queue.task_done()

    async def trigger_ai_analysis(self):
        """
        Aggregates recent state, calls the LLM asynchronously, routes reasoning 
        telemetry back to the UI, and pushes execution commands to MT5 if warranted.
        """
        print("[ANALYSIS] Triggering AI Analysis Check...")
        
        recent_ticks = list(self.tick_buffer)
        if not recent_ticks: return
        
        # Aggregate the raw ticks into a condensed market state representation
        current_price = recent_ticks[-1].get("bid", 0)
        market_state = {
            "current_price": current_price,
            "tick_volume_in_window": len(recent_ticks),
            "volatility_state": "High" if len(recent_ticks) > 1000 else "Normal"
        }
        
        risk_params = {
            "max_drawdown_pct": 2.0,
            "max_exposure": 100000,
            "current_open_positions": 0
        }

        # 1. Ask Gemini for the decision (runs in thread pool, doesn't block loop)
        decision = await self.ai_engine.analyze_market_state(market_state, risk_params)
        
        # 2. Route reasoning back to Node.js Data Bridge for the UI Hunt Log
        if self.bridge_ws and not self.bridge_ws.closed:
            telemetry_payload = {
                "type": "AI_TELEMETRY",
                "action": decision.action,
                "conviction": decision.conviction,
                "regime": decision.regime,
                "reasoning": decision.reasoning
            }
            try:
                # Fire and forget telemetry update
                asyncio.create_task(self.bridge_ws.send(json.dumps(telemetry_payload)))
            except Exception as e:
                print(f"[TELEMETRY] Failed to send: {e}")

        # 3. Route Execution to MT5
        if decision.action in ["BUY", "SELL"] and decision.conviction >= 80:
            print(f"[EXECUTION] High conviction {decision.action} ({decision.conviction}%)! Routing to MT5.")
            exec_payload = {
                "action": decision.action,
                "symbol": "XAUUSD",
                "price": current_price,
                "reason": decision.reasoning
            }
            # Push securely over ZMQ to the MT5 executor service
            await self.exec_socket.send_json(exec_payload)
        else:
            print(f"[ANALYSIS] Action: {decision.action} ({decision.conviction}%). Standing by.")

    async def run(self):
        print("Starting BullionHunter Core Trading Engine (Async Mode)...")
        # Run ingestion and processing loops concurrently
        await asyncio.gather(
            self.ingest_ticks(),
            self.process_ticks()
        )

if __name__ == "__main__":
    engine = CoreTradingEngine()
    try:
        # Boot up the asyncio event loop
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print("Engine shutting down gracefully.")
