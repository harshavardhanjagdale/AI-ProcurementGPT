import api from "./api";

export const chatService = {
  async sendMessage(message: string, rfqId?: string, workflowId?: string) {
    const { data } = await api.post("/chat", { message, rfq_id: rfqId, workflow_id: workflowId });
    return data;
  },

  async submitDecision(workflowId: string, decision: string, targets?: any[]) {
    const { data } = await api.post("/chat/decision", {
      workflow_id: workflowId,
      decision,
      negotiation_targets: targets,
    });
    return data;
  },

  async getHistory(rfqId?: string) {
    const params = rfqId ? { rfq_id: rfqId } : {};
    const { data } = await api.get("/chat/history", { params });
    return data;
  },

  async getWorkflowStatus(workflowId: string) {
    const { data } = await api.get(`/chat/workflow/${workflowId}/status`);
    return data;
  },
};
