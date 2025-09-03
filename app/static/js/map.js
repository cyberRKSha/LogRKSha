import * as api from './api.js';

let threatMap;

export async function initThreatMap() {
    const mapElement = document.getElementById('threatMap');
    if (!mapElement) return;

    // Initialize the map
    threatMap = L.map('threatMap').setView([20, 0], 2); // Center on the world

    // Add the map tile layer (the actual map image)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(threatMap);

    // Fetch data and plot points
    const locations = await api.fetchAnomalousIPLocations();
    locations.forEach(loc => {
        // Create a pulsing icon for the marker
        const pulsingIcon = L.divIcon({
            className: 'css-icon',
            html: '<div class="gps_ring"></div>',
            iconSize: [20, 20]
        });

        const marker = L.marker([loc.lat, loc.lon], { icon: pulsingIcon }).addTo(threatMap);
        marker.bindPopup(`<b>IP:</b> ${loc.ip}<br><b>Location:</b> ${loc.city}, ${loc.country}`);
    });
}