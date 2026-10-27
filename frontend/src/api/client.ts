import axios from "axios";

const TOKEN_KEY = "opd.access";
const REFRESH_KEY = "opd.refresh";

export const api = axios.create({ baseURL: "/api" });

export function getAccess() { return localStorage.getItem(TOKEN_KEY); }
export function getRefresh() { return localStorage.getItem(REFRESH_KEY); }
export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

api.interceptors.request.use((config) => {
  const token = getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      const refresh = getRefresh();
      if (!refresh) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(error);
      }
      original._retry = true;
      try {
        const { data } = await axios.post("/api/auth/refresh/", { refresh });
        setTokens(data.access, data.refresh ?? refresh);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (e) {
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(e);
      }
    }
    return Promise.reject(error);
  }
);
