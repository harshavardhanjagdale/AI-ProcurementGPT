import api from "./api";

export interface LLMSettingsResponse {
  provider: string;
  model: string;
  api_key_hint: string;
  is_configured: boolean;
}

export interface LLMModel {
  id: string;
  name: string;
}

export interface ModelsResponse {
  providers: Record<string, LLMModel[]>;
}

export interface ProviderModelsResponse {
  provider: string;
  models: LLMModel[];
}

export interface ValidateResponse {
  valid: boolean;
  message: string;
}

export const settingsService = {
  async getLLMSettings(): Promise<LLMSettingsResponse> {
    const response = await api.get("/settings/llm");
    return response.data;
  },

  async updateLLMSettings(data: {
    provider: string;
    api_key: string;
    model: string;
  }): Promise<{ message: string; provider: string; model: string }> {
    const response = await api.patch("/settings/llm", data);
    return response.data;
  },

  async validateKey(data: {
    provider: string;
    api_key: string;
    model: string;
  }): Promise<ValidateResponse> {
    const response = await api.post("/settings/llm/validate", data);
    return response.data;
  },

  async getAvailableModels(provider?: string): Promise<ModelsResponse | ProviderModelsResponse> {
    const params = provider ? { provider } : {};
    const response = await api.get("/settings/llm/models", { params });
    return response.data;
  },

  async removeKey(): Promise<{ message: string; provider: string; model: string }> {
    const response = await api.delete("/settings/llm");
    return response.data;
  },
};
