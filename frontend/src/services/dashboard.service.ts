import api from "./api";
import type { DashboardStats } from "@/types";

export interface QuotationAnalytics {
  total: number;
  pending: number;
  accepted: number;
  rejected: number;
  accepted_value: number;
  avg_ai_score: number;
  by_status: Record<string, number>;
  monthly_trend: { month: string; count: number; value: number }[];
  top_suppliers: { name: string; count: number; avg_score: number }[];
}

export interface NegotiationAnalytics {
  total: number;
  active: number;
  completed: number;
  failed: number;
  success_rate: number;
  total_savings: number;
  avg_savings_pct: number;
  avg_rounds: number;
  by_status: Record<string, number>;
  monthly_savings: { month: string; savings: number; count: number }[];
}

export interface POAnalytics {
  total: number;
  pending_approvals: number;
  total_spend: number;
  avg_po_value: number;
  overdue: number;
  by_status: Record<string, number>;
  tax_breakdown: { subtotal: number; tax: number; grand_total: number };
  monthly_spend: { month: string; spend: number; count: number }[];
  top_suppliers: { name: string; value: number; count: number }[];
}

export interface SupplierPerformance {
  top_suppliers: { id: string; name: string; rating: number; country: string; po_count: number; total_value: number }[];
  response_times: { name: string; avg_days: number }[];
  win_rates: { name: string; quotes: number; wins: number; rate: number }[];
}

export interface ProcurementOverview {
  monthly_spend: { month: string; spend: number }[];
  workflow_stats: { total: number; completed: number; failed: number; cancelled: number };
  avg_cycle_days: number;
}

export const dashboardService = {
  async getStats() {
    const { data } = await api.get<DashboardStats>("/dashboard/stats");
    return data;
  },

  async getRecentActivity() {
    const { data } = await api.get("/dashboard/recent-activity");
    return data;
  },

  async getPipeline() {
    const { data } = await api.get("/dashboard/rfq-pipeline");
    return data;
  },

  async getQuotationAnalytics() {
    const { data } = await api.get<QuotationAnalytics>("/dashboard/quotation-analytics");
    return data;
  },

  async getNegotiationAnalytics() {
    const { data } = await api.get<NegotiationAnalytics>("/dashboard/negotiation-analytics");
    return data;
  },

  async getPOAnalytics() {
    const { data } = await api.get<POAnalytics>("/dashboard/po-analytics");
    return data;
  },

  async getSupplierPerformance() {
    const { data } = await api.get<SupplierPerformance>("/dashboard/supplier-performance");
    return data;
  },

  async getProcurementOverview() {
    const { data } = await api.get<ProcurementOverview>("/dashboard/procurement-overview");
    return data;
  },
};
