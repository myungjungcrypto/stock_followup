export type TrackingItem = {
  id: number;
  stock_id: number;
  label: string;
  rationale: string;
  query: string;
  priority: number;
  cadence_minutes: number;
  enabled: boolean;
  last_checked_at: string | null;
  created_at: string;
};

export type EventItem = {
  id: number;
  stock_id: number;
  tracking_item_id: number | null;
  title: string;
  summary: string;
  url: string | null;
  source: string;
  published_at: string | null;
  relevance_score: number;
  sentiment: string;
  created_at: string;
};

export type Decision = {
  id: number;
  stock_id: number;
  event_id: number | null;
  action: string;
  confidence: number;
  reasoning: string;
  counterpoints: string;
  created_at: string;
};

export type Note = {
  id: number;
  stock_id: number;
  title: string;
  url: string | null;
  source_type: string;
  content: string;
  created_at: string;
};

export type Alert = {
  id: number;
  stock_id: number;
  decision_id: number | null;
  channel: string;
  message: string;
  sent: boolean;
  error: string | null;
  created_at: string;
};

export type Stock = {
  id: number;
  ticker: string;
  company_name: string;
  market: string;
  status: string;
  position_type: string;
  average_price: number | null;
  target_price: number | null;
  stop_loss: number | null;
  thesis: string;
  importance: number;
  check_interval_minutes: number;
  created_at: string;
  updated_at: string;
  notes: Note[];
  tracking_items: TrackingItem[];
  events: EventItem[];
  decisions: Decision[];
  alerts: Alert[];
};

export type StockPayload = {
  ticker: string;
  company_name: string;
  market: string;
  status: string;
  position_type: string;
  thesis: string;
  importance: number;
  check_interval_minutes: number;
  average_price?: number | null;
  target_price?: number | null;
  stop_loss?: number | null;
};

export type NotePayload = {
  title: string;
  url?: string | null;
  source_type: string;
  content: string;
};

export type TrackingItemPayload = {
  label: string;
  rationale: string;
  query: string;
  priority: number;
  cadence_minutes: number;
  enabled: boolean;
};

const jsonHeaders = { "Content-Type": "application/json" };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listStocks: () => request<Stock[]>("/api/stocks"),
  createStock: (payload: StockPayload) =>
    request<Stock>("/api/stocks", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    }),
  addNote: (stockId: number, payload: NotePayload) =>
    request<Stock>(`/api/stocks/${stockId}/notes`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    }),
  addTrackingItem: (stockId: number, payload: TrackingItemPayload) =>
    request<Stock>(`/api/stocks/${stockId}/tracking-items`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    }),
  scanStock: (stockId: number) =>
    request<{ stock_id: number; events_created: number; decisions_created: number; alerts_created: number }>(
      `/api/stocks/${stockId}/scan`,
      { method: "POST" }
    )
};
