const express = require('express');
const { WebSocketServer } = require('ws');
const zmq = require('zeromq');
const http = require('http');
const throttle = require('lodash.throttle');

// Configurations
const HTTP_PORT = process.env.PORT || 3000;
const MT5_ZMQ_ADDRESS = process.env.MT5_ZMQ_ADDRESS || 'tcp://127.0.0.1:5555';
const ZMQ_TOPIC = 'XAUUSD';

const app = express();
const server = http.createServer(app);

app.get('/status', (req, res) => {
    res.json({ status: 'Data Bridge Operational', version: '2.0.0' });
});

class WebSocketHub {
    constructor(server) {
        // Core feed: Unthrottled for Python Engine
        this.coreWss = new WebSocketServer({ noServer: true });
        // UI feed: Throttled for Next.js frontend
        this.uiWss = new WebSocketServer({ noServer: true });

        server.on('upgrade', (request, socket, head) => {
            const pathname = request.url;
            if (pathname === '/core-feed') {
                this.coreWss.handleUpgrade(request, socket, head, (ws) => {
                    this.coreWss.emit('connection', ws, request);
                });
            } else if (pathname === '/ui-feed') {
                this.uiWss.handleUpgrade(request, socket, head, (ws) => {
                    this.uiWss.emit('connection', ws, request);
                });
            } else {
                socket.destroy();
            }
        });

        this._setupHeartbeats(this.coreWss, 'Core Engine');
        this._setupHeartbeats(this.uiWss, 'UI Client');

        // Throttle UI broadcast to 10 updates per second (100ms) to prevent browser crashes
        this.broadcastToUI = throttle(this._broadcastToUI.bind(this), 100);
    }

    _setupHeartbeats(wss, clientName) {
        wss.on('connection', (ws) => {
            console.log(`[WS] ${clientName} connected`);
            this.logSystemEvent('SUCCESS', `${clientName} connected to WebSocket`);
            ws.isAlive = true;

            ws.on('pong', () => {
                ws.isAlive = true;
            });

            ws.on('close', () => {
                console.log(`[WS] ${clientName} disconnected`);
                this.logSystemEvent('WARN', `${clientName} disconnected from WebSocket`);
            });
        });

        // Ping every 5 seconds
        setInterval(() => {
            wss.clients.forEach((ws) => {
                if (ws.isAlive === false) {
                    console.log(`[WS] Terminating unresponsive ${clientName}`);
                    this.logSystemEvent('ERROR', `Unresponsive ${clientName} connection terminated`);
                    return ws.terminate();
                }
                ws.isAlive = false;
                ws.ping();
            });
        }, 5000);
    }

    broadcastToCore(data) {
        const message = JSON.stringify(data);
        this.coreWss.clients.forEach(client => {
            if (client.readyState === 1) { // OPEN
                client.send(message);
            }
        });
    }

    _broadcastToUI(data) {
        const message = JSON.stringify(data);
        this.uiWss.clients.forEach(client => {
            if (client.readyState === 1) { // OPEN
                client.send(message);
            }
        });
    }

    logSystemEvent(level, message) {
        const event = {
            type: 'SYSTEM_LOG',
            timestamp: new Date().toISOString(),
            level, // 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS'
            message
        };
        // We broadcast system logs immediately to the UI (bypassing the tick throttle if needed)
        // But for simplicity, we can just use the throttled function or a direct send
        const msgStr = JSON.stringify(event);
        this.uiWss.clients.forEach(client => {
            if (client.readyState === 1) client.send(msgStr);
        });
    }
}

class ZmqIngestionLayer {
    constructor(address, topic, wsHub) {
        this.address = address;
        this.topic = topic;
        this.wsHub = wsHub;
        this.sock = new zmq.Subscriber();
        this.reconnectTimeout = 1000;
        this.maxReconnectTimeout = 30000;
        this.isConnected = false;
    }

    async connect() {
        try {
            this.sock.connect(this.address);
            this.sock.subscribe(this.topic);
            this.isConnected = true;
            console.log(`[ZMQ] Connected and subscribed to ${this.topic} at ${this.address}`);
            this.wsHub.logSystemEvent('SUCCESS', `Connected to MT5 ZMQ at ${this.address}`);
            
            // Reset backoff on success
            this.reconnectTimeout = 1000;

            for await (const [topic, message] of this.sock) {
                this.handleMessage(topic.toString(), message.toString());
            }
        } catch (error) {
            this.isConnected = false;
            console.error(`[ZMQ] Connection error:`, error.message);
            this.wsHub.logSystemEvent('ERROR', `MT5 ZMQ Connection lost: ${error.message}`);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        if (this.sock) {
            try { this.sock.close(); } catch(e) {}
            this.sock = new zmq.Subscriber();
        }
        
        console.log(`[ZMQ] Reconnecting in ${this.reconnectTimeout}ms...`);
        setTimeout(() => this.connect(), this.reconnectTimeout);
        
        // Exponential backoff
        this.reconnectTimeout = Math.min(this.reconnectTimeout * 2, this.maxReconnectTimeout);
    }

    handleMessage(topic, message) {
        try {
            // MT5 format expectation: JSON or "Bid|Ask|Volume|Timestamp"
            let parsedData;
            
            if (message.startsWith('{')) {
                parsedData = JSON.parse(message);
            } else {
                const parts = message.split('|');
                if (parts.length >= 4) {
                    parsedData = {
                        symbol: topic,
                        bid: parseFloat(parts[0]),
                        ask: parseFloat(parts[1]),
                        volume: parseInt(parts[2], 10),
                        timestamp: parseInt(parts[3], 10) || Date.now()
                    };
                } else {
                    throw new Error("Invalid payload structure");
                }
            }

            // Data Sanitization: Ensure strictly typed numbers
            if (
                typeof parsedData.bid !== 'number' || isNaN(parsedData.bid) ||
                typeof parsedData.ask !== 'number' || isNaN(parsedData.ask)
            ) {
                throw new Error("Malformed tick data");
            }

            const unifiedTick = {
                type: 'TICK',
                symbol: parsedData.symbol || this.topic,
                bid: parsedData.bid,
                ask: parsedData.ask,
                volume: parsedData.volume || 0,
                timestamp: parsedData.timestamp || Date.now()
            };

            // Broadcast routing
            this.wsHub.broadcastToCore(unifiedTick); // Unthrottled firehose
            this.wsHub.broadcastToUI(unifiedTick);   // Throttled 10fps feed
            
        } catch (error) {
            // Drop malformed packets immediately
        }
    }
}

// Application Bootstrap
const wsHub = new WebSocketHub(server);
const zmqIngestion = new ZmqIngestionLayer(MT5_ZMQ_ADDRESS, ZMQ_TOPIC, wsHub);

server.listen(HTTP_PORT, () => {
    console.log(`[HTTP] Data Bridge Operational on port ${HTTP_PORT}`);
    wsHub.logSystemEvent('INFO', 'Data Bridge Initialized. Waiting for ZMQ stream...');
    
    // Start ZMQ connection asynchronously
    zmqIngestion.connect();
});
