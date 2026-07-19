import api from "./api";

export interface WorkflowSessionSummary {
  id: string;
  title: string;
  status: string;
  status_emoji: string;
  current_step: string | null;
  current_agent: string | null;
  progress_percentage: number;
  rfq_id: string | null;
  updated_at: string;
  created_at: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  display_name: string;
  status: string;
  agent: string | null;
  order_index: number;
  started_at: string | null;
  completed_at: string | null;
  execution_time_ms: number | null;
  error_message: string | null;
}

export interface WorkflowEvent {
  id: string;
  event_type: string;
  title: string;
  description: string | null;
  agent: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "system" | "event";
  content: string;
  message_type: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface QuotationItem {
  product_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
}

export interface Quotation {
  id: string;
  supplier_id: string;
  supplier_name: string;
  total_amount: number;
  tax_percent: number | null;
  tax_amount: number | null;
  grand_total: number | null;
  currency: string;
  delivery_days: number | null;
  warranty_terms: string | null;
  payment_terms: string | null;
  validity_days: number | null;
  ai_ranking: number | null;
  is_recommended: boolean;
  negotiation_round: number;
  strengths: string[];
  weaknesses: string[];
  status: string;
  items: QuotationItem[];
}

export interface WorkflowSessionDetail extends WorkflowSessionSummary {
  current_node: string | null;
  langgraph_thread_id: string | null;
  started_at: string;
  completed_at: string | null;
  steps?: WorkflowStep[];
}

export type WorkflowEventType =
  | "workflow_progress"
  | "chat_message"
  | "workflow_complete"
  | "workflow_error"
  | "state_sync"
  | "ping"
  | "error"
  // Event-driven quotation / negotiation / PO processing events (see useWorkflowSocket)
  | "quotation_received"
  | "quotation_ocr_started"
  | "quotation_ocr_complete"
  | "quotation_extracting"
  | "quotation_validated"
  | "quotation_ready"
  | "quotation_failed"
  | "comparison_ready"
  | "negotiation_draft_ready"
  | "negotiation_sent"
  | "po_preview_ready"
  | "po_finalized";

export interface WorkflowProgressEvent {
  type: WorkflowEventType;
  workflowId: string;
  currentStep?: string | null;
  stepIndex?: number;
  totalSteps?: number;
  progress?: number;
  currentStage?: string;
  currentAgent?: string | null;
  status?: string;
  title?: string | null;
  message?: string | null;
  timestamp?: string;
  steps?: WorkflowStep[];
  chatMessage?: ConversationMessage | null;
  messages?: ConversationMessage[];
}

export const workflowService = {
  async listSessions(params?: { page?: number; limit?: number; status?: string }) {
    const { data } = await api.get("/workflow/sessions", { params });
    return data as { items: WorkflowSessionSummary[]; total: number };
  },

  async getSession(id: string) {
    const { data } = await api.get(`/workflow/${id}`);
    return data as WorkflowSessionDetail;
  },

  async getSteps(id: string) {
    const { data } = await api.get(`/workflow/${id}/steps`);
    return data as { steps: WorkflowStep[] };
  },

  async getEvents(id: string, limit = 50) {
    const { data } = await api.get(`/workflow/${id}/events`, { params: { limit } });
    return data as { events: WorkflowEvent[] };
  },

  async getChat(id: string, limit = 100) {
    const { data } = await api.get(`/workflow/${id}/chat`, { params: { limit } });
    return data as { messages: ConversationMessage[] };
  },

  async getQuotations(id: string) {
    const { data } = await api.get(`/workflow/${id}/quotations`);
    return data as { quotations: Quotation[] };
  },

  async createSession(title?: string) {
    const { data } = await api.post("/workflow/new", { title });
    return data as WorkflowSessionDetail;
  },

  async continueSession(id: string, message: string) {
    const { data } = await api.post(`/workflow/${id}/continue`, { message });
    return data as {
      message: string;
      session: WorkflowSessionDetail;
      steps: WorkflowStep[];
      current_step: string;
      workflow_id: string;
    };
  },

  async submitDecision(
    id: string,
    decision: "approve" | "negotiate" | "cancel",
    targetPrice?: number,
    quotationId?: string
  ) {
    const { data } = await api.post(`/workflow/${id}/decision`, {
      decision,
      target_price: targetPrice ?? null,
      quotation_id: quotationId ?? null,
    });
    return data as {
      message: string;
      session: WorkflowSessionDetail;
      current_step: string;
      error: string | null;
    };
  },

  async renameSession(id: string, title: string) {
    const { data } = await api.post(`/workflow/${id}/rename`, { title });
    return data;
  },

  async deleteSession(id: string) {
    const { data } = await api.delete(`/workflow/${id}`);
    return data;
  },
};
