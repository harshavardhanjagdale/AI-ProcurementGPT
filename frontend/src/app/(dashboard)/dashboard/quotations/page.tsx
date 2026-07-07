"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { rfqService } from "@/services/rfq.service";
import { quotationService } from "@/services/quotation.service";
import { dashboardService, QuotationAnalytics } from "@/services/dashboard.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import { KPICard, AreaChartCard, BarChartCard } from "@/components/charts";
import {
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Trophy,
  DollarSign,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Star,
} from "lucide-react";
import type { RFQ, Quotation } from "@/types";

export default function QuotationsPage() {
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [selectedRfq, setSelectedRfq] = useState<string>("");
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [analytics, setAnalytics] = useState<QuotationAnalytics | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortField, setSortField] = useState<"total_amount" | "ai_score" | "delivery_days">("ai_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    rfqService.list({ limit: 50 }).then((data) => {
      const items = data.items || (data as any);
      setRfqs(items);
    }).catch(console.error);

    dashboardService.getQuotationAnalytics().then(setAnalytics).catch(console.error);
  }, []);

  async function loadQuotations(rfqId: string) {
    setSelectedRfq(rfqId);
    setLoading(true);
    try {
      const [quots, comp] = await Promise.all([
        quotationService.listByRfq(rfqId),
        quotationService.compare(rfqId).catch(() => null),
      ]);
      setQuotations(quots);
      setComparison(comp);
    } catch (err) { console.error(err); }
    setLoading(false);
  }

  async function handleAccept(id: string) {
    await quotationService.accept(id);
    if (selectedRfq) loadQuotations(selectedRfq);
  }

  async function handleReject(id: string) {
    await quotationService.reject(id);
    if (selectedRfq) loadQuotations(selectedRfq);
  }

  const filteredQuotations = quotations
    .filter((q) => statusFilter === "all" || q.status === statusFilter)
    .sort((a, b) => {
      const aVal = a[sortField] ?? 0;
      const bVal = b[sortField] ?? 0;
      return sortDir === "desc" ? Number(bVal) - Number(aVal) : Number(aVal) - Number(bVal);
    });

  const formatK = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
    return v.toFixed(0);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Quotation Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">Monitor, compare, and analyze vendor quotations</p>
      </div>

      {/* KPI Row */}
      {analytics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Quotations"
            value={analytics.total}
            subtitle="All time received"
            icon={<FileText className="w-5 h-5 text-white" />}
            color="blue"
          />
          <KPICard
            title="Pending Review"
            value={analytics.pending}
            subtitle="Awaiting decision"
            icon={<Clock className="w-5 h-5 text-white" />}
            color="amber"
          />
          <KPICard
            title="Accepted"
            value={analytics.accepted}
            subtitle={formatCurrency(analytics.accepted_value, "INR")}
            icon={<CheckCircle2 className="w-5 h-5 text-white" />}
            color="green"
          />
          <KPICard
            title="Avg AI Score"
            value={`${analytics.avg_ai_score}/100`}
            subtitle="Quality benchmark"
            icon={<Star className="w-5 h-5 text-white" />}
            color="purple"
          />
        </div>
      )}

      {/* Charts Row */}
      {analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AreaChartCard
            title="Quotations Received — Monthly"
            subtitle="Count of quotations over last 6 months"
            data={analytics.monthly_trend}
            dataKey="count"
            xKey="month"
            color="#6366f1"
            gradientId="quotTrend"
          />
          <BarChartCard
            title="Top Suppliers by Volume"
            subtitle="Number of quotations submitted"
            data={analytics.top_suppliers}
            dataKey="count"
            xKey="name"
            color="#10b981"
            layout="horizontal"
          />
        </div>
      )}

      {/* RFQ Selector + Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-500 mb-1.5 block">Select RFQ</label>
              <select
                className="w-full p-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                value={selectedRfq}
                onChange={(e) => loadQuotations(e.target.value)}
              >
                <option value="">-- Choose an RFQ to view quotations --</option>
                {rfqs.map((rfq) => (
                  <option key={rfq.id} value={rfq.id}>
                    {rfq.rfq_number} — {rfq.title}
                  </option>
                ))}
              </select>
            </div>
            {quotations.length > 0 && (
              <>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1.5 block">Status</label>
                  <select
                    className="p-2.5 border border-gray-200 rounded-lg text-sm bg-white"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">All</option>
                    <option value="received">Received</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1.5 block">Sort By</label>
                  <select
                    className="p-2.5 border border-gray-200 rounded-lg text-sm bg-white"
                    value={`${sortField}-${sortDir}`}
                    onChange={(e) => {
                      const [field, dir] = e.target.value.split("-");
                      setSortField(field as any);
                      setSortDir(dir as any);
                    }}
                  >
                    <option value="ai_score-desc">AI Score (High→Low)</option>
                    <option value="ai_score-asc">AI Score (Low→High)</option>
                    <option value="total_amount-asc">Price (Low→High)</option>
                    <option value="total_amount-desc">Price (High→Low)</option>
                    <option value="delivery_days-asc">Delivery (Fast)</option>
                    <option value="delivery_days-desc">Delivery (Slow)</option>
                  </select>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* AI Recommendation */}
      {comparison?.recommendation && (
        <div className="rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 p-5">
          <div className="flex items-start gap-3">
            <Trophy className="w-6 h-6 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-indigo-900">AI Recommendation</h3>
              <p className="text-sm mt-1 text-indigo-800">{comparison.recommendation}</p>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      )}

      {/* Interactive Table */}
      {!loading && filteredQuotations.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50/80">
                  <th className="text-left p-3 font-medium text-gray-600 w-8"></th>
                  <th className="text-left p-3 font-medium text-gray-600">Supplier</th>
                  <th className="text-left p-3 font-medium text-gray-600">Amount</th>
                  <th className="text-left p-3 font-medium text-gray-600">Tax</th>
                  <th className="text-left p-3 font-medium text-gray-600">Grand Total</th>
                  <th className="text-left p-3 font-medium text-gray-600">Delivery</th>
                  <th className="text-left p-3 font-medium text-gray-600">AI Score</th>
                  <th className="text-left p-3 font-medium text-gray-600">Status</th>
                  <th className="text-left p-3 font-medium text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredQuotations.map((q, idx) => (
                  <>
                    <tr
                      key={q.id}
                      className={`border-b hover:bg-gray-50/50 transition cursor-pointer ${q.ai_ranking === 1 ? "bg-indigo-50/30" : ""}`}
                      onClick={() => setExpandedRow(expandedRow === q.id ? null : q.id)}
                    >
                      <td className="p-3">
                        {expandedRow === q.id ? (
                          <ChevronDown className="w-4 h-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        )}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          {q.ai_ranking === 1 && (
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold">1</span>
                          )}
                          <span className="font-medium text-gray-900">{q.supplier_name || `Supplier ${idx + 1}`}</span>
                        </div>
                      </td>
                      <td className="p-3 font-medium">{formatCurrency(q.total_amount, q.currency)}</td>
                      <td className="p-3 text-gray-600">
                        {q.tax_percent ? `${q.tax_percent}%` : "—"}
                        {q.tax_amount ? ` (${formatCurrency(q.tax_amount, q.currency)})` : ""}
                      </td>
                      <td className="p-3 font-semibold text-gray-900">
                        {q.grand_total ? formatCurrency(q.grand_total, q.currency) : "—"}
                      </td>
                      <td className="p-3 text-gray-600">{q.delivery_days ? `${q.delivery_days} days` : "N/A"}</td>
                      <td className="p-3">
                        {q.ai_score != null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-indigo-500 rounded-full"
                                style={{ width: `${q.ai_score}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-gray-700">{q.ai_score}</span>
                          </div>
                        ) : "—"}
                      </td>
                      <td className="p-3">
                        <Badge className={getStatusColor(q.status)}>{q.status}</Badge>
                      </td>
                      <td className="p-3">
                        {q.status === "received" && (
                          <div className="flex gap-1.5">
                            <Button size="sm" variant="ghost" className="h-7 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50" onClick={(e) => { e.stopPropagation(); handleAccept(q.id); }}>
                              <Check className="w-3.5 h-3.5" />
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 text-rose-600 hover:text-rose-700 hover:bg-rose-50" onClick={(e) => { e.stopPropagation(); handleReject(q.id); }}>
                              <X className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {expandedRow === q.id && (
                      <tr key={`${q.id}-expanded`} className="bg-gray-50/50">
                        <td colSpan={9} className="p-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {q.items && q.items.length > 0 && (
                              <div className="md:col-span-2">
                                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Line Items</h4>
                                <div className="space-y-1">
                                  {q.items.map((item: any, i: number) => (
                                    <div key={i} className="flex justify-between text-xs p-2 bg-white rounded border">
                                      <span className="text-gray-700">{item.product_name}</span>
                                      <span className="text-gray-500">{item.quantity} × {formatCurrency(item.unit_price, q.currency)}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            <div>
                              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Details</h4>
                              <div className="space-y-2 text-xs">
                                {q.payment_terms && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-500">Payment</span>
                                    <span className="text-gray-700">{q.payment_terms}</span>
                                  </div>
                                )}
                                {q.validity_period && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-500">Validity</span>
                                    <span className="text-gray-700">{q.validity_period}</span>
                                  </div>
                                )}
                                {q.negotiation_round != null && (
                                  <div className="flex justify-between">
                                    <span className="text-gray-500">Round</span>
                                    <span className="text-gray-700">{q.negotiation_round}</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && selectedRfq && quotations.length === 0 && (
        <div className="text-center py-16">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">No quotations received for this RFQ yet</p>
          <p className="text-xs text-gray-400 mt-1">Quotations will appear here once suppliers respond</p>
        </div>
      )}

      {!selectedRfq && !analytics && (
        <div className="text-center py-16">
          <TrendingUp className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">Select an RFQ to view quotation details</p>
        </div>
      )}
    </div>
  );
}
