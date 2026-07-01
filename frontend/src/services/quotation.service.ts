import api from "./api";
import type { Quotation } from "@/types";

export const quotationService = {
  async listByRfq(rfqId: string) {
    const { data } = await api.get<Quotation[]>(`/quotations/rfq/${rfqId}`);
    return data;
  },

  async get(id: string) {
    const { data } = await api.get<Quotation>(`/quotations/${id}`);
    return data;
  },

  async compare(rfqId: string) {
    const { data } = await api.get(`/quotations/rfq/${rfqId}/compare`);
    return data;
  },

  async accept(id: string) {
    const { data } = await api.post(`/quotations/${id}/accept`);
    return data;
  },

  async reject(id: string) {
    const { data } = await api.post(`/quotations/${id}/reject`);
    return data;
  },

  async triggerOCR(rfqId: string) {
    const { data } = await api.post(`/quotations/rfq/${rfqId}/process-ocr`);
    return data;
  },
};
