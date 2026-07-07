"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { negotiationService } from "@/services/negotiation.service";
import { dashboardService, NegotiationAnalytics } from "@/services/dashboard.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import { KPICard, AreaChartCard, DonutChartCard } from "@/components/charts";
import {
  Handshake,
  TrendingDown,
  ArrowRight,
  Check,
  X,
  Zap,
  CheckCircle2,
  Target,
  PiggyBank,
  AlertCircle,
} from "lucide-react";
import type { Negotiation } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b",
  sent: "#6366f1",
  counter_received: "#06b6d4",
  accepted: "#10b981",
  rejected: "#ef4444",
  expired: "#94a3b8",
};

export default function NegotiationsPage() {
  const [negotiations, setNegotiations] = useState<Negotiation[]>([]);
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<NegotiationAnalytics | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    loadNegotiations();
    dashboardService.getNegotiationAnalytics().then(setAnalytics).catch(console.error);
  }, []);

  async function loadNegotiations() {
    setLoading(true);
    try {
      const data = await negotiationService.list();
      setNegotiations(data.items || data as any);
    } catch { }
    setLoading(false);
  }

  async function handleAccept(id: string) {
    await negotiationService.accept(id);
    loadNegotiations();
  }

  async function handleReject(id: string) {
    await negotiationService.reject(id);
    loadNegotiations();
  }

  const filtered = negotiations.filter(
    (n) => statusFilter === "all" || n.status === statusFilter
  );

  const attentionNeeded = negotiations.filter((n) => n.status === "counter_received");

  const formatK = (v: number) => {
    if (v >= 1_000_000) return `₹${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `₹${(v / 1_000).toFixed(0)}K`;
    return `₹${v.toFixed(0)}`;
  };

  const donutData = analytics
    ? Object.entries(analytics.by_status).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1).replace("_", " "),
        value,
        color: STATUS_COLORS[name] || "#94a3b8",
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Negotiation Command Center</h1>
        <p className="text-sm text-gray-500 mt-1">AI-powered price negotiations — track savings and performance</p>
      </div>

      {/* KPI Row */}
      {analytics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Active Negotiations"
            value={analytics.active}
            subtitle="Pending + Sent + Counter"
            icon={<Zap className="w-5 h-5 text-white" />}
            color="indigo"
          />
          <KPICard
            title="Completed"
            value={analytics.completed}
            subtitle={`Avg ${analytics.avg_rounds} rounds`}
            icon={<CheckCircle2 className="w-5 h-5 text-white" />}
            color="green"
          />
          <KPICard
            title="Success Rate"
            value={`${analytics.success_rate}%`}
            subtitle={`${analytics.completed} of ${analytics.completed + analytics.failed} concluded`}
            icon={<Target className="w-5 h-5 text-white" />}
            color="purple"
          />
          <KPICard
            title="Total Savings"
            value={formatK(analytics.total_savings)}
            subtitle={`Avg ${analytics.avg_savings_pct}% per deal`}
            icon={<PiggyBank className="w-5 h-5 text-white" />}
            color="green"
          />
        </div>
      )}

      {/* Charts Row */}
      {analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AreaChartCard
            title="Monthly Savings Trend"
            subtitle="Cumulative negotiation savings (accepted)"
            data={analytics.monthly_savings}
            dataKey="savings"
            xKey="month"
            color="#10b981"
            gradientId="savingsTrend"
            formatValue={(v) => formatK(v)}
          />
          <DonutChartCard
            title="Status Distribution"
            subtitle="Negotiation outcomes breakdown"
            data={donutData}
          />
        </div>
      )}

      {/* Attention Banner */}
      {attentionNeeded.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-900">
              {attentionNeeded.length} negotiation{attentionNeeded.length > 1 ? "s" : ""} need your attention
            </p>
            <p className="text-xs text-amber-700 mt-0.5">Counter offers received — accept or reject to proceed</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {["all", "pending", "sent", "counter_received", "accepted", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              statusFilter === s
                ? "bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Negotiations Table */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50/80">
                  <th className="text-left p-3 font-medium text-gray-600">Supplier</th>
                  <th className="text-left p-3 font-medium text-gray-600">Round</th>
                  <th className="text-left p-3 font-medium text-gray-600">Original</th>
                  <th className="text-left p-3 font-medium text-gray-600">Target</th>
                  <th className="text-left p-3 font-medium text-gray-600">Negotiated</th>
                  <th className="text-left p-3 font-medium text-gray-600">Savings</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((neg) => {
                  const finalPrice = neg.negotiated_price || neg.target_price;
                  const savings = neg.original_price - finalPrice;
                  const savingsPct = neg.original_price > 0
                    ? ((savings / neg.original_price) * 100).toFixed(1)
                    : "0";

                  return (
                    <tr key={neg.id} className="border-b hover:bg-gray-50/50 transition">
                      <td className="p-3 font-medium text-gray-900">
                        {(neg as any).supplier_name || `Supplier`}
                      </td>
                      <td className="p-3">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">
                          {neg.round_number}
                        </span>
                      </td>
                      <td className="p-3 text-gray-600">{formatCurrency(neg.original_price)}</td>
                      <td className="p-3 text-indigo-600 font-medium">{formatCurrency(neg.target_price)}</td>
                      <td className="p-3">
                        {neg.negotiated_price ? (
                          <span className="text-emerald-600 font-medium">{formatCurrency(neg.negotiated_price)}</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="p-3">
                        {savings > 0 ? (
                          <div className="flex items-center gap-1 text-emerald-600">
                            <TrendingDown className="w-3.5 h-3.5" />
                            <span className="text-xs font-medium">{savingsPct}%</span>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="p-3">
                        <Badge className={getStatusColor(neg.status)}>
                          {neg.status.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="p-3">
                        {neg.status === "counter_received" && (
                          <div className="flex gap-1.5">
                            <Button size="sm" variant="ghost" className="h-7 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50" onClick={() => handleAccept(neg.id)}>
                              <Check className="w-3.5 h-3.5" />
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 text-rose-600 hover:text-rose-700 hover:bg-rose-50" onClick={() => handleReject(neg.id)}>
                              <X className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center py-16">
          <Handshake className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">No negotiations found</p>
          <p className="text-xs text-gray-400 mt-1">AI will initiate negotiations when quotes are above target</p>
        </div>
      )}
    </div>
  );
}
