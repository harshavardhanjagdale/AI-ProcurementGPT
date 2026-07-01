import api from "./api";
import type { PurchaseOrder } from "@/types";

export const purchaseOrderService = {
  async list(params?: { page?: number; limit?: number; status?: string }) {
    const { data } = await api.get("/purchase-orders", { params });
    return data;
  },

  async get(id: string) {
    const { data } = await api.get<PurchaseOrder>(`/purchase-orders/${id}`);
    return data;
  },

  async create(quotationId: string, deliveryDate?: string, paymentTerms?: string) {
    const { data } = await api.post("/purchase-orders", {
      quotation_id: quotationId,
      delivery_date: deliveryDate,
      payment_terms: paymentTerms,
    });
    return data;
  },

  async approve(id: string) {
    const { data } = await api.post(`/purchase-orders/${id}/approve`);
    return data;
  },

  async send(id: string) {
    const { data } = await api.post(`/purchase-orders/${id}/send`);
    return data;
  },

  getDownloadUrl(id: string) {
    return `${api.defaults.baseURL}/purchase-orders/${id}/download`;
  },
};
