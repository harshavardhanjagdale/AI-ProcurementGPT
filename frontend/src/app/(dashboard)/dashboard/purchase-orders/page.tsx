"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { purchaseOrderService } from "@/services/purchase-order.service";
import { dashboardService, POAnalytics } from "@/services/dashboard.service";
import { formatDate, formatCurrency, getStatusColor } from "@/lib/utils";
import { KPICard, AreaChartCard, DonutChartCard, BarChartCard } from "@/components/charts";
import {
  ShoppingCart,
  Download,
  Send,
  CheckCircle,
  FileText,
  DollarSign,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { PurchaseOrder } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  draft: "#f59e0b",
  approved: "#6366f1",
  sent: "#06b6d4",
  acknowledged: "#8b5cf6",
  fulfilled: "#10b981",
  cancelled: "#ef4444",
};

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<POAnalytics | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  useEffect(() => {
    loadOrders();
    dashboardService.getPOAnalytics().then(setAnalytics).catch(console.error);
  }, []);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await purchaseOrderService.list({ limit: 50 });
      setOrders(data.items || data as any);
    } catch { }
    setLoading(false);
  }

  async function handleApprove(id: string) {
    await purchaseOrderService.approve(id);
    loadOrders();
  }

  async function handleSend(id: string) {
    await purchaseOrderService.send(id);
    loadOrders();
  }

  async function handleDownload(id: string) {
    try {
      await purchaseOrderService.downloadPdf(id);
    } catch {
      alert("Failed to download PDF");
    }
  }

  const filtered = orders.filter(
    (po) => statusFilter === "all" || po.status === statusFilter
  );

  const formatK = (v: number) => {
    if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(1)}Cr`;
    if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)}L`;
    if (v >= 1_000) return `₹${(v / 1_000).toFixed(0)}K`;
    return `₹${v.toFixed(0)}`;
  };

  const donutData = analytics
    ? Object.entries(analytics.by_status).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
        color: STATUS_COLORS[name] || "#94a3b8",
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Purchase Order Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Track procurement spend, delivery, and PO lifecycle</p>
      </div>

      {/* KPI Row */}
      {analytics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Purchase Orders"
            value={analytics.total}
            subtitle="All time generated"
            icon={<FileText className="w-5 h-5 text-white" />}
            color="blue"
          />
          <KPICard
            title="Total Spend"
            value={formatK(analytics.total_spend)}
            subtitle={`Avg ${formatK(analytics.avg_po_value)} per PO`}
            icon={<DollarSign className="w-5 h-5 text-white" />}
            color="green"
          />
          <KPICard
            title="Pending Approvals"
            value={analytics.pending_approvals}
            subtitle="Draft POs awaiting action"
            icon={<Clock className="w-5 h-5 text-white" />}
            color="amber"
          />
          <KPICard
            title="Overdue Deliveries"
            value={analytics.overdue}
            subtitle="Past delivery date"
            icon={<AlertTriangle className="w-5 h-5 text-white" />}
            color="red"
          />
        </div>
      )}

      {/* Charts Row */}
      {analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <AreaChartCard
              title="Monthly Spend Trend"
              subtitle="PO value over last 6 months"
              data={analytics.monthly_spend}
              dataKey="spend"
              xKey="month"
              color="#6366f1"
              gradientId="spendTrend"
              formatValue={(v) => formatK(v)}
            />
          </div>
          <DonutChartCard
            title="PO Status Distribution"
            subtitle="Current breakdown"
            data={donutData}
          />
        </div>
      )}

      {/* Top Suppliers */}
      {analytics && analytics.top_suppliers.length > 0 && (
        <BarChartCard
          title="Top Suppliers by PO Value"
          subtitle="Highest value procurement partners"
          data={analytics.top_suppliers}
          dataKey="value"
          xKey="name"
          color="#8b5cf6"
          layout="horizontal"
          formatValue={(v) => formatK(v)}
          height={200}
        />
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {["all", "draft", "approved", "sent", "acknowledged", "fulfilled", "cancelled"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              statusFilter === s
                ? "bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* PO Table */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50/80">
                  <th className="text-left p-3 font-medium text-gray-600 w-8"></th>
                  <th className="text-left p-3 font-medium text-gray-600">PO Number</th>
                  <th className="text-left p-3 font-medium text-gray-600">Amount</th>
                  <th className="text-left p-3 font-medium text-gray-600">Tax</th>
                  <th className="text-left p-3 font-medium text-gray-600">Delivery</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Created</th>
                  <th className="text-left p-3 font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((po) => (
                  <>
                    <tr
                      key={po.id}
                      className="border-b hover:bg-gray-50/50 transition cursor-pointer"
                      onClick={() => setExpandedRow(expandedRow === po.id ? null : po.id)}
                    >
                      <td className="p-3">
                        {expandedRow === po.id ? (
                          <ChevronDown className="w-4 h-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        )}
                      </td>
                      <td className="p-3 font-medium text-gray-900">{po.po_number}</td>
                      <td className="p-3 font-semibold">{formatCurrency(po.total_amount, po.currency)}</td>
                      <td className="p-3 text-gray-600 text-xs">
                        {(po as any).tax_percent ? `${(po as any).tax_percent}%` : "—"}
                      </td>
                      <td className="p-3 text-gray-600">
                        {po.delivery_date ? formatDate(po.delivery_date) : "—"}
                      </td>
                      <td className="p-3">
                        <Badge className={getStatusColor(po.status)}>{po.status}</Badge>
                      </td>
                      <td className="p-3 text-gray-500 text-xs">{formatDate(po.created_at)}</td>
                      <td className="p-3">
                        <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
                          {po.status === "draft" && (
                            <Button size="sm" variant="ghost" className="h-7 text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50" onClick={() => handleApprove(po.id)}>
                              <CheckCircle className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          {po.status === "approved" && (
                            <Button size="sm" variant="ghost" className="h-7 text-cyan-600 hover:text-cyan-700 hover:bg-cyan-50" onClick={() => handleSend(po.id)}>
                              <Send className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          {po.pdf_path && (
                            <Button size="sm" variant="ghost" className="h-7 text-gray-600 hover:text-gray-700 hover:bg-gray-100" onClick={() => handleDownload(po.id)}>
                              <Download className="w-3.5 h-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expandedRow === po.id && po.items && po.items.length > 0 && (
                      <tr key={`${po.id}-items`} className="bg-gray-50/50">
                        <td colSpan={8} className="p-4">
                          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Line Items</h4>
                          <div className="grid grid-cols-4 gap-2 text-xs text-gray-500 mb-1 px-2">
                            <span>Product</span><span>Qty</span><span>Unit Price</span><span>Total</span>
                          </div>
                          {po.items.map((item: any, i: number) => (
                            <div key={i} className="grid grid-cols-4 gap-2 text-sm py-1.5 px-2 bg-white rounded border mb-1">
                              <span className="truncate text-gray-700">{item.product_name}</span>
                              <span className="text-gray-600">{item.quantity}</span>
                              <span className="text-gray-600">{formatCurrency(item.unit_price, po.currency)}</span>
                              <span className="font-medium">{formatCurrency(item.total_price, po.currency)}</span>
                            </div>
                          ))}
                          {po.payment_terms && (
                            <p className="text-xs text-gray-500 mt-2">Payment terms: {po.payment_terms}</p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center py-16">
          <ShoppingCart className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">No purchase orders found</p>
          <p className="text-xs text-gray-400 mt-1">POs are generated after accepting quotations</p>
        </div>
      )}
    </div>
  );
}
