"use client";

import { useEffect, useState } from "react";
import { dashboardService, SupplierPerformance, ProcurementOverview, POAnalytics, NegotiationAnalytics } from "@/services/dashboard.service";
import { KPICard, AreaChartCard, BarChartCard } from "@/components/charts";
import { formatCurrency } from "@/lib/utils";
import {
  Activity,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  Trophy,
  Timer,
  Zap,
  Award,
  Target,
} from "lucide-react";

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<ProcurementOverview | null>(null);
  const [supplier, setSupplier] = useState<SupplierPerformance | null>(null);
  const [poData, setPOData] = useState<POAnalytics | null>(null);
  const [negData, setNegData] = useState<NegotiationAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      dashboardService.getProcurementOverview().then(setOverview),
      dashboardService.getSupplierPerformance().then(setSupplier),
      dashboardService.getPOAnalytics().then(setPOData),
      dashboardService.getNegotiationAnalytics().then(setNegData),
    ]).catch(console.error).finally(() => setLoading(false));
  }, []);

  const formatK = (v: number) => {
    if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(1)}Cr`;
    if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)}L`;
    if (v >= 1_000) return `₹${(v / 1_000).toFixed(0)}K`;
    return `₹${v.toFixed(0)}`;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-72 rounded-xl bg-gray-100 animate-pulse" />
          <div className="h-72 rounded-xl bg-gray-100 animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Procurement Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">Cross-cutting insights across all procurement activities</p>
      </div>

      {/* Overview KPIs */}
      {overview && poData && negData && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Spend"
            value={formatK(poData.total_spend)}
            subtitle={`${poData.total} purchase orders`}
            icon={<TrendingUp className="w-5 h-5 text-white" />}
            color="blue"
          />
          <KPICard
            title="Negotiation Savings"
            value={formatK(negData.total_savings)}
            subtitle={`${negData.success_rate}% success rate`}
            icon={<Target className="w-5 h-5 text-white" />}
            color="green"
          />
          <KPICard
            title="Avg Cycle Time"
            value={`${overview.avg_cycle_days} days`}
            subtitle="Request to PO"
            icon={<Timer className="w-5 h-5 text-white" />}
            color="purple"
          />
          <KPICard
            title="Workflow Efficiency"
            value={overview.workflow_stats.total > 0
              ? `${Math.round(overview.workflow_stats.completed / overview.workflow_stats.total * 100)}%`
              : "—"}
            subtitle={`${overview.workflow_stats.completed} of ${overview.workflow_stats.total} completed`}
            icon={<Zap className="w-5 h-5 text-white" />}
            color="indigo"
          />
        </div>
      )}

      {/* Spend Trend */}
      {overview && overview.monthly_spend.length > 0 && (
        <AreaChartCard
          title="Annual Procurement Spend"
          subtitle="Monthly spend trend (last 12 months)"
          data={overview.monthly_spend}
          dataKey="spend"
          xKey="month"
          color="#6366f1"
          gradientId="annualSpend"
          height={280}
          formatValue={(v) => formatK(v)}
        />
      )}

      {/* Supplier Performance Section */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Award className="w-5 h-5 text-indigo-500" />
          Supplier Scorecard
        </h2>

        {supplier && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Suppliers by Value */}
            {supplier.top_suppliers.length > 0 && (
              <BarChartCard
                title="Top Suppliers by PO Value"
                subtitle="Highest value procurement partners"
                data={supplier.top_suppliers.map((s) => ({ name: s.name, value: s.total_value }))}
                dataKey="value"
                xKey="name"
                color="#8b5cf6"
                layout="horizontal"
                formatValue={(v) => formatK(v)}
                height={260}
              />
            )}

            {/* Response Times */}
            {supplier.response_times.length > 0 && (
              <BarChartCard
                title="Supplier Response Time"
                subtitle="Average days to respond to RFQs"
                data={supplier.response_times.map((s) => ({ name: s.name, days: s.avg_days }))}
                dataKey="days"
                xKey="name"
                color="#06b6d4"
                layout="horizontal"
                height={260}
              />
            )}
          </div>
        )}
      </div>

      {/* Win Rates Table */}
      {supplier && supplier.win_rates.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b bg-gray-50/50">
            <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
              <Trophy className="w-4 h-4 text-amber-500" />
              Supplier Win Rates
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">Quotation acceptance rate by supplier</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50/30">
                  <th className="text-left p-3 font-medium text-gray-600">Supplier</th>
                  <th className="text-left p-3 font-medium text-gray-600">Quotations</th>
                  <th className="text-left p-3 font-medium text-gray-600">Wins</th>
                  <th className="text-left p-3 font-medium text-gray-600">Win Rate</th>
                  <th className="text-left p-3 font-medium text-gray-600">Performance</th>
                </tr>
              </thead>
              <tbody>
                {supplier.win_rates.map((s) => (
                  <tr key={s.name} className="border-b hover:bg-gray-50/50 transition">
                    <td className="p-3 font-medium text-gray-900">{s.name}</td>
                    <td className="p-3 text-gray-600">{s.quotes}</td>
                    <td className="p-3 text-emerald-600 font-medium">{s.wins}</td>
                    <td className="p-3 font-semibold">{s.rate}%</td>
                    <td className="p-3">
                      <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all"
                          style={{ width: `${Math.min(s.rate, 100)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Workflow Stats */}
      {overview && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-500" />
            Workflow Performance
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-gray-50">
              <p className="text-2xl font-bold text-gray-900">{overview.workflow_stats.total}</p>
              <p className="text-xs text-gray-500 mt-1">Total Workflows</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-emerald-50">
              <p className="text-2xl font-bold text-emerald-700">{overview.workflow_stats.completed}</p>
              <p className="text-xs text-emerald-600 mt-1">Completed</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-rose-50">
              <p className="text-2xl font-bold text-rose-700">{overview.workflow_stats.failed}</p>
              <p className="text-xs text-rose-600 mt-1">Failed</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-amber-50">
              <p className="text-2xl font-bold text-amber-700">{overview.workflow_stats.cancelled}</p>
              <p className="text-xs text-amber-600 mt-1">Cancelled</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
