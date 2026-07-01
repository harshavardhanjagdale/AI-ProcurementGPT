import api from "./api";
import type { RFQ, PaginatedResponse } from "@/types";

export const rfqService = {
  async list(params?: { page?: number; limit?: number; status?: string }) {
    const { data } = await api.get<PaginatedResponse<RFQ>>("/rfqs", { params });
    return data;
  },

  async get(id: string) {
    const { data } = await api.get<RFQ>(`/rfqs/${id}`);
    return data;
  },

  async create(rfq: { title: string; description?: string; items: any[]; budget_min?: number; budget_max?: number; currency?: string; delivery_deadline?: string; supplier_ids?: string[] }) {
    const { data } = await api.post<RFQ>("/rfqs", rfq);
    return data;
  },

  async update(id: string, rfq: Partial<RFQ>) {
    const { data } = await api.put<RFQ>(`/rfqs/${id}`, rfq);
    return data;
  },

  async cancel(id: string) {
    const { data } = await api.delete(`/rfqs/${id}`);
    return data;
  },

  async sendEmails(id: string) {
    const { data } = await api.post(`/emails/send-rfq/${id}`);
    return data;
  },
};
