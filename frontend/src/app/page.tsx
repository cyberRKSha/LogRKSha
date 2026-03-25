import DashboardLayout from "@/components/layout/DashboardLayout";
import StatCard from "@/components/ui/StatCard";

const LogsIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const AlertIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

export default function DashboardPage() {
  const stats = {
    totalLogs: 12450,
    anomalies: 127,
    normalLogs: 12323,
    modelAccuracy: "96.2%",
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            <p className="text-[var(--text-muted)] text-sm">Real-time log anomaly monitoring</p>
          </div>
          <span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/20 text-green-400 text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Monitoring Active
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total Logs" value={stats.totalLogs.toLocaleString()} icon={<LogsIcon />} />
          <StatCard title="Anomalies" value={stats.anomalies} icon={<AlertIcon />} colorClass="text-red-400" />
          <StatCard title="Normal Logs" value={stats.normalLogs.toLocaleString()} colorClass="text-green-400" />
          <StatCard title="Model Accuracy" value={stats.modelAccuracy} colorClass="text-indigo-400" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Activity Timeline</h3>
            <div className="h-64 flex items-center justify-center text-[var(--text-muted)]">
              Chart component coming soon...
            </div>
          </div>
          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Model Drift</h3>
            <div className="h-64 flex items-center justify-center text-[var(--text-muted)]">
              Drift chart coming soon...
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Alerts</h3>
          <div className="text-[var(--text-muted)] text-center py-8">
            LogTable component coming soon...
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
