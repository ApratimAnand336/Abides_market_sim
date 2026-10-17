import { useEffect, useMemo, useState } from 'react';
import { Activity, BarChart2, Cpu, Gauge, Newspaper, Play } from 'lucide-react';
import { useHealth, usePayload, usePresets, useRunController, useRunList } from './hooks/useSimulation';
import { useQueryParam, useTab, type TabId } from './lib/urlState';
import { SCHEMA_VERSION, type SimPayload } from './types/payload';
import { MARKET_DEFAULTS, POPULATION_DEFAULTS, Sidebar, type SimForm } from './components/Sidebar';
import { Header, KpiRow } from './components/Header';
import { RunBanner } from './components/RunBanner';
import { GuideModal } from './components/GuideModal';
import { EmptyState, ErrorState, Skeleton, Toast } from './components/ui/feedback';
import { Button } from './components/ui/controls';
import { MarketOverview } from './tabs/MarketOverview';
import { AgentPerformance } from './tabs/AgentPerformance';
import { NewsSentiment } from './tabs/NewsSentiment';
import { MarketHealth } from './tabs/MarketHealth';
import { Realism } from './tabs/Realism';
import { cn } from './lib/cn';

// spec v1.4 §6.1: the default market is P0 (60 informed fundamentalists, no value agents)
const DEFAULT_FORM: SimForm = { seed: 42, end_time: '16:00:00', num_fund: 60, fund_mode: 'informed', num_mom: 12, ...POPULATION_DEFAULTS, ...MARKET_DEFAULTS, news: [] };

const TAB_DEFS: { id: TabId; label: string; icon: typeof BarChart2; iconClass: string }[] = [
  { id: 'overview', label: 'Market Overview', icon: BarChart2, iconClass: 'text-up' },
  { id: 'agents', label: 'Agent Performance', icon: Cpu, iconClass: 'text-mid' },
  { id: 'news', label: 'News & Sentiment', icon: Newspaper, iconClass: 'text-spread' },
  { id: 'health', label: 'Market Health', icon: Activity, iconClass: 'text-warn' },
  { id: 'realism', label: 'Realism', icon: Gauge, iconClass: 'text-accent' },
];

export function App() {
  const health = useHealth();
  const presets = usePresets();
  const runList = useRunList();
  const [urlRun, setUrlRun] = useQueryParam('run', '');
  const [tab, setTab] = useTab();
  const [guideOpen, setGuideOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; tone: 'success' | 'error' } | null>(null);
  const [form, setForm] = useState<SimForm>(DEFAULT_FORM);
  const [formFromRun, setFormFromRun] = useState(false);

  // startup: URL ?run= wins, else the most recent cached run
  const initialRunId = urlRun || runList.data?.[0]?.run_id || null;
  const ctrl = useRunController(initialRunId);
  const payloadQ = usePayload(ctrl.displayedId);
  const loaded: SimPayload | null = payloadQ.data ?? null;
  // runs cached by an older engine lack v1.1 fields: show a notice, not a crash
  const staleSchema = loaded && loaded.schema_version !== SCHEMA_VERSION ? (loaded.schema_version as string) : null;
  const payload: SimPayload | null = staleSchema ? null : loaded;

  useEffect(() => {
    if (ctrl.displayedId && ctrl.displayedId !== urlRun) setUrlRun(ctrl.displayedId);
  }, [ctrl.displayedId, urlRun, setUrlRun]);

  // the sidebar starts from the parameters of the first loaded run
  useEffect(() => {
    if (payload && !formFromRun) {
      const p = payload.meta.params;
      setForm({
        seed: p.seed,
        end_time: p.end_time,
        num_fund: p.num_fund,
        fund_mode: p.fund_mode ?? 'informed',
        num_mom: p.num_mom,
        num_value: p.num_value ?? POPULATION_DEFAULTS.num_value,
        num_noise: p.num_noise ?? POPULATION_DEFAULTS.num_noise,
        num_mm: p.num_mm ?? POPULATION_DEFAULTS.num_mm,
        num_retail: p.num_retail ?? POPULATION_DEFAULTS.num_retail,
        mm_kind: p.mm_kind ?? POPULATION_DEFAULTS.mm_kind,
        day_type: p.day_type ?? MARKET_DEFAULTS.day_type,
        auto_news: p.auto_news ?? MARKET_DEFAULTS.auto_news,
        news: p.news,
      });
      setFormFromRun(true);
    }
  }, [payload, formFromRun]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const running = !!ctrl.progress && (ctrl.progress.status === 'queued' || ctrl.progress.status === 'running');

  const onRun = async () => {
    setDrawerOpen(false);
    try {
      const r = await ctrl.start(form);
      if (r.cached) setToast({ msg: `Loaded cached run ${r.runId} (same parameters and engine).`, tone: 'success' });
    } catch (e) {
      setToast({ msg: (e as Error).message, tone: 'error' });
    }
  };

  // toast when a background run finishes and is swapped in
  const [lastShown, setLastShown] = useState<string | null>(null);
  useEffect(() => {
    if (payload && lastShown && payload.meta.run_id !== lastShown && !running) {
      setToast({
        msg: `Simulation ${payload.meta.run_id} ready: ${payload.market.totals.trades.toLocaleString('en-US')} trades, ${payload.agents.fundamental.length} fundamental and ${payload.agents.momentum.length} momentum agents.`,
        tone: 'success',
      });
    }
    if (payload) setLastShown(payload.meta.run_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload?.meta.run_id]);

  const sidebar = (
    <Sidebar
      form={form}
      setForm={setForm}
      presets={presets.data ?? []}
      finbertAvailable={!!health.data?.finbert_available}
      runs={runList.data ?? []}
      progress={ctrl.progress}
      displayedRunId={ctrl.displayedId}
      onRun={onRun}
      onCancel={ctrl.cancel}
      onLoadRun={(id) => {
        ctrl.load(id);
        setDrawerOpen(false);
      }}
      onOpenGuide={() => setGuideOpen(true)}
    />
  );

  const content = useMemo(() => {
    if (!payload) return null;
    switch (tab) {
      case 'overview':
        return <MarketOverview payload={payload} />;
      case 'agents':
        return <AgentPerformance payload={payload} />;
      case 'news':
        return <NewsSentiment payload={payload} finbertAvailable={!!health.data?.finbert_available} />;
      case 'health':
        return <MarketHealth payload={payload} />;
      case 'realism':
        return <Realism payload={payload} />;
    }
  }, [payload, tab, health.data?.finbert_available]);

  return (
    <div className="flex min-h-screen bg-bg text-text">
      {/* sidebar: fixed on desktop, drawer below 1024 px */}
      <div className="sticky top-0 hidden h-screen shrink-0 lg:block">{sidebar}</div>
      {drawerOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="h-full">
            <Sidebar {...sidebar.props} onClose={() => setDrawerOpen(false)} />
          </div>
          <div className="flex-1 bg-black/60" onClick={() => setDrawerOpen(false)} aria-hidden />
        </div>
      )}

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1600px] p-4 md:p-8">
          <Header payload={payload} onOpenControls={() => setDrawerOpen(true)} />

          {ctrl.progress && <RunBanner progress={ctrl.progress} onRetry={ctrl.retry} onDismiss={ctrl.dismissError} />}

          {!backendReachable(health) ? (
            <ErrorState
              title="Backend not reachable"
              error={'The dashboard needs the FastAPI backend on port 8000.\nStart it with:  uvicorn api.server:app --port 8000\n(or scripts/dev.sh to start backend and frontend together).'}
              onRetry={() => window.location.reload()}
            />
          ) : runList.isLoading || (ctrl.displayedId && payloadQ.isLoading) ? (
            <LoadingSkeleton />
          ) : staleSchema ? (
            <ErrorState
              title="This run was made by an older engine"
              error={`Run ${ctrl.displayedId} uses payload schema ${staleSchema}; this dashboard shows schema ${SCHEMA_VERSION}.\nRun the simulation again (same parameters) to see it with the current agents.`}
            />
          ) : payloadQ.isError ? (
            <ErrorState title="Could not load the run" error={(payloadQ.error as Error).message} onRetry={() => payloadQ.refetch()} />
          ) : !payload ? (
            running ? null : (
              <EmptyState
                title="Run your first simulation"
                body="No cached runs yet. Choose the parameters in the sidebar (the defaults reproduce the reference run: seed 42, full day, 5 + 5 EKF agents) and start a simulation."
                action={
                  <Button variant="primary" onClick={onRun}>
                    <Play className="h-4 w-4 fill-white" aria-hidden /> Run Simulation
                  </Button>
                }
              />
            )
          ) : (
            <div className={cn('transition-opacity', running && 'pointer-events-none opacity-60')} aria-busy={running}>
              <KpiRow payload={payload} />
              <nav role="tablist" aria-label="Dashboard sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
                {TAB_DEFS.map(({ id, label, icon: Icon, iconClass }) => (
                  <button
                    key={id}
                    role="tab"
                    type="button"
                    aria-selected={tab === id}
                    onClick={() => setTab(id)}
                    className={cn(
                      '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-[13px] font-semibold transition-colors',
                      tab === id ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text',
                    )}
                  >
                    <Icon className={cn('h-4 w-4', iconClass)} aria-hidden />
                    {label}
                  </button>
                ))}
              </nav>
              <div role="tabpanel">{content}</div>
              <footer className="mt-10 flex flex-wrap justify-between gap-2 border-t border-border pt-4 font-mono text-[11px] text-dim">
                <span>
                  run {payload.meta.run_id} · created {new Date(payload.meta.created_at).toLocaleString('en-US')} · simulated in{' '}
                  {payload.meta.wall_time_s.toFixed(1)} s
                </span>
                <span>FinVerse · ABIDES market simulation</span>
              </footer>
            </div>
          )}
        </div>
      </main>

      <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} payload={payload} />
      {toast && <Toast message={toast.msg} tone={toast.tone} onClose={() => setToast(null)} />}
    </div>
  );
}

function backendReachable(h: ReturnType<typeof useHealth>): boolean {
  return !h.isError;
}

function LoadingSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading run">
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[106px]" />
        ))}
      </div>
      <Skeleton className="mb-6 h-10" />
      <Skeleton className="h-[460px]" />
    </div>
  );
}
