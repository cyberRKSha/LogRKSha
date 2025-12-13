# Create scripts/model_reporter.py - Comprehensive model evaluation and reporting

import os
import json
import pickle
import logging
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_auc_score,
    precision_recall_curve, roc_curve
)
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)

class ModelReporter:
    """Comprehensive model evaluation and reporting system"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "model_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Create dated report directory
        self.current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.report_dir = self.reports_dir / f"report_{self.current_date}"
        self.report_dir.mkdir(exist_ok=True)
        
        self.metrics = {}
        self.predictions = []
        self.model_info = {}
        
    def collect_predictions(self, days_back: int = 7) -> pd.DataFrame:
        """Collect predictions from the database for analysis"""
        try:
            from app.config import settings
            import sqlite3
            
            # Connect to database
            db_path = settings.DATABASE_URL.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            
            # Query predictions from the last N days
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            query = """
            SELECT 
                l.id, l.source, l.log, l.is_anomaly, l.risk_score, 
                l.timestamp, l.verdict, l.sequence_risk,
                a.id as alert_id, a.status as alert_status
            FROM logs l
            LEFT JOIN alerts a ON l.id = a.log_id
            WHERE l.timestamp >= ?
            ORDER BY l.timestamp DESC
            """
            
            df = pd.read_sql_query(query, conn, params=(cutoff_date,))
            conn.close()
            
            logger.info(f"Collected {len(df)} predictions for analysis")
            return df
            
        except Exception as e:
            logger.error(f"Failed to collect predictions: {e}")
            return pd.DataFrame()
    
    def analyze_model_performance(self, df: pd.DataFrame) -> Dict:
        """Analyze model performance across different dimensions"""
        
        if df.empty:
            return {}
        
        analysis = {
            'overall_stats': self._calculate_overall_stats(df),
            'source_breakdown': self._analyze_by_source(df),
            'temporal_analysis': self._analyze_temporal_patterns(df),
            'zeek_specific': self._analyze_zeek_performance(df),
            'alert_analysis': self._analyze_alert_effectiveness(df)
        }
        
        return analysis
    
    def _calculate_overall_stats(self, df: pd.DataFrame) -> Dict:
        """Calculate overall model statistics"""
        
        total_logs = len(df)
        anomalies = df['is_anomaly'].sum()
        normal_logs = total_logs - anomalies
        
        # Basic stats
        stats = {
            'total_logs_processed': total_logs,
            'anomalies_detected': int(anomalies),
            'normal_logs': int(normal_logs),
            'anomaly_rate': float(anomalies / total_logs) if total_logs > 0 else 0.0,
            'average_risk_score': float(df['risk_score'].mean()),
            'high_risk_alerts': int((df['risk_score'] > 0.7).sum()),
        }
        
        # Risk score distribution
        stats['risk_distribution'] = {
            'low_risk_0_0.3': int((df['risk_score'] <= 0.3).sum()),
            'medium_risk_0.3_0.7': int(((df['risk_score'] > 0.3) & (df['risk_score'] <= 0.7)).sum()),
            'high_risk_0.7_1.0': int((df['risk_score'] > 0.7).sum())
        }
        
        return stats
    
    def _analyze_by_source(self, df: pd.DataFrame) -> Dict:
        """Analyze performance by log source"""
        
        source_analysis = {}
        
        for source in df['source'].unique():
            source_df = df[df['source'] == source]
            
            source_analysis[source] = {
                'total_logs': len(source_df),
                'anomalies': int(source_df['is_anomaly'].sum()),
                'anomaly_rate': float(source_df['is_anomaly'].mean()),
                'avg_risk_score': float(source_df['risk_score'].mean()),
                'is_zeek_log': 'zeek' in source.lower() or any(zeek_file in source.lower() 
                                                               for zeek_file in ['conn.log', 'dns.log', 'http.log'])
            }
        
        return source_analysis
    
    def _analyze_zeek_performance(self, df: pd.DataFrame) -> Dict:
        """Specific analysis for Zeek logs"""
        
        # Identify Zeek logs
        zeek_logs = df[df['source'].str.contains('zeek|conn\.log|dns\.log|http\.log|ssl\.log', case=False, na=False)]
        
        if zeek_logs.empty:
            return {'no_zeek_logs': True}
        
        analysis = {
            'zeek_logs_processed': len(zeek_logs),
            'zeek_anomaly_rate': float(zeek_logs['is_anomaly'].mean()),
            'zeek_avg_risk': float(zeek_logs['risk_score'].mean()),
            'by_zeek_type': {}
        }
        
        # Analysis by Zeek log type
        zeek_types = ['conn.log', 'dns.log', 'http.log', 'ssl.log', 'weird.log']
        for log_type in zeek_types:
            type_logs = zeek_logs[zeek_logs['source'].str.contains(log_type, case=False, na=False)]
            if not type_logs.empty:
                analysis['by_zeek_type'][log_type] = {
                    'count': len(type_logs),
                    'anomaly_rate': float(type_logs['is_anomaly'].mean()),
                    'avg_risk': float(type_logs['risk_score'].mean())
                }
        
        return analysis
    
    def _analyze_temporal_patterns(self, df: pd.DataFrame) -> Dict:
        """Analyze temporal patterns in detections"""
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        return {
            'hourly_distribution': df.groupby('hour')['is_anomaly'].agg(['count', 'sum', 'mean']).to_dict('index'),
            'daily_distribution': df.groupby('day_of_week')['is_anomaly'].agg(['count', 'sum', 'mean']).to_dict('index'),
            'peak_anomaly_hour': int(df.groupby('hour')['is_anomaly'].mean().idxmax()),
            'peak_activity_hour': int(df.groupby('hour').size().idxmax())
        }
    
    def _analyze_alert_effectiveness(self, df: pd.DataFrame) -> Dict:
        """Analyze alert generation and management"""
        
        alerts = df.dropna(subset=['alert_id'])
        
        if alerts.empty:
            return {'no_alerts': True}
        
        return {
            'total_alerts_generated': len(alerts),
            'alert_generation_rate': float(len(alerts) / len(df)),
            'alert_risk_distribution': {
                'high_risk': int((alerts['risk_score'] > 0.7).sum()),
                'medium_risk': int(((alerts['risk_score'] > 0.4) & (alerts['risk_score'] <= 0.7)).sum()),
                'low_risk': int((alerts['risk_score'] <= 0.4).sum())
            },
            'alert_status_breakdown': alerts['alert_status'].value_counts().to_dict()
        }
    
    def generate_visualizations(self, df: pd.DataFrame, analysis: Dict) -> List[str]:
        """Generate comprehensive visualizations"""
        
        plots = []
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 1. Anomaly Rate by Source
        if 'source_breakdown' in analysis:
            self._plot_anomaly_by_source(df, analysis['source_breakdown'])
            plots.append('anomaly_by_source.png')
        
        # 2. Risk Score Distribution
        self._plot_risk_distribution(df)
        plots.append('risk_score_distribution.png')
        
        # 3. Temporal Analysis
        if 'temporal_analysis' in analysis:
            self._plot_temporal_analysis(df, analysis['temporal_analysis'])
            plots.append('temporal_analysis.png')
        
        # 4. Zeek-specific Analysis
        if 'zeek_specific' in analysis and not analysis['zeek_specific'].get('no_zeek_logs'):
            self._plot_zeek_analysis(df, analysis['zeek_specific'])
            plots.append('zeek_analysis.png')
        
        # 5. Model Performance Over Time
        self._plot_performance_timeline(df)
        plots.append('performance_timeline.png')
        
        return plots
    
    def _plot_anomaly_by_source(self, df: pd.DataFrame, source_breakdown: Dict):
        """Plot anomaly rates by log source"""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        sources = list(source_breakdown.keys())
        anomaly_rates = [source_breakdown[s]['anomaly_rate'] for s in sources]
        total_logs = [source_breakdown[s]['total_logs'] for s in sources]
        
        # Anomaly rates
        bars1 = ax1.bar(range(len(sources)), anomaly_rates)
        ax1.set_title('Anomaly Rate by Log Source')
        ax1.set_xlabel('Log Source')
        ax1.set_ylabel('Anomaly Rate')
        ax1.set_xticks(range(len(sources)))
        ax1.set_xticklabels(sources, rotation=45, ha='right')
        
        # Add value labels on bars
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.2%}', ha='center', va='bottom')
        
        # Log volume
        bars2 = ax2.bar(range(len(sources)), total_logs, color='lightcoral')
        ax2.set_title('Log Volume by Source')
        ax2.set_xlabel('Log Source')  
        ax2.set_ylabel('Number of Logs')
        ax2.set_xticks(range(len(sources)))
        ax2.set_xticklabels(sources, rotation=45, ha='right')
        
        plt.tight_layout()
        plt.savefig(self.report_dir / 'anomaly_by_source.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_risk_distribution(self, df: pd.DataFrame):
        """Plot risk score distribution"""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Histogram
        ax1.hist(df['risk_score'], bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.set_title('Risk Score Distribution')
        ax1.set_xlabel('Risk Score')
        ax1.set_ylabel('Frequency')
        ax1.axvline(df['risk_score'].mean(), color='red', linestyle='--', 
                   label=f'Mean: {df["risk_score"].mean():.3f}')
        ax1.legend()
        
        # Box plot by anomaly status
        anomaly_data = [df[df['is_anomaly'] == 0]['risk_score'], 
                       df[df['is_anomaly'] == 1]['risk_score']]
        ax2.boxplot(anomaly_data, labels=['Normal', 'Anomaly'])
        ax2.set_title('Risk Score by Classification')
        ax2.set_ylabel('Risk Score')
        
        plt.tight_layout()
        plt.savefig(self.report_dir / 'risk_score_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_temporal_analysis(self, df: pd.DataFrame, temporal_data: Dict):
        """Plot temporal patterns"""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Hourly patterns
        hours = list(range(24))
        hourly_counts = [temporal_data['hourly_distribution'].get(h, {'count': 0})['count'] for h in hours]
        hourly_anomalies = [temporal_data['hourly_distribution'].get(h, {'sum': 0})['sum'] for h in hours]
        
        ax1.bar(hours, hourly_counts, alpha=0.7, label='Total Logs', color='lightblue')
        ax1.bar(hours, hourly_anomalies, alpha=0.7, label='Anomalies', color='red')
        ax1.set_title('Log Activity by Hour')
        ax1.set_xlabel('Hour of Day')
        ax1.set_ylabel('Number of Logs')
        ax1.legend()
        
        # Daily patterns
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        daily_counts = [temporal_data['daily_distribution'].get(i, {'count': 0})['count'] for i in range(7)]
        daily_anomalies = [temporal_data['daily_distribution'].get(i, {'sum': 0})['sum'] for i in range(7)]
        
        ax2.bar(days, daily_counts, alpha=0.7, label='Total Logs', color='lightgreen')
        ax2.bar(days, daily_anomalies, alpha=0.7, label='Anomalies', color='orange')
        ax2.set_title('Log Activity by Day of Week')
        ax2.set_xlabel('Day of Week')
        ax2.set_ylabel('Number of Logs')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(self.report_dir / 'temporal_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_zeek_analysis(self, df: pd.DataFrame, zeek_data: Dict):
        """Plot Zeek-specific analysis"""
        
        if zeek_data.get('no_zeek_logs'):
            return
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Zeek log types analysis
        zeek_types = list(zeek_data['by_zeek_type'].keys())
        anomaly_rates = [zeek_data['by_zeek_type'][t]['anomaly_rate'] for t in zeek_types]
        log_counts = [zeek_data['by_zeek_type'][t]['count'] for t in zeek_types]
        
        # Create bubble chart
        scatter = ax.scatter(range(len(zeek_types)), anomaly_rates, 
                           s=[c/10 for c in log_counts], alpha=0.6, 
                           c=range(len(zeek_types)), cmap='viridis')
        
        ax.set_title('Zeek Log Analysis\n(Bubble size = log count)')
        ax.set_xlabel('Zeek Log Type')
        ax.set_ylabel('Anomaly Rate')
        ax.set_xticks(range(len(zeek_types)))
        ax.set_xticklabels(zeek_types, rotation=45, ha='right')
        
        # Add count labels
        for i, (zeek_type, count, rate) in enumerate(zip(zeek_types, log_counts, anomaly_rates)):
            ax.annotate(f'{count} logs', (i, rate), xytext=(5, 5), 
                       textcoords='offset points', fontsize=9)
        
        plt.colorbar(scatter, label='Log Type Index')
        plt.tight_layout()
        plt.savefig(self.report_dir / 'zeek_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_performance_timeline(self, df: pd.DataFrame):
        """Plot model performance over time"""
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Daily aggregation
        daily_stats = df.groupby('date').agg({
            'is_anomaly': ['count', 'sum', 'mean'],
            'risk_score': 'mean'
        }).round(3)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
        
        # Anomaly detection over time
        ax1.plot(daily_stats.index, daily_stats[('is_anomaly', 'count')], 
                label='Total Logs', marker='o', linewidth=2)
        ax1.plot(daily_stats.index, daily_stats[('is_anomaly', 'sum')], 
                label='Anomalies Detected', marker='s', linewidth=2)
        ax1.set_title('Model Activity Over Time')
        ax1.set_ylabel('Number of Logs')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Risk scores over time
        ax2.plot(daily_stats.index, daily_stats[('risk_score', 'mean')], 
                color='red', marker='d', linewidth=2)
        ax2.set_title('Average Risk Score Over Time')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Average Risk Score')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.report_dir / 'performance_timeline.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_comprehensive_report(self, days_back: int = 7) -> str:
        """Generate comprehensive model performance report"""
        
        logger.info(f"Generating comprehensive model report for last {days_back} days...")
        
        # Collect data
        df = self.collect_predictions(days_back)
        if df.empty:
            logger.warning("No data available for report generation")
            return ""
        
        # Analyze performance
        analysis = self.analyze_model_performance(df)
        
        # Generate visualizations
        plots = self.generate_visualizations(df, analysis)
        
        # Create HTML report
        report_path = self._generate_html_report(analysis, plots, days_back)
        
        # Create JSON summary
        self._save_json_summary(analysis, df)
        
        logger.info(f"Model report generated: {report_path}")
        return str(report_path)
    
    def _generate_html_report(self, analysis: Dict, plots: List[str], days_back: int) -> Path:
        """Generate HTML report"""
        
        report_path = self.report_dir / 'model_performance_report.html'
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Model Performance Report - {self.current_date}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .alert-card {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .success-card {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .chart {{ text-align: center; margin: 20px 0; }}
                .chart img {{ max-width: 100%; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .number {{ font-size: 1.5em; font-weight: bold; color: #007bff; }}
                .section {{ margin: 30px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 Log Anomaly Detection - Model Performance Report</h1>
                    <p>Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Analysis Period: Last {days_back} days</p>
                </div>
        """
        
        # Overall Statistics
        if 'overall_stats' in analysis:
            stats = analysis['overall_stats']
            html_content += f"""
                <div class="section">
                    <h2>📊 Overall Performance</h2>
                    <div class="metric-card">
                        <h3>Processing Summary</h3>
                        <p>Total Logs Processed: <span class="number">{stats['total_logs_processed']:,}</span></p>
                        <p>Anomalies Detected: <span class="number">{stats['anomalies_detected']:,}</span></p>
                        <p>Anomaly Rate: <span class="number">{stats['anomaly_rate']:.2%}</span></p>
                        <p>Average Risk Score: <span class="number">{stats['average_risk_score']:.3f}</span></p>
                        <p>High Risk Alerts: <span class="number">{stats['high_risk_alerts']:,}</span></p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Risk Distribution</h3>
                        <p>Low Risk (0-0.3): <span class="number">{stats['risk_distribution']['low_risk_0_0.3']:,}</span></p>
                        <p>Medium Risk (0.3-0.7): <span class="number">{stats['risk_distribution']['medium_risk_0.3_0.7']:,}</span></p>
                        <p>High Risk (0.7-1.0): <span class="number">{stats['risk_distribution']['high_risk_0.7_1.0']:,}</span></p>
                    </div>
                </div>
            """
        
        # Zeek-specific Analysis
        if 'zeek_specific' in analysis and not analysis['zeek_specific'].get('no_zeek_logs'):
            zeek_data = analysis['zeek_specific']
            html_content += f"""
                <div class="section">
                    <h2>🌐 Zeek Network Log Analysis</h2>
                    <div class="alert-card">
                        <h3>Zeek Performance Summary</h3>
                        <p>Zeek Logs Processed: <span class="number">{zeek_data['zeek_logs_processed']:,}</span></p>
                        <p>Zeek Anomaly Rate: <span class="number">{zeek_data['zeek_anomaly_rate']:.2%}</span></p>
                        <p>Average Zeek Risk Score: <span class="number">{zeek_data['zeek_avg_risk']:.3f}</span></p>
                    </div>
                    
                    <h4>Performance by Zeek Log Type:</h4>
                    <table>
                        <tr><th>Log Type</th><th>Count</th><th>Anomaly Rate</th><th>Avg Risk Score</th></tr>
            """
            
            for log_type, data in zeek_data['by_zeek_type'].items():
                html_content += f"""
                        <tr>
                            <td>{log_type}</td>
                            <td>{data['count']:,}</td>
                            <td>{data['anomaly_rate']:.2%}</td>
                            <td>{data['avg_risk']:.3f}</td>
                        </tr>
                """
            
            html_content += """
                    </table>
                </div>
            """
        
        # Source Analysis
        if 'source_breakdown' in analysis:
            html_content += """
                <div class="section">
                    <h2>📁 Performance by Log Source</h2>
                    <table>
                        <tr><th>Source</th><th>Total Logs</th><th>Anomalies</th><th>Anomaly Rate</th><th>Avg Risk Score</th><th>Type</th></tr>
            """
            
            for source, data in analysis['source_breakdown'].items():
                source_type = "Zeek Network" if data['is_zeek_log'] else "System"
                html_content += f"""
                        <tr>
                            <td>{source}</td>
                            <td>{data['total_logs']:,}</td>
                            <td>{data['anomalies']:,}</td>
                            <td>{data['anomaly_rate']:.2%}</td>
                            <td>{data['avg_risk_score']:.3f}</td>
                            <td>{source_type}</td>
                        </tr>
                """
            
            html_content += """
                    </table>
                </div>
            """
        
        # Charts
        if plots:
            html_content += """
                <div class="section">
                    <h2>📈 Performance Visualizations</h2>
            """
            
            for plot in plots:
                chart_title = plot.replace('_', ' ').replace('.png', '').title()
                html_content += f"""
                    <div class="chart">
                        <h3>{chart_title}</h3>
                        <img src="{plot}" alt="{chart_title}">
                    </div>
                """
            
            html_content += "</div>"
        
        # Recommendations
        html_content += self._generate_recommendations(analysis)
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return report_path
    
    def _generate_recommendations(self, analysis: Dict) -> str:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Check overall performance
        if 'overall_stats' in analysis:
            anomaly_rate = analysis['overall_stats']['anomaly_rate']
            if anomaly_rate > 0.3:
                recommendations.append("⚠️ High anomaly rate detected (>30%). Consider adjusting model sensitivity or reviewing training data.")
            elif anomaly_rate < 0.01:
                recommendations.append("⚠️ Very low anomaly rate (<1%). Model might be missing threats - consider increasing sensitivity.")
        
        # Check Zeek performance
        if 'zeek_specific' in analysis and not analysis['zeek_specific'].get('no_zeek_logs'):
            zeek_rate = analysis['zeek_specific']['zeek_anomaly_rate']
            if zeek_rate > 0.5:
                recommendations.append("🌐 High Zeek anomaly rate detected. Consider adding more IoT/network traffic to training data.")
        
        # Check temporal patterns
        if 'temporal_analysis' in analysis:
            peak_hour = analysis['temporal_analysis']['peak_anomaly_hour']
            recommendations.append(f"⏰ Peak anomaly detection at hour {peak_hour}. Monitor this time period closely.")
        
        if not recommendations:
            recommendations.append("✅ Model performance appears stable. Continue monitoring.")
        
        html = """
            <div class="section">
                <h2>💡 Recommendations</h2>
                <div class="alert-card">
        """
        
        for rec in recommendations:
            html += f"<p>{rec}</p>"
        
        html += """
                </div>
            </div>
        """
        
        return html
    
    def _save_json_summary(self, analysis: Dict, df: pd.DataFrame):
        """Save JSON summary for programmatic access"""
        
        summary = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'report_id': self.current_date,
                'data_points': len(df),
                'analysis_period_days': 7
            },
            'performance_metrics': analysis,
            'model_health_score': self._calculate_health_score(analysis)
        }
        
        summary_path = self.report_dir / 'model_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
    
    def _calculate_health_score(self, analysis: Dict) -> float:
        """Calculate overall model health score (0-100)"""
        
        score = 100.0
        
        if 'overall_stats' in analysis:
            # Penalize extreme anomaly rates
            anomaly_rate = analysis['overall_stats']['anomaly_rate']
            if anomaly_rate > 0.3 or anomaly_rate < 0.01:
                score -= 20
            
            # Consider risk score distribution
            risk_dist = analysis['overall_stats']['risk_distribution']
            total = sum(risk_dist.values())
            if total > 0:
                high_risk_ratio = risk_dist['high_risk_0.7_1.0'] / total
                if high_risk_ratio > 0.1:  # More than 10% high risk
                    score -= 15
        
        # Zeek-specific penalties
        if 'zeek_specific' in analysis and not analysis['zeek_specific'].get('no_zeek_logs'):
            zeek_anomaly_rate = analysis['zeek_specific']['zeek_anomaly_rate']
            if zeek_anomaly_rate > 0.5:  # More than 50% of Zeek logs flagged
                score -= 25
        
        return max(0.0, min(100.0, score))

# Integration function to add to your existing scripts
def generate_model_report():
    """Generate comprehensive model performance report"""
    from app.config import settings
    
    reporter = ModelReporter(os.path.dirname(settings.PROJECT_ROOT))
    report_path = reporter.generate_comprehensive_report(days_back=7)
    
    if report_path:
        print(f"📊 Model performance report generated: {report_path}")
        print(f"📁 Report directory: {reporter.report_dir}")
        return str(report_path)
    else:
        print("❌ Failed to generate model report")
        return None

if __name__ == "__main__":
    generate_model_report()
