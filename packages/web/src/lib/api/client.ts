import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { ApiError } from './types';

// Auth utilities - imported dynamically to avoid circular dependencies
let authUtils: any = null;

const getAuthUtils = async () => {
  if (!authUtils && typeof window !== 'undefined') {
    try {
      authUtils = await import('@/lib/auth/utils');
    } catch {
      // Auth not available, continue without it
    }
  }
  return authUtils;
};

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds - accommodates LLM operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth and logging
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Add authentication token if available
    if (typeof window !== 'undefined') {
      try {
        const auth = await getAuthUtils();
        const token = auth?.storage?.getToken();
        if (token && !auth.isTokenExpired(token)) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch {
        // Fallback to localStorage for backward compatibility
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    }

    // Log request in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, {
        params: config.params,
        data: config.data,
      });
    }

    return config;
  },
  (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and logging
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log response in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`API Response: ${response.config.method?.toUpperCase()} ${response.config.url}`, {
        status: response.status,
        data: response.data,
      });
    }

    return response;
  },
  (error: AxiosError<ApiError>) => {
    // Enhanced error handling
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;
      
      console.error(`API Error ${status}:`, data);

      // Handle specific error types
      switch (status) {
        case 401:
          // Unauthorized - clear auth and redirect to login
          if (typeof window !== 'undefined') {
            getAuthUtils().then(auth => {
              if (auth?.storage?.clearAuth) {
                auth.storage.clearAuth();
              } else {
                // Fallback to localStorage
                localStorage.removeItem('auth_token');
              }
              
              // Trigger logout event for auth context
              window.dispatchEvent(new CustomEvent('auth:logout'));
              
              // Redirect to login if not already there
              if (!window.location.pathname.includes('/login')) {
                const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
                window.location.href = `/login?returnUrl=${returnUrl}`;
              }
            });
          }
          break;
        case 403:
          // Forbidden
          console.error('Access denied:', data?.detail);
          break;
        case 404:
          // Not found
          console.error('Resource not found:', data?.detail);
          break;
        case 422:
          // Validation error (FastAPI)
          console.error('Validation error:', data);
          break;
        case 500:
          // Server error
          console.error('Server error:', data?.detail);
          break;
        default:
          console.error('API error:', data?.detail || 'Unknown error');
      }

      // Create user-friendly error message
      const userMessage = data?.detail || `Server error (${status})`;
      
      return Promise.reject(new Error(userMessage));
    } else if (error.request) {
      // Network error
      console.error('Network error:', error.message);
      return Promise.reject(new Error('Network error - please check your connection'));
    } else {
      // Request setup error
      console.error('Request error:', error.message);
      return Promise.reject(new Error('Request failed'));
    }
  }
);

// Helper functions for common patterns

/**
 * Generic GET request
 */
export async function get<T>(url: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

/**
 * Generic POST request
 */
export async function post<T, D = any>(url: string, data?: D): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

/**
 * Generic PUT request
 */
export async function put<T, D = any>(url: string, data?: D): Promise<T> {
  const response = await apiClient.put<T>(url, data);
  return response.data;
}

/**
 * Generic PATCH request
 */
export async function patch<T, D = any>(url: string, data?: D): Promise<T> {
  const response = await apiClient.patch<T>(url, data);
  return response.data;
}

/**
 * Generic DELETE request
 */
export async function del<T>(url: string): Promise<T> {
  const response = await apiClient.delete<T>(url);
  return response.data;
}

/**
 * File upload request with progress tracking
 */
export async function uploadFile(
  url: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(progress);
      }
    },
  });

  return response.data;
}

/**
 * Download file with proper handling
 */
export async function downloadFile(
  url: string,
  filename: string,
  params?: Record<string, any>
): Promise<void> {
  const response = await apiClient.get(url, {
    params,
    responseType: 'blob',
  });

  // Create download link
  const blob = new Blob([response.data]);
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

/**
 * Check if the API is healthy
 */
export async function healthCheck(): Promise<boolean> {
  try {
    await apiClient.get('/health');
    return true;
  } catch {
    return false;
  }
}

// Alias for backward compatibility
export const api = apiClient;

export default apiClient;