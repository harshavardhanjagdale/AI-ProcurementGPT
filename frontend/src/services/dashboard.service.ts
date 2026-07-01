import api from "./api";
import type { DashboardStats } from "@/types";

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
};
