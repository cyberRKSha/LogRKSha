// import * as ui from './ui.js';

let ws;

export function connectWebSocket(onMessageCallback) {
    ws = new WebSocket("ws://" + window.location.host + "/ws");
    ws.onopen = () => {
        console.log("WebSocket connection established. 🟢");
    };
    ws.onmessage = onMessageCallback;
    ws.onclose = () => { 
        console.log("WebSocket disconnected. Will try to reconnect..."); 
        setTimeout(() => connectWebSocket(onMessageCallback), 5000); };
    ws.onerror = (error) => { 
        console.error("WebSocket error:", error);
        ws.close();
    };
}
