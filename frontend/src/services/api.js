// Thin wrapper around fetch. All metrics shown in the UI come from these Django endpoints.
const BASE = import.meta.env.VITE_API_BASE || '/api';

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function query(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.append(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : '';
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      ...options,
    });
  } catch {
    throw new ApiError('Cannot reach the API. Is the Django server running on port 8000?', 0);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    const details = err?.details;
    let message = err?.message || `Request failed (${res.status})`;
    if (details && typeof details === 'object') {
      message = Object.entries(details)
        .map(([k, v]) => `${k === 'non_field_errors' ? '' : `${k}: `}${Array.isArray(v) ? v.join(' ') : typeof v === 'object' ? JSON.stringify(v) : v}`)
        .join('; ');
    }
    throw new ApiError(message, res.status, details);
  }
  return body;
}

export const api = {
  get: (path, params) => request(`${path}${query(params)}`),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
};
