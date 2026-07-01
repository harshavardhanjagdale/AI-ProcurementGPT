import api from "./api";
import type { Negotiation } from "@/types";

export const negotiationService = {
  async list(params?: { rfq_id?: string; status?: string }) {
    const { data } = await api.get("/negotiations", { params });
    return data;
  },

  async get(id: string) {
    const { data } = await api.get<Negotiation>(`/negotiations/${id}`);
    return data;
  },

  async initiate(rfqId: string, supplierId: string, targetPrice: number) {
    const { data } = await api.post("/negotiations", {
      rfq_id: rfqId,
      supplier_id: supplierId,
      target_price: targetPrice,
    });
    return data;
  },

  async accept(id: string) {
    const { data } = await api.post(`/negotiations/${id}/accept`);
    return data;
  },

  async reject(id: string) {
    const { data } = await api.post(`/negotiations/${id}/reject`);
    return data;
  },
};
