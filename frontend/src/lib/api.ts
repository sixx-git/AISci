import axios from 'axios';
import env from '@/config/env';

const rawBaseURL = env.API_BASE_URL?.trim() || '';
const normalizedBaseURL = rawBaseURL.replace(/\/$/, '');

const baseURL = normalizedBaseURL
  ? `${normalizedBaseURL}/api/v1`
  : '/api/v1';

const api = axios.create({
  baseURL,
  timeout: 120000,
});

api.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const serverMessage =
      error.response?.data?.message ||
      error.response?.data?.detail;

    const message = serverMessage || error.message || '请求失败';
    const finalMessage = status ? `[${status}] ${message}` : message;

    if (import.meta.env.DEV) {
      console.error('[API Error]', error.config?.url, finalMessage);
    }

    return Promise.reject(new Error(finalMessage));
  },
);

export default api;