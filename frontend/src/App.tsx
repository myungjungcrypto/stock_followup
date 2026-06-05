import {
  Activity,
  Bell,
  BookOpen,
  Clock,
  CirclePlus,
  ExternalLink,
  FileText,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, Stock } from "./api";

const actionTone: Record<string, string> = {
  NO_ACTION: "neutral",
  WATCH: "watch",
  RESEARCH: "research",
  POSITIVE: "positive",
  NEGATIVE: "negative",
  REDUCE_RISK: "risk",
  EXIT_CHECK: "risk"
};

const initialStock = {
  ticker: "",
  company_name: "",
  market: "US",
  status: "watching",
  position_type: "watchlist",
  thesis: "",
  importance: 3,
  check_interval_minutes: 180,
  average_price: null,
  target_price: null,
  stop_loss: null
};

function App() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [stockForm, setStockForm] = useState(initialStock);
  const [noteForm, setNoteForm] = useState({ title: "", url: "", source_type: "memo", content: "" });
  const [trackingForm, setTrackingForm] = useState({
    label: "",
    rationale: "",
    query: "",
    priority: 3,
    cadence_minutes: 180,
    enabled: true
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selected = useMemo(
    () => stocks.find((stock) => stock.id === selectedId) ?? stocks[0] ?? null,
    [selectedId, stocks]
  );

  useEffect(() => {
    void loadStocks();
  }, []);

  async function loadStocks() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.listStocks();
      setStocks(data);
      if (!selectedId && data[0]) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const created = await api.createStock(stockForm);
      setStocks((current) => [created, ...current]);
      setSelectedId(created.id);
      setStockForm(initialStock);
      setNotice(`${created.ticker} 종목을 추가했습니다.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "종목을 추가하지 못했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function submitNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.addNote(selected.id, {
        ...noteForm,
        url: noteForm.url || null
      });
      setStocks((current) => current.map((stock) => (stock.id === updated.id ? updated : stock)));
      setNoteForm({ title: "", url: "", source_type: "memo", content: "" });
      setNotice("메모를 분석해서 팔로우업 항목을 갱신했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "메모 분석에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function submitTrackingItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.addTrackingItem(selected.id, trackingForm);
      setStocks((current) => current.map((stock) => (stock.id === updated.id ? updated : stock)));
      setTrackingForm({ label: "", rationale: "", query: "", priority: 3, cadence_minutes: 180, enabled: true });
      setNotice("수동 팔로우업 항목을 추가했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "팔로우업 항목을 추가하지 못했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function scanSelected() {
    if (!selected) return;
    setIsScanning(true);
    setError(null);
    try {
      const result = await api.scanStock(selected.id);
      await loadStocks();
      setSelectedId(selected.id);
      setNotice(
        `스캔 완료: 새 이벤트 ${result.events_created}개, 판단 ${result.decisions_created}개, 알림 ${result.alerts_created}개, 제외 ${result.events_skipped}개`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "스캔에 실패했습니다.");
    } finally {
      setIsScanning(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Stock Follow-Up</h1>
          <p>투자 논리에서 추적 항목을 뽑고, 새 정보가 thesis를 바꾸는지 감시합니다.</p>
        </div>
        <button className="icon-button" onClick={() => void loadStocks()} title="새로고침">
          <RefreshCw size={18} />
        </button>
      </header>

      {error && <div className="banner error">{error}</div>}
      {notice && <div className="banner notice">{notice}</div>}

      <section className="workspace">
        <aside className="sidebar">
          <form className="panel add-form" onSubmit={submitStock}>
            <div className="panel-title">
              <CirclePlus size={18} />
              <h2>종목 추가</h2>
            </div>
            <div className="form-grid">
              <label>
                티커
                <input
                  value={stockForm.ticker}
                  onChange={(event) => setStockForm({ ...stockForm, ticker: event.target.value })}
                  placeholder="NVDA"
                  required
                />
              </label>
              <label>
                회사명
                <input
                  value={stockForm.company_name}
                  onChange={(event) => setStockForm({ ...stockForm, company_name: event.target.value })}
                  placeholder="NVIDIA"
                  required
                />
              </label>
              <label>
                시장
                <input
                  value={stockForm.market}
                  onChange={(event) => setStockForm({ ...stockForm, market: event.target.value })}
                />
              </label>
              <label>
                상태
                <select
                  value={stockForm.position_type}
                  onChange={(event) => setStockForm({ ...stockForm, position_type: event.target.value })}
                >
                  <option value="watchlist">관심</option>
                  <option value="holding">보유</option>
                  <option value="candidate">매수 후보</option>
                </select>
              </label>
              <label className="wide">
                투자 논리
                <textarea
                  value={stockForm.thesis}
                  onChange={(event) => setStockForm({ ...stockForm, thesis: event.target.value })}
                  placeholder="왜 이 종목을 보고 있는지, 깨지면 안 되는 전제는 무엇인지"
                  rows={4}
                />
              </label>
            </div>
            <button className="primary-button" disabled={isSaving}>
              <CirclePlus size={17} />
              추가
            </button>
          </form>

          <div className="panel watchlist">
            <div className="panel-title">
              <Activity size={18} />
              <h2>Watchlist</h2>
            </div>
            {isLoading ? (
              <div className="empty">불러오는 중</div>
            ) : stocks.length === 0 ? (
              <div className="empty">추적할 종목을 추가하세요.</div>
            ) : (
              <div className="stock-list">
                {stocks.map((stock) => {
                  const latest = stock.decisions[stock.decisions.length - 1];
                  return (
                    <button
                      key={stock.id}
                      className={stock.id === selected?.id ? "stock-row active" : "stock-row"}
                      onClick={() => setSelectedId(stock.id)}
                    >
                      <span>
                        <strong>{stock.ticker}</strong>
                        <small>{stock.company_name}</small>
                      </span>
                      <span className={`pill ${latest ? actionTone[latest.action] : "neutral"}`}>
                        {latest?.action ?? "NEW"}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        <section className="detail">
          {!selected ? (
            <div className="panel empty-state">
              <Search size={32} />
              <h2>종목을 추가하면 분석 흐름이 시작됩니다.</h2>
            </div>
          ) : (
            <>
              <div className="detail-header">
                <div>
                  <span className="eyebrow">{selected.market}</span>
                  <h2>
                    {selected.ticker} <small>{selected.company_name}</small>
                  </h2>
                </div>
                <button className="primary-button" onClick={() => void scanSelected()} disabled={isScanning}>
                  <Play size={17} />
                  {isScanning ? "스캔 중" : "지금 스캔"}
                </button>
              </div>

              <div className="metrics">
                <Metric label="추적 항목" value={selected.tracking_items.length} />
                <Metric label="뉴스 이벤트" value={selected.events.length} />
                <Metric label="판단 기록" value={selected.decisions.length} />
                <Metric label="알림" value={selected.alerts.length} />
              </div>

              <section className="panel thesis-panel">
                <div className="panel-title">
                  <BookOpen size={18} />
                  <h2>투자 논리</h2>
                </div>
                <p>{selected.thesis || "등록된 투자 논리가 없습니다."}</p>
              </section>

              <div className="two-column">
                <section className="panel">
                  <div className="panel-title">
                    <FileText size={18} />
                    <h2>입력 메모</h2>
                  </div>
                  <form className="note-form" onSubmit={submitNote}>
                    <input
                      value={noteForm.title}
                      onChange={(event) => setNoteForm({ ...noteForm, title: event.target.value })}
                      placeholder="제목"
                    />
                    <input
                      value={noteForm.url}
                      onChange={(event) => setNoteForm({ ...noteForm, url: event.target.value })}
                      placeholder="URL"
                    />
                    <textarea
                      value={noteForm.content}
                      onChange={(event) => setNoteForm({ ...noteForm, content: event.target.value })}
                      placeholder="기사, 글, 내 생각을 붙여넣기"
                      rows={8}
                      required
                    />
                    <button className="primary-button" disabled={isSaving}>
                      <Sparkles size={17} />
                      분석
                    </button>
                  </form>
                </section>

                <section className="panel">
                  <div className="panel-title">
                    <Search size={18} />
                    <h2>팔로우업 항목</h2>
                  </div>
                  <form className="tracking-form" onSubmit={submitTrackingItem}>
                    <input
                      value={trackingForm.label}
                      onChange={(event) => setTrackingForm({ ...trackingForm, label: event.target.value })}
                      placeholder="직접 추가할 추적 항목"
                      required
                    />
                    <input
                      value={trackingForm.query}
                      onChange={(event) => setTrackingForm({ ...trackingForm, query: event.target.value })}
                      placeholder="검색어"
                      required
                    />
                    <div className="compact-controls">
                      <label>
                        우선순위
                        <input
                          min="1"
                          max="5"
                          type="number"
                          value={trackingForm.priority}
                          onChange={(event) =>
                            setTrackingForm({ ...trackingForm, priority: Number(event.target.value) })
                          }
                        />
                      </label>
                      <label>
                        주기
                        <select
                          value={trackingForm.cadence_minutes}
                          onChange={(event) =>
                            setTrackingForm({ ...trackingForm, cadence_minutes: Number(event.target.value) })
                          }
                        >
                          <option value={60}>1시간</option>
                          <option value={180}>3시간</option>
                          <option value={360}>6시간</option>
                          <option value={720}>12시간</option>
                          <option value={1440}>1일</option>
                        </select>
                      </label>
                    </div>
                    <textarea
                      value={trackingForm.rationale}
                      onChange={(event) => setTrackingForm({ ...trackingForm, rationale: event.target.value })}
                      placeholder="왜 중요한지"
                      rows={3}
                    />
                    <button className="secondary-button" disabled={isSaving}>
                      <CirclePlus size={16} />
                      항목 추가
                    </button>
                  </form>
                  <div className="tracking-list">
                    {selected.tracking_items.length === 0 ? (
                      <div className="empty">메모를 입력하면 자동 생성됩니다.</div>
                    ) : (
                      selected.tracking_items.map((item) => (
                        <article key={item.id} className="tracking-item">
                          <div>
                            <strong>{item.label}</strong>
                            <p>{item.rationale}</p>
                            <small>{item.query}</small>
                            <small>
                              <Clock size={13} />
                              {formatCadence(item.cadence_minutes)}
                              {item.last_checked_at ? ` · 마지막 확인 ${formatDate(item.last_checked_at)}` : ""}
                            </small>
                          </div>
                          <span className="score">P{item.priority}</span>
                        </article>
                      ))
                    )}
                  </div>
                </section>
              </div>

              <section className="panel">
                <div className="panel-title">
                  <ShieldAlert size={18} />
                  <h2>최근 판단</h2>
                </div>
                <div className="decision-list">
                  {selected.decisions.length === 0 ? (
                    <div className="empty">아직 판단 기록이 없습니다.</div>
                  ) : (
                    [...selected.decisions].reverse().slice(0, 6).map((decision) => (
                      <article key={decision.id} className="decision-item">
                        <span className={`pill ${actionTone[decision.action] ?? "neutral"}`}>{decision.action}</span>
                        <div>
                          <strong>{Math.round(decision.confidence * 100)}%</strong>
                          <p>{decision.reasoning}</p>
                          {decision.counterpoints && <small>{decision.counterpoints}</small>}
                        </div>
                      </article>
                    ))
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-title">
                  <FileText size={18} />
                  <h2>입력 기록</h2>
                </div>
                <div className="note-list">
                  {selected.notes.length === 0 ? (
                    <div className="empty">아직 저장된 메모가 없습니다.</div>
                  ) : (
                    [...selected.notes].reverse().slice(0, 6).map((note) => (
                      <article key={note.id} className="note-item">
                        <div>
                          <strong>{note.title || note.source_type}</strong>
                          <small>{formatDate(note.created_at)}</small>
                          <p>{note.content}</p>
                        </div>
                        {note.url && (
                          <a className="icon-link" href={note.url} target="_blank" rel="noreferrer" title="원문 열기">
                            <ExternalLink size={17} />
                          </a>
                        )}
                      </article>
                    ))
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-title">
                  <Bell size={18} />
                  <h2>새 정보</h2>
                </div>
                <div className="event-list">
                  {selected.events.length === 0 ? (
                    <div className="empty">스캔 후 새 정보가 여기에 쌓입니다.</div>
                  ) : (
                    [...selected.events].reverse().slice(0, 12).map((event) => (
                      <article key={event.id} className="event-item">
                        <div>
                          <strong>{event.title}</strong>
                          <p>{stripHtml(event.summary)}</p>
                          <small>
                            {event.source}
                            {event.published_at ? ` · ${formatDate(event.published_at)}` : ""}
                          </small>
                        </div>
                        <span className="score">{Math.round(event.relevance_score * 100)}%</span>
                        {event.url && (
                          <a className="icon-link" href={event.url} target="_blank" rel="noreferrer" title="원문 열기">
                            <ExternalLink size={17} />
                          </a>
                        )}
                      </article>
                    ))
                  )}
                </div>
              </section>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatCadence(minutes: number) {
  if (minutes < 60) return `${minutes}분마다`;
  if (minutes % 1440 === 0) return `${minutes / 1440}일마다`;
  if (minutes % 60 === 0) return `${minutes / 60}시간마다`;
  return `${minutes}분마다`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function stripHtml(value: string) {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export default App;
