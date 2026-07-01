import api from "./api";
import type { Supplier, PaginatedResponse } from "@/types";

export const supplierService = {
  async list(params?: { page?: number; limit?: number; status?: string; country?: string; category?: string }) {
    const { data } = await api.get<PaginatedResponse<Supplier>>("/suppliers", { params });
    return data;
  },

  async get(id: string) {
    const { data } = await api.get<Supplier>(`/suppliers/${id}`);
    return data;
  },

  async create(supplier: Partial<Supplier> & { categories?: string[] }) {
    const { data } = await api.post<Supplier>("/suppliers", supplier);
    return data;
  },

  async update(id: string, supplier: Partial<Supplier> & { categories?: string[] }) {
    const { data } = await api.put<Supplier>(`/suppliers/${id}`, supplier);
    return data;
  },

  async delete(id: string) {
    await api.delete(`/suppliers/${id}`);
  },
};
