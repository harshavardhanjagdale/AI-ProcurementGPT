"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { dashboardService } from "@/services/dashboard.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import {
  FileText,
  Users,
  ShoppingCart,
  TrendingDown,
  BarChart3,
  Zap,
} from "lucide-react";
import type { DashboardStats } from "@/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardService.getStats().then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your procurement operations</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <Card key={card.title} className="hover:shadow-md transition-shadow">
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              RFQ Pipeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.rfqs_by_status && Object.keys(stats.rfqs_by_status).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(stats.rfqs_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge className={getStatusColor(status)}>
                        {status.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <span className="text-sm font-semibold">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No RFQs yet. Start with AI Chat!</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "New RFQ", href: "/dashboard/rfqs/new", icon: "🤖" },
                { label: "Suppliers", href: "/dashboard/suppliers", icon: "🏢" },
                { label: "Quotations", href: "/dashboard/quotations", icon: "📊" },
                { label: "Orders", href: "/dashboard/purchase-orders", icon: "📦" },
              ].map((action) => (
                <a
                  key={action.label}
                  href={action.href}
                  className="flex items-center gap-3 p-4 rounded-xl border hover:border-primary/30 hover:bg-primary/5 transition-all"
                >
                  <span className="text-2xl">{action.icon}</span>
                  <span className="text-sm font-medium">{action.label}</span>
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
