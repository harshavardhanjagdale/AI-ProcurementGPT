export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Supplier {
  id: string;
  name: string;
  email: string;
  phone?: string;
  country: string;
  city?: string;
  address?: string;
  rating: number;
  avg_delivery_days?: number;
  status: string;
  categories: { id: string; category_name: string }[];
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface RFQItem {
  id: string;
  product_name: string;
  specifications?: string;
  quantity: number;
  unit: string;
  estimated_unit_price?: number;
}

export interface RFQ {
  id: string;
  rfq_number: string;
  user_id: string;
  title: string;
  description?: string;
  budget_min?: number;
  budget_max?: number;
  currency: string;
  delivery_deadline?: string;
  status: string;
  ai_workflow_id?: string;
  items: RFQItem[];
  suppliers: { id: string; supplier_id: string; status: string }[];
  created_at: string;
  updated_at: string;
}

export interface Quotation {
  id: string;
  rfq_id: string;
  supplier_id: string;
  supplier_name?: string;
  total_amount: number;
  currency: string;
  delivery_days?: number;
  warranty_terms?: string;
  payment_terms?: string;
  ai_ranking?: number;
  status: string;
  items: QuotationItem[];
  tax_percent?: number;
  tax_amount?: number;
  grand_total?: number;
  validity_period?: string;
  negotiation_round?: number;
  created_at: string;
}

export interface QuotationItem {
  id: string;
  product_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
  specifications?: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  rfq_id: string;
  supplier_id: string;
  total_amount: number;
  currency: string;
  delivery_date?: string;
  payment_terms?: string;
  status: string;
  pdf_path?: string;
  items: { product_name: string; unit_price: number; quantity: number; total_price: number }[];
  created_at: string;
}

export interface Negotiation {
  id: string;
  rfq_id: string;
  supplier_id: string;
  round_number: number;
  original_price: number;
  target_price: number;
  negotiated_price?: number;
  status: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  rfq_id?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface DashboardStats {
  total_rfqs: number;
  active_rfqs: number;
  total_suppliers: number;
  total_purchase_orders: number;
  total_po_value: number;
  total_quotations: number;
  negotiation_savings: number;
  rfqs_by_status: Record<string, number>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}
