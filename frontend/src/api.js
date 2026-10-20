export class SessionExpiredError extends Error {
  constructor() {
    super('Session expired, please log in again');
    this.name = 'SessionExpiredError';
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, options) {
  const res = await fetch(path, options);
  if (res.status === 401) {
    throw new SessionExpiredError();
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore - use default message
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export function getStatus() {
  return request('/api/status');
}

export function getProfile() {
  return request('/api/profile');
}

export function loginWithToken(requestToken) {
  return request('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_token: requestToken }),
  });
}

export function getSignals({ short, long, lookback }) {
  const params = new URLSearchParams({ short, long, lookback });
  return request(`/api/signals?${params.toString()}`);
}

export function getSymbols() {
  return request('/api/symbols');
}

function postJson(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function runSingleBacktest(payload) {
  return postJson('/api/backtest/single', payload);
}

export function startUniverseBacktest(payload) {
  return postJson('/api/backtest/all', payload);
}

export function getBacktestJob(jobId) {
  return request(`/api/backtest/jobs/${jobId}`);
}

export function runParameterSweep(payload) {
  return postJson('/api/backtest/sweep', payload);
}
