"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { dashboardService, POAnalytics, NegotiationAnalytics } from "@/services/dashboard.service";
import { workflowService, type WorkflowSessionSummary } from "@/services/workflow.service";
import { authService } from "@/services/auth.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import { AreaChartCard, BarChartCard } from "@/components/charts";
import {
  FileText,
  Users,
  ShoppingCart,
  TrendingDown,
  BarChart3,
  Zap,
  Sparkles,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type { DashboardStats, User } from "@/types";

const SESSION_STATUS_ICON: Record<string, React.ReactNode> = {
  active: <Clock className="w-3.5 h-3.5 text-indigo-500" />,
  waiting: <AlertCircle className="w-3.5 h-3.5 text-amber-500" />,
  completed: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />,
};

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [recentSessions, setRecentSessions] = useState<WorkflowSessionSummary[]>([]);
  const [poAnalytics, setPOAnalytics] = useState<POAnalytics | null>(null);
  const [negAnalytics, setNegAnalytics] = useState<NegotiationAnalytics | null>(null);
  const [pipeline, setPipeline] = useState<{ status: string; count: number }[]>([]);

  useEffect(() => {
    authService.getMe().then(setUser).catch(() => {});
    dashboardService.getStats().then(setStats).catch(console.error).finally(() => setLoading(false));
    workflowService.listSessions({ limit: 5 }).then((d) => setRecentSessions(d.items)).catch(() => {});
    dashboardService.getPOAnalytics().then(setPOAnalytics).catch(() => {});
    dashboardService.getNegotiationAnalytics().then(setNegAnalytics).catch(() => {});
    dashboardService.getPipeline().then((d) => setPipeline(d.pipeline || [])).catch(() => {});
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-44 rounded-2xl bg-gradient-to-r from-indigo-50 to-violet-50 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: "Active RFQs",
      value: stats?.active_rfqs || 0,
      subtitle: `${stats?.total_rfqs || 0} total`,
      icon: FileText,
      color: "text-blue-600 bg-blue-50",
    },
    {
      title: "Suppliers",
      value: stats?.total_suppliers || 0,
      subtitle: "Active vendors",
      icon: Users,
      color: "text-emerald-600 bg-emerald-50",
    },
    {
      title: "Purchase Orders",
      value: formatCurrency(stats?.total_po_value || 0),
      subtitle: `${stats?.total_purchase_orders || 0} orders`,
      icon: ShoppingCart,
      color: "text-purple-600 bg-purple-50",
    },
    {
      title: "AI Savings",
      value: formatCurrency(stats?.negotiation_savings || 0),
      subtitle: "From negotiations",
      icon: TrendingDown,
      color: "text-orange-600 bg-orange-50",
    },
  ];

  const formatK = (v: number) => {
    if (v >= 10_000_000) return `${(v / 10_000_000).toFixed(1)}Cr`;
    if (v >= 100_000) return `${(v / 100_000).toFixed(1)}L`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
    return v.toFixed(0);
  };

  const pipelineData = pipeline
    .filter((p) => p.count > 0)
    .map((p) => ({ name: p.status.replace(/_/g, " "), count: p.count }));

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 via-violet-600 to-purple-700 p-8 md:p-10 shadow-xl shadow-indigo-500/10">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZGVmcz48cGF0dGVybiBpZD0iZyIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSIgd2lkdGg9IjIwIiBoZWlnaHQ9IjIwIj48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSIxLjUiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNSkiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IGZpbGw9InVybCgjZykiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiLz48L3N2Zz4=')] opacity-60" />
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white">
              Welcome back, {user?.full_name || "User"}
            </h1>
            <p className="text-indigo-100 mt-2 text-sm md:text-base max-w-lg">
              Manage your procurement workflows with AI-powered automation. Create RFQs, analyze quotes, and generate purchase orders in minutes.
            </p>
          </div>
          <button
            onClick={() => router.push("/workspace")}
            className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl bg-white text-indigo-700 font-semibold text-sm hover:bg-indigo-50 transition-all shadow-lg shadow-black/10 flex-shrink-0 group"
          >
            <Sparkles className="w-5 h-5" />
            Start New Procurement
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <Card key={card.title} className="hover:shadow-md transition-shadow border-slate-200/80">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{card.title}</p>
                  <p className="text-2xl font-bold mt-1">{card.value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{card.subtitle}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${card.color}`}>
                  <card.icon className="w-6 h-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {poAnalytics && poAnalytics.monthly_spend.length > 0 && (
          <AreaChartCard
            title="Monthly Procurement Spend"
            subtitle="PO values over last 6 months"
            data={poAnalytics.monthly_spend}
            dataKey="spend"
            xKey="month"
            color="#6366f1"
            gradientId="dashSpend"
            formatValue={(v) => formatK(v)}
          />
        )}
        {pipelineData.length > 0 && (
          <BarChartCard
            title="RFQ Pipeline"
            subtitle="Distribution of RFQs by current status"
            data={pipelineData}
            dataKey="count"
            xKey="name"
            color="#8b5cf6"
            layout="horizontal"
          />
        )}
      </div>

      {/* Savings Trend (only if data exists) */}
      {negAnalytics && negAnalytics.monthly_savings.length > 0 && (
        <AreaChartCard
          title="AI Negotiation Savings Trend"
          subtitle="Monthly savings achieved through automated negotiations"
          data={negAnalytics.monthly_savings}
          dataKey="savings"
          xKey="month"
          color="#10b981"
          gradientId="dashSavings"
          formatValue={(v) => formatK(v)}
          height={200}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Workflows */}
        <Card className="lg:col-span-2 border-slate-200/80">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="w-5 h-5 text-indigo-500" />
              Recent Workflows
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentSessions.length > 0 ? (
              <div className="space-y-2">
                {recentSessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => router.push("/workspace")}
                    className="w-full flex items-center justify-between p-3.5 rounded-xl border border-slate-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all group text-left"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {SESSION_STATUS_ICON[session.status] || SESSION_STATUS_ICON.active}
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate group-hover:text-indigo-700 transition-colors">
                          {session.title}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {new Date(session.updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize">
                        {session.status}
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-center py-10 text-muted-foreground">
                <Sparkles className="w-8 h-8 mx-auto mb-3 opacity-40" />
                <p className="text-sm">No workflows yet.</p>
                <p className="text-xs mt-1">Click &quot;Start New Procurement&quot; to begin.</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <div className="space-y-6">
          <Card className="border-slate-200/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-500" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  { label: "New RFQ", href: "/dashboard/rfqs/new", icon: "🤖" },
                  { label: "Suppliers", href: "/dashboard/suppliers", icon: "🏢" },
                  { label: "Quotations", href: "/dashboard/quotations", icon: "📊" },
                  { label: "Orders", href: "/dashboard/purchase-orders", icon: "📦" },
                  { label: "Negotiations", href: "/dashboard/negotiations", icon: "🤝" },
                  { label: "Analytics", href: "/dashboard/analytics", icon: "📈" },
                ].map((action) => (
                  <a
                    key={action.label}
                    href={action.href}
                    className="flex items-center gap-2.5 p-3 rounded-xl border border-slate-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all"
                  >
                    <span className="text-xl">{action.icon}</span>
                    <span className="text-xs font-medium text-slate-700">{action.label}</span>
                  </a>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
