import api from "./api";

export const authService = {
  async login(email: string, password: string) {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return data;
  },

  async register(email: string, password: string, full_name: string, role: string = "procurement_manager") {
    const { data } = await api.post("/auth/register", { email, password, full_name, role });
    return data;
  },

  async getMe() {
    const { data } = await api.get("/auth/me");
    return data;
  },

  logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  },

  isAuthenticated(): boolean {
    if (typeof window === "undefined") return false;
    return !!localStorage.getItem("access_token");
  },
};
