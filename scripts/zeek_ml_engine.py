# scripts/zeek_ml_engine.py - Complete Specialized ML engine for Zeek network logs

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
import math
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path
from collections import Counter
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class ZeekMLEngine:
    """Specialized ML engine for Zeek network logs"""
    
    def __init__(self, model_dir: Union[str, Path]):
        self.model_dir = str(model_dir)  # Convert to string
        self.zeek_embedder = None
        self.zeek_classifier = None
        self.network_scaler = None
        self.protocol_patterns = self._load_protocol_patterns()
        self.baseline_stats = self._load_baseline_stats()
        self.zeek_sources = [
            'conn.log', 'dns.log', 'http.log', 'ssl.log', 'weird.log', 
            'files.log', 'dhcp.log', 'quic.log', 'notice.log', 'stats.log',
            'telemetry.log', 'capture_loss.log'
        ]
        
        # Initialize components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize ML components for Zeek processing"""
        try:
            # Create model directory if it doesn't exist
            os.makedirs(self.model_dir, exist_ok=True)
            
            # Initialize lightweight embedder (could be replaced with custom network embedder)
            logger.info("Initializing Zeek ML components...")
            
            # For now, we'll use rule-based approach with simple ML backing
            # This can be enhanced with proper ML models trained on network data
            
            logger.info("Zeek ML components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Zeek ML components: {e}")
            
    def is_zeek_source(self, source: str) -> bool:
        """Check if the log source is from Zeek"""
        return any(zeek_src in source.lower() for zeek_src in self.zeek_sources)
        
    def _load_protocol_patterns(self) -> Dict:
        """Load known protocol patterns and IoT signatures"""
        return {
            'legitimate_iot': [
                'mi-connect', 'airplay', 'chromecast', 'homekit', 'upnp',
                'mdns', 'ssdp', 'dlna', 'smartthings', 'alexa', 'google-home',
                'nest-', 'ring-', 'philips-hue', 'samsung-tv', 'lg-tv',
                'roku-', 'fire-tv', 'apple-tv'
            ],
            'legitimate_services': [
                'microsoft.com', 'google.com', 'apple.com', 'cloudflare.com',
                'amazonaws.com', 'office.com', 'live.com', 'outlook.com',
                'github.com', 'stackoverflow.com', 'ubuntu.com', 'mozilla.org',
                'wikipedia.org', 'netflix.com', 'youtube.com', 'spotify.com'
            ],
            'suspicious_patterns': [
                'dga', 'base64', 'powershell', 'cmd.exe', 'tor-exit',
                'mining-pool', 'c2-beacon', 'data-exfil', 'botnet',
                'malware', 'phishing', 'ransomware', 'trojan', 'exploit'
            ],
            'internal_networks': [
                '192.168.', '10.', '172.16.', '172.17.', '172.18.', 
                '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
                '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
                '172.29.', '172.30.', '172.31.', 'fe80::', 'fc00::', 'fd00::'
            ]
        }
    
    def _load_baseline_stats(self) -> Dict:
        """Load network baseline statistics for anomaly detection"""
        baseline_file = os.path.join(self.model_dir, 'zeek_baseline.json')
        if os.path.exists(baseline_file):
            try:
                with open(baseline_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load baseline stats: {e}")
                
        return self._create_default_baseline()
    
    def _create_default_baseline(self) -> Dict:
        """Create default baseline for network behavior"""
        return {
            'conn_duration': {'mean': 5.0, 'std': 10.0, 'max_normal': 3600},
            'dns_query_length': {'mean': 15.0, 'std': 10.0, 'max_normal': 100},
            'http_uri_length': {'mean': 50.0, 'std': 30.0, 'max_normal': 500},
            'bytes_transferred': {'mean': 1024, 'std': 5000, 'max_normal': 100000},
            'common_ports': [80, 443, 22, 21, 25, 53, 993, 995, 143, 110, 5353],
            'safe_domains': ['local', '.lan', '.corp', '.internal'],
            'normal_protocols': ['tcp', 'udp', 'icmp', 'http', 'https', 'dns', 'dhcp']
        }
    
    def extract_zeek_features(self, log_line: str, source: str) -> Dict:
        """Extract numerical features from Zeek logs for ML processing"""
        features = {
            'duration': 0.0,
            'orig_bytes': 0,
            'resp_bytes': 0,
            'port_score': 0.0,
            'domain_entropy': 0.0,
            'is_local': 0,
            'protocol_score': 0.0,
            'time_of_day': 0.0,
            'query_length': 0,
            'connection_state_score': 0.0
        }
        
        try:
            parts = log_line.split('\t')
            
            # Extract timestamp for time-based features
            if len(parts) > 0:
                try:
                    timestamp = float(parts[0])
                    dt = datetime.fromtimestamp(timestamp)
                    features['time_of_day'] = dt.hour / 24.0  # Normalize to 0-1
                except:
                    features['time_of_day'] = 0.5  # Default to noon
            
            if 'conn.log' in source and len(parts) >= 15:
                features.update(self._extract_conn_features(parts))
            elif 'dns.log' in source and len(parts) >= 10:
                features.update(self._extract_dns_features(parts))
            elif 'http.log' in source and len(parts) >= 12:
                features.update(self._extract_http_features(parts))
            elif 'ssl.log' in source and len(parts) >= 10:
                features.update(self._extract_ssl_features(parts))
                
        except Exception as e:
            logger.debug(f"Feature extraction failed for {source}: {e}")
            
        return features
    
    def _extract_conn_features(self, parts: List[str]) -> Dict:
        """Extract features from conn.log"""
        features = {}
        try:
            # Duration (index 8)
            duration = float(parts[8]) if parts[8] != '-' else 0.0
            features['duration'] = min(duration, 3600)  # Cap at 1 hour
            
            # Bytes (indices 9, 10)
            features['orig_bytes'] = int(parts[9]) if parts[9] != '-' else 0
            features['resp_bytes'] = int(parts[10]) if parts[10] != '-' else 0
            
            # Port analysis (index 5 - destination port)
            dst_port = int(parts[5]) if parts[5].isdigit() else 0
            features['port_score'] = 1.0 if dst_port in self.baseline_stats['common_ports'] else 0.5
            
            # Connection state analysis (index 11)
            conn_state = parts[11] if len(parts) > 11 else ""
            features['connection_state_score'] = self._score_connection_state(conn_state)
            
            # Local vs external (indices 2, 4 - source and dest IPs)
            src_ip, dst_ip = parts[2], parts[4]
            features['is_local'] = 1 if self._is_internal_traffic(src_ip, dst_ip) else 0
            
        except Exception as e:
            logger.debug(f"Conn feature extraction error: {e}")
            
        return features
    
    def _extract_dns_features(self, parts: List[str]) -> Dict:
        """Extract features from dns.log"""
        features = {}
        try:
            # Query (index 8)
            query = parts[8] if len(parts) > 8 else ""
            
            # Domain entropy (randomness indicator)
            features['domain_entropy'] = self._calculate_entropy(query)
            
            # Query length
            features['query_length'] = len(query)
            
            # Protocol legitimacy score
            features['protocol_score'] = self._score_dns_query(query)
            
            # Response code analysis (index 14)
            if len(parts) > 14:
                rcode = parts[14]
                features['dns_response_score'] = 1.0 if rcode == 'NOERROR' else 0.5
            
        except Exception as e:
            logger.debug(f"DNS feature extraction error: {e}")
            
        return features
    
    def _extract_http_features(self, parts: List[str]) -> Dict:
        """Extract features from http.log"""
        features = {}
        try:
            # HTTP method (index 6)
            method = parts[6] if len(parts) > 6 else ""
            features['http_method_score'] = 1.0 if method in ['GET', 'POST', 'HEAD'] else 0.5
            
            # Host (index 7)
            host = parts[7] if len(parts) > 7 else ""
            features['domain_entropy'] = self._calculate_entropy(host)
            features['protocol_score'] = self._score_domain(host)
            
            # URI (index 8)
            uri = parts[8] if len(parts) > 8 else ""
            features['query_length'] = len(uri)
            
            # Response code (index 11)
            if len(parts) > 11:
                status_code = parts[11]
                if status_code.isdigit():
                    code = int(status_code)
                    features['http_status_score'] = 1.0 if 200 <= code < 400 else 0.5
            
        except Exception as e:
            logger.debug(f"HTTP feature extraction error: {e}")
            
        return features
    
    def _extract_ssl_features(self, parts: List[str]) -> Dict:
        """Extract features from ssl.log"""
        features = {}
        try:
            # SSL version (index 6)
            version = parts[6] if len(parts) > 6 else ""
            features['ssl_version_score'] = 1.0 if 'TLS' in version else 0.5
            
            # Server name (index 8)
            if len(parts) > 8:
                server_name = parts[8]
                features['domain_entropy'] = self._calculate_entropy(server_name)
                features['protocol_score'] = self._score_domain(server_name)
            
        except Exception as e:
            logger.debug(f"SSL feature extraction error: {e}")
            
        return features
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy for randomness detection"""
        if not text:
            return 0.0
        
        try:
            counts = Counter(text.lower())
            length = len(text)
            entropy = -sum((count/length) * math.log2(count/length) 
                          for count in counts.values())
            return entropy
        except:
            return 0.0
    
    def _score_dns_query(self, query: str) -> float:
        """Score DNS query legitimacy"""
        if not query:
            return 0.5
            
        query_lower = query.lower()
        
        # Check for legitimate patterns
        if any(pattern in query_lower for pattern in self.protocol_patterns['legitimate_services']):
            return 0.9  # High legitimacy
        
        if any(pattern in query_lower for pattern in self.protocol_patterns['legitimate_iot']):
            return 0.8  # IoT legitimacy
            
        if query_lower.endswith('.local') or any(safe in query_lower for safe in self.baseline_stats['safe_domains']):
            return 0.7  # mDNS/local legitimacy
            
        # Check for suspicious patterns
        if any(pattern in query_lower for pattern in self.protocol_patterns['suspicious_patterns']):
            return 0.1  # Suspicious
            
        # Default scoring based on entropy and length
        entropy = self._calculate_entropy(query)
        if entropy > 4.0 and len(query) > 20:
            return 0.2  # High entropy = suspicious
        elif entropy < 2.0:
            return 0.6  # Low entropy = likely legitimate
        else:
            return 0.5  # Neutral
    
    def _score_domain(self, domain: str) -> float:
        """Score domain legitimacy for HTTP/SSL"""
        if not domain:
            return 0.5
            
        domain_lower = domain.lower()
        
        # Legitimate services
        if any(service in domain_lower for service in self.protocol_patterns['legitimate_services']):
            return 0.9
            
        # Check for suspicious patterns
        if any(suspicious in domain_lower for suspicious in self.protocol_patterns['suspicious_patterns']):
            return 0.1
            
        # Entropy-based scoring
        entropy = self._calculate_entropy(domain)
        if entropy > 4.0:
            return 0.3  # High entropy domains are suspicious
        elif entropy < 2.5:
            return 0.7  # Low entropy is more legitimate
        else:
            return 0.5
    
    def _score_connection_state(self, conn_state: str) -> float:
        """Score connection state for suspiciousness"""
        if not conn_state:
            return 0.5
            
        # Normal connection states
        normal_states = ['SF', 'S0', 'REJ', 'RSTO', 'RSTR']  # SF = successful, S0 = attempt, etc.
        
        if conn_state in normal_states:
            return 0.8  # Normal
        elif 'R' in conn_state:  # Reset states
            return 0.6  # Potentially suspicious but common
        else:
            return 0.4  # Unusual states
    
    def _is_internal_traffic(self, src_ip: str, dst_ip: str) -> bool:
        """Check if traffic is internal"""
        for ip in [src_ip, dst_ip]:
            if any(ip.startswith(internal) for internal in self.protocol_patterns['internal_networks']):
                return True
        return False
    
    def predict_zeek_log(self, log_line: str, source: str) -> Tuple[bool, float, str, Dict]:
        """Enhanced prediction specifically for Zeek logs - Returns 4 values to match worker.py"""

        # Skip Zeek headers
        if log_line.startswith('#'):
            return False, 0.05, "Normal", {'reason': 'Zeek header line', 'type': 'header'}

        # Extract features
        features = self.extract_zeek_features(log_line, source)

        # Protocol-specific analysis
        if 'dns.log' in source:
            return self._predict_dns_log(log_line, features)
        elif 'conn.log' in source:
            return self._predict_conn_log(log_line, features)
        elif 'http.log' in source:
            return self._predict_http_log(log_line, features)
        elif 'ssl.log' in source:
            return self._predict_ssl_log(log_line, features)
        elif 'weird.log' in source or 'notice.log' in source:
            return self._predict_alert_log(log_line, features, source)
        else:
            return self._predict_generic_zeek(log_line, features, source)

    def _predict_dns_log(self, log_line: str, features: Dict) -> Tuple[bool, float, str, Dict]:
        """Specialized DNS log prediction - Returns (is_anomaly, risk_score, verdict, details)"""
        protocol_score = features.get('protocol_score', 0.5)
        domain_entropy = features.get('domain_entropy', 0.0)
        query_length = features.get('query_length', 0)

        # Extract query for analysis
        parts = log_line.split('\t')
        query = parts[8] if len(parts) > 8 else ""

        # High confidence normal for known good patterns
        if protocol_score >= 0.7:
            return (False, 0.05, "Normal", {
                'reason': 'Legitimate DNS pattern', 
                'protocol_score': protocol_score,
                'query': query[:50]
            })

        # High confidence anomaly for suspicious patterns  
        if protocol_score <= 0.2 or domain_entropy > 4.5:
            return (True, 0.85, "Anomaly", {
                'reason': 'Suspicious DNS pattern', 
                'entropy': domain_entropy,
                'query': query[:50]
            })

        # Check for DGA (Domain Generation Algorithm) patterns
        if domain_entropy > 3.5 and query_length > 15 and '.' in query:
            return (True, 0.75, "Anomaly", {
                'reason': 'Possible DGA domain',
                'entropy': domain_entropy,
                'query': query[:50]
            })

        # Default to normal for DNS queries
        return (False, 0.2, "Normal", {
            'reason': 'Standard DNS query', 
            'protocol_score': protocol_score,
            'query': query[:50]
        })

    def _predict_conn_log(self, log_line: str, features: Dict) -> Tuple[bool, float, str, Dict]:
        """Specialized connection log prediction - Returns (is_anomaly, risk_score, verdict, details)"""
        duration = features.get('duration', 0.0)
        orig_bytes = features.get('orig_bytes', 0)
        resp_bytes = features.get('resp_bytes', 0)
        is_local = features.get('is_local', 0)
        port_score = features.get('port_score', 0.5)
        conn_state_score = features.get('connection_state_score', 0.5)

        # Extract connection details
        parts = log_line.split('\t')
        src_ip = parts[2] if len(parts) > 2 else ""
        dst_port = parts[5] if len(parts) > 5 else ""
        conn_state = parts[11] if len(parts) > 11 else ""

        # Very short-lived connections with data transfer (potential scanning)
        if duration < 0.1 and (orig_bytes > 0 or resp_bytes > 0):
            return (True, 0.7, "Anomaly", {
                'reason': 'Very short connection with data transfer',
                'duration': duration,
                'bytes': f"{orig_bytes}/{resp_bytes}"
            })

        # Large data transfers to unusual ports
        total_bytes = orig_bytes + resp_bytes
        if total_bytes > 100000 and port_score < 0.6:
            return (True, 0.75, "Anomaly", {
                'reason': 'Large data transfer to unusual port',
                'bytes': total_bytes,
                'port': dst_port
            })

        # External connections with connection issues
        if is_local == 0 and conn_state_score < 0.5:
            return (True, 0.6, "Anomaly", {
                'reason': 'External connection with issues',
                'conn_state': conn_state,
                'dst_port': dst_port
            })

        # Normal internal traffic
        if is_local == 1 and port_score > 0.7:
            return (False, 0.1, "Normal", {
                'reason': 'Normal internal network traffic',
                'port': dst_port
            })

        # Default normal
        return (False, 0.2, "Normal", {
            'reason': 'Standard network connection',
            'duration': duration,
            'port': dst_port
        })

    def _predict_http_log(self, log_line: str, features: Dict) -> Tuple[bool, float, str, Dict]:
        """Specialized HTTP log prediction - Returns (is_anomaly, risk_score, verdict, details)"""
        protocol_score = features.get('protocol_score', 0.5)
        domain_entropy = features.get('domain_entropy', 0.0)
        query_length = features.get('query_length', 0)

        parts = log_line.split('\t')
        method = parts[6] if len(parts) > 6 else ""
        host = parts[7] if len(parts) > 7 else ""
        uri = parts[8] if len(parts) > 8 else ""

        # Suspicious long URIs
        if query_length > 500:
            return (True, 0.7, "Anomaly", {
                'reason': 'Extremely long HTTP URI',
                'uri_length': query_length,
                'host': host[:30]
            })

        # High entropy domains
        if domain_entropy > 4.0:
            return (True, 0.6, "Anomaly", {
                'reason': 'High entropy domain name',
                'entropy': domain_entropy,
                'host': host[:30]
            })

        # Legitimate services
        if protocol_score >= 0.8:
            return (False, 0.1, "Normal", {
                'reason': 'Request to legitimate service',
                'host': host[:30],
                'method': method
            })

        return (False, 0.3, "Normal", {
            'reason': 'Standard HTTP request',
            'host': host[:30],
            'method': method
        })

    def _predict_ssl_log(self, log_line: str, features: Dict) -> Tuple[bool, float, str, Dict]:
        """Specialized SSL log prediction - Returns (is_anomaly, risk_score, verdict, details)"""
        protocol_score = features.get('protocol_score', 0.5)
        domain_entropy = features.get('domain_entropy', 0.0)

        parts = log_line.split('\t')
        server_name = parts[8] if len(parts) > 8 else ""

        # High entropy server names
        if domain_entropy > 4.0:
            return (True, 0.6, "Anomaly", {
                'reason': 'High entropy SSL server name',
                'entropy': domain_entropy,
                'server': server_name[:30]
            })

        # Legitimate services
        if protocol_score >= 0.8:
            return (False, 0.1, "Normal", {
                'reason': 'SSL to legitimate service',
                'server': server_name[:30]
            })

        return (False, 0.2, "Normal", {
            'reason': 'Standard SSL connection',
            'server': server_name[:30]
        })

    def _predict_alert_log(self, log_line: str, features: Dict, source: str) -> Tuple[bool, float, str, Dict]:
        """Handle weird.log and notice.log (Zeek's built-in alerts) - Returns (is_anomaly, risk_score, verdict, details)"""

        # Zeek's weird.log and notice.log are inherently suspicious
        return (True, 0.9, "Zeek Alert", {
            'reason': f'Zeek built-in alert from {source}',
            'type': 'zeek_alert',
            'content': log_line[:100]
        })

    def _predict_generic_zeek(self, log_line: str, features: Dict, source: str) -> Tuple[bool, float, str, Dict]:
        """Generic Zeek log prediction for other log types - Returns (is_anomaly, risk_score, verdict, details)"""

        # Most generic Zeek logs are informational
        return (False, 0.2, "Normal", {
            'reason': f'Generic Zeek log from {source}',
            'type': 'informational'
        })
    
    def normalize_zeek_for_analysis(self, log_line: str, source: str) -> str:
        """Advanced normalization for better ML understanding"""
        
        if 'dns.log' in source:
            return self._normalize_dns_log(log_line)
        elif 'conn.log' in source:
            return self._normalize_conn_log(log_line)
        elif 'http.log' in source:
            return self._normalize_http_log(log_line)
        elif 'ssl.log' in source:
            return self._normalize_ssl_log(log_line)
        elif 'weird.log' in source or 'notice.log' in source:
            return self._normalize_alert_log(log_line, source)
        else:
            return f"network activity detected in {source}"
    
    def _normalize_dns_log(self, log_line: str) -> str:
        """Advanced DNS log normalization"""
        try:
            parts = log_line.split('\t')
            if len(parts) < 9:
                return "dns query detected"
            
            src_ip = parts[2]
            query = parts[8] if len(parts) > 8 else "unknown"
            
            # Identify query type
            if '.local' in query:
                return f"local network service discovery for {query}"
            elif any(iot in query.lower() for iot in self.protocol_patterns['legitimate_iot']):
                return f"smart device service discovery {query}"
            elif any(service in query.lower() for service in self.protocol_patterns['legitimate_services']):
                return f"legitimate service lookup {query}"
            elif self._calculate_entropy(query) > 4.0:
                return f"suspicious high-entropy dns query {query[:20]}"
            else:
                return f"dns query for {query}"
                
        except Exception as e:
            return "dns network activity"
    
    def _normalize_conn_log(self, log_line: str) -> str:
        """Normalize connection logs"""
        try:
            parts = log_line.split('\t')
            if len(parts) < 7:
                return "network connection detected"
            
            src_ip, dst_ip = parts[2], parts[4]
            dst_port = parts[5]
            proto = parts[6]
            
            if self._is_internal_traffic(src_ip, dst_ip):
                return f"internal network connection {src_ip} to {dst_ip} port {dst_port} via {proto}"
            else:
                return f"external network connection {src_ip} to {dst_ip} port {dst_port} via {proto}"
                
        except Exception as e:
            return "network connection activity"
    
    def _normalize_http_log(self, log_line: str) -> str:
        """Normalize HTTP logs"""
        try:
            parts = log_line.split('\t')
            if len(parts) < 9:
                return "http request detected"
            
            src_ip = parts[2]
            method = parts[6] if len(parts) > 6 else "GET"
            host = parts[7] if len(parts) > 7 else "unknown"
            uri = parts[8] if len(parts) > 8 else "/"
            
            return f"http request {method} {host}{uri[:50]} from {src_ip}"
                
        except Exception as e:
            return "http web traffic"
    
    def _normalize_ssl_log(self, log_line: str) -> str:
        """Normalize SSL logs"""
        try:
            parts = log_line.split('\t')
            if len(parts) < 6:
                return "ssl connection detected"
            
            src_ip, dst_ip = parts[2], parts[4]
            server_name = parts[8] if len(parts) > 8 else "unknown"
            
            return f"ssl connection from {src_ip} to {server_name} ({dst_ip})"
                
        except Exception as e:
            return "ssl encrypted connection"
    
    def _normalize_alert_log(self, log_line: str, source: str) -> str:
        """Normalize Zeek alert logs"""
        try:
            parts = log_line.split('\t')
            
            if 'weird.log' in source:
                weird_type = parts[6] if len(parts) > 6 else "unknown"
                return f"network anomaly detected: {weird_type}"
            elif 'notice.log' in source:
                notice_type = parts[6] if len(parts) > 6 else "unknown"
                return f"zeek security notice: {notice_type}"
            else:
                return f"zeek alert from {source}"
                
        except Exception as e:
            return f"zeek security alert from {source}"
    
    def save_model_state(self):
        """Save current model state and statistics"""
        try:
            state_file = os.path.join(self.model_dir, 'zeek_engine_state.json')
            state = {
                'protocol_patterns': self.protocol_patterns,
                'baseline_stats': self.baseline_stats,
                'last_updated': datetime.now().isoformat(),
                'version': '1.0.0'
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            logger.info(f"Zeek engine state saved to {state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save Zeek engine state: {e}")
    
    def load_model_state(self):
        """Load saved model state"""
        try:
            state_file = os.path.join(self.model_dir, 'zeek_engine_state.json')
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    
                self.protocol_patterns = state.get('protocol_patterns', self.protocol_patterns)
                self.baseline_stats = state.get('baseline_stats', self.baseline_stats)
                
                logger.info(f"Zeek engine state loaded from {state_file}")
                
        except Exception as e:
            logger.warning(f"Failed to load Zeek engine state: {e}")
    
    def update_baseline_stats(self, new_stats: Dict):
        """Update baseline statistics with new data"""
        try:
            for key, value in new_stats.items():
                if key in self.baseline_stats:
                    self.baseline_stats[key].update(value)
                else:
                    self.baseline_stats[key] = value
            
            # Save updated stats
            self.save_model_state()
            
            logger.info("Baseline statistics updated")
            
        except Exception as e:
            logger.error(f"Failed to update baseline stats: {e}")

# Factory function for easy instantiation
def create_zeek_engine(model_dir: Union[str, Path]) -> ZeekMLEngine:
    """Factory function to create ZeekMLEngine instance"""
    return ZeekMLEngine(model_dir)

# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python zeek_ml_engine.py <model_dir> <test_log_line>")
        sys.exit(1)
    
    model_dir = sys.argv[1]
    test_log = sys.argv[2]
    
    # Create engine
    engine = ZeekMLEngine(model_dir)
    
    # Test prediction
    source = "conn.log"  # Default source
    if len(sys.argv) > 3:
        source = sys.argv[3]
    
    verdict, confidence, details = engine.predict_zeek_log(test_log, source)
    normalized = engine.normalize_zeek_for_analysis(test_log, source)
    
    print(f"Verdict: {verdict}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Details: {details}")
    print(f"Normalized: {normalized}")
