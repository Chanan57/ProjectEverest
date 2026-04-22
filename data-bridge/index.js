const express = require('express');
const { WebSocketServer, WebSocket } = require('ws');
const fs = require('fs');
const yaml = require('js-yaml');
require('dotenv').config({ path: '../.env.example' }); // using example for fallback

const app = express();
const port = process.env.PORT || 3000;

// Load Configuration from single source of truth
let config = {};
try {
    const fileContents = fs.readFileSync('../config.yaml', 'utf8');
    config = yaml.load(fileContents);
} catch (e) {
    console.error('Failed to load config.yaml:', e);
}

app.use(express.json());

// Basic API Route
app.get('/status', (req, res) => {
    res.json({ status: 'Data Bridge Operational', version: '1.0.0' });
});

// Start Server for local Python engine
const server = app.listen(port, () => {
    console.log(`Data Bridge API listening at http://localhost:${port}`);
});

// Configure WebSocket Server (Local hub for Python engine)
const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
    console.log('New Local Client Connected (e.g., Python Engine)');
    
    ws.on('message', (message) => {
        console.log(`Received message from local client: ${message}`);
    });

    ws.send(JSON.stringify({ type: 'WELCOME', message: 'Connected to Project Everest Data Bridge' }));
});

// --- Market Data Provider Connection & Latency Monitor ---

// We mock the provider endpoint (in production, use wss://your-broker-feed.com)
const PROVIDER_URL = 'wss://echo.websocket.events/'; 
let lastTickTime = Date.now();
let providerWs = null;
let deadManTriggered = false;

function connectToProvider() {
    console.log(`Connecting to market data provider: ${PROVIDER_URL}`);
    providerWs = new WebSocket(PROVIDER_URL);

    providerWs.on('open', () => {
        console.log('Connected to market data provider.');
        lastTickTime = Date.now();
        deadManTriggered = false;
        
        // Mock subbing to a feed
        providerWs.send(JSON.stringify({ action: "subscribe", channel: "market_data" }));
        
        // Simulate incoming ticks if echo server doesn't stream 
        // (Just for demonstration)
        setInterval(() => {
            if(providerWs.readyState === WebSocket.OPEN) {
                 providerWs.send(JSON.stringify({ type: "tick", symbol: "EURUSD", price: 1.10 + Math.random() * 0.01 }));
            }
        }, 100); 
    });

    providerWs.on('message', (data) => {
        lastTickTime = Date.now();
        if (deadManTriggered) {
             console.log("Connection recovered. Ticks resuming.");
             deadManTriggered = false;
        }

        // Broadcast tick locally to the Python engine (all connected WebSocket clients)
        wss.clients.forEach((client) => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(data.toString());
            }
        });
    });

    providerWs.on('close', () => {
        console.warn('Market provider connection closed. Attempting reconnect...');
        setTimeout(connectToProvider, 1000);
    });

    providerWs.on('error', (err) => {
        console.error('Market provider WebSocket Error:', err.message);
    });
}

connectToProvider();

// Latency Monitor (Safety Net)
setInterval(() => {
    const latency = Date.now() - lastTickTime;

    if (latency > 5000) {
        if (!deadManTriggered) {
             console.error(`🚨 DEAD-MAN SWITCH TRIGGERED! No tick for ${latency}ms. Connection to market data lost!`);
             // Here you could send a system-wide halt message to the Python engine
             // e.g., wss.clients.forEach(c => c.send(JSON.stringify({type: 'EMERGENCY_HALT'})));
             deadManTriggered = true;
        }
    } else if (latency > 500) {
        console.warn(`⚠️ High Latency Warning: No tick received for ${latency}ms.`);
    }
}, 100); // Check latency every 100ms
