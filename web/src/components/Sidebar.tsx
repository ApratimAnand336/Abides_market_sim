import { useMemo, useState } from 'react';
import { BookOpen, Dices, Loader2, Newspaper, Play, Plus, Sliders, Sparkles, Trash2, X } from 'lucide-react';
import { api } from '../lib/api';
import { clockHM, fmtElapsed, parseHMS, sessionSeconds } from '../lib/format';
import type { EndTime, NewsInput, RunListItem } from '../types/payload';
import type { RunProgress } from '../hooks/useSimulation';
import { SentimentChip } from './ui/Badge';
import { Button, NumberInput, SegmentedControl, Select, Slider, TextInput } from './ui/controls';
import { cn } from '../lib/cn';

export interface SimForm {
  seed: number;
  end_time: EndTime;
  num_fund: number;
  num_mom: number;
  news: NewsInput[];
}

const END_TIMES: { value: EndTime; label: string }[] = [
  { value: '10:00:00', label: '10:00:00 (30 min)' },
  { value: '11:00:00', label: '11:00:00 (1.5 h)' },
  { value: '12:00:00', label: '12:00:00 (2.5 h)' },
  { value: '14:00:00', label: '14:00:00 (4.5 h)' },
  { value: '16:00:00', label: '16:00:00 (Full day 6.5 h)' },
];

function SidebarLabel({ icon: Icon, children }: { icon: typeof Sliders; children: string }) {
  return (
    <div className="micro mb-3 flex items-center gap-2 text-text">
      <Icon className="h-4 w-4 text-accent" aria-hidden />
      <span>{children}</span>
    </div>
  );
}

export function Sidebar({
  form,
  setForm,
  presets,
  finbertAvailable,
  runs,
  progress,
  displayedRunId,
  onRun,
  onCancel,
  onLoadRun,
  onOpenGuide,
  onClose,
}: {
  form: SimForm;
  setForm: (f: SimForm) => void;
  presets: { headline: string; sentiment: number }[];
  finbertAvailable: boolean;
  runs: RunListItem[];
  progress: RunProgress | null;
  displayedRunId: string | null;
  onRun: () => void;
  onCancel: () => void;
  onLoadRun: (runId: string) => void;
  onOpenGuide: () => void;
  onClose?: () => void;
}) {
  const [offset, setOffset] = useState('00:05:00');
  const [mode, setMode] = useState<'predefined' | 'custom'>('predefined');
  const [presetIdx, setPresetIdx] = useState(0);
  const [headline, setHeadline] = useState('');
  const [manual, setManual] = useState(0);
  const [scoring, setScoring] = useState(false);
  const [scoreNote, setScoreNote] = useState<string | null>(null);

  const running = !!progress && (progress.status === 'queued' || progress.status === 'running');
  const sessionS = sessionSeconds(form.end_time);

  const offsetError = useMemo(() => {
    const s = parseHMS(offset);
    if (Number.isNaN(s)) return 'Use HH:MM:SS';
    if (s <= 0 || s >= sessionS) return `Must be strictly between 00:00:00 and ${fmtOffset(sessionS)} (session ends ${clockHM(sessionS)})`;
    return null;
  }, [offset, sessionS]);

  // queued news that fall outside a shortened session
  const invalidNews = form.news.filter((n) => {
    const s = parseHMS(n.offset);
    return !(s > 0 && s < sessionS);
  });

  const preset = presets[presetIdx];
  const canAdd = !offsetError && (mode === 'predefined' ? !!preset : headline.trim().length > 0 && headline.length <= 200);

  const addNews = () => {
    if (!canAdd) return;
    const item: NewsInput =
      mode === 'predefined'
        ? { offset, headline: preset.headline, sentiment: preset.sentiment }
        : { offset, headline: headline.trim(), sentiment: Math.round(manual * 100) / 100 };
    setForm({ ...form, news: [...form.news, item].sort((a, b) => a.offset.localeCompare(b.offset)) });
  };

  const scoreFinbert = async () => {
    if (!headline.trim()) return;
    setScoring(true);
    setScoreNote(null);
    try {
      const r = await api.sentiment(headline.trim());
      setManual(Math.max(-1, Math.min(1, r.compound)));
      setScoreNote(`FinBERT: +${(r.positive * 100).toFixed(0)}% / −${(r.negative * 100).toFixed(0)}% / ${(r.neutral * 100).toFixed(0)}% neutral`);
    } catch (e) {
      setScoreNote(`FinBERT unavailable: ${(e as Error).message}`);
    } finally {
      setScoring(false);
    }
  };

  const seedValid = Number.isInteger(form.seed) && form.seed >= 0 && form.seed <= 2 ** 31 - 1;

  return (
    <aside className="flex h-full w-[360px] max-w-full flex-col border-r border-border bg-sidebar">
      <div className="flex-1 overflow-y-auto px-5 pt-5 pb-4">
        {/* Brand */}
        <div className="mb-5">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-accent-strong font-bold text-white shadow-lg shadow-accent/20">FV</div>
              <div>
                <h2 className="text-[15px] font-bold leading-tight text-text">FinVerse</h2>
                <span className="font-mono text-[11px] text-muted">Market Simulation</span>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="secondary" onClick={onOpenGuide} className="px-2.5 py-1.5 text-[12px] text-indigo-200">
                <BookOpen className="h-3.5 w-3.5" aria-hidden /> Guide
              </Button>
              {onClose && (
                <Button variant="ghost" onClick={onClose} aria-label="Close controls">
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
          <p className="text-[12px] leading-relaxed text-muted">
            Discrete-event limit order book simulation (ABIDES) with Kalman-filter fundamental and momentum investors. Every number shown comes from a real
            simulation run.
          </p>
        </div>

        {/* Simulation controls */}
        <div className="border-t border-border pt-5">
          <SidebarLabel icon={Sliders}>Simulation Controls</SidebarLabel>
          <div className="flex flex-col gap-4">
            <NumberInput
              label="Random Seed"
              value={form.seed}
              min={0}
              max={2 ** 31 - 1}
              onChange={(v) => setForm({ ...form, seed: v })}
              right={
                <Button
                  variant="secondary"
                  aria-label="Randomise seed"
                  title="Randomise seed"
                  // a new seed for the next run; not market data
                  onClick={() => setForm({ ...form, seed: crypto.getRandomValues(new Uint32Array(1))[0] % 2 ** 31 })}
                >
                  <Dices className="h-4 w-4" />
                </Button>
              }
            />
            {!seedValid && <p className="-mt-2 text-[11px] text-rose-300">Seed must be an integer 0 – 2,147,483,647</p>}
            <Select label="Market Close Time" value={form.end_time} options={END_TIMES} onChange={(v) => setForm({ ...form, end_time: v })} />
            <Slider label="Fundamental EKF" value={form.num_fund} min={0} max={20} onChange={(v) => setForm({ ...form, num_fund: v })} />
            <Slider
              label="Momentum EKF"
              value={form.num_mom}
              min={0}
              max={12}
              onChange={(v) => setForm({ ...form, num_mom: v })}
              help="Replaces stock momentum agents (max 12)"
            />
          </div>
        </div>

        {/* News */}
        <div className="mt-5 border-t border-border pt-5">
          <SidebarLabel icon={Newspaper}>News Events Injection</SidebarLabel>
          <div className="flex flex-col gap-3.5">
            <TextInput label="Time offset (after 09:30 open)" value={offset} onChange={setOffset} placeholder="00:05:00" error={offsetError} mono />
            <SegmentedControl
              label="Headline source"
              value={mode}
              onChange={setMode}
              options={[
                { value: 'predefined', label: 'Predefined' },
                { value: 'custom', label: 'Custom' },
              ]}
            />
            {mode === 'predefined' ? (
              presets.length ? (
                <>
                  <Select
                    label="Headline"
                    value={presetIdx}
                    options={presets.map((p, i) => ({ value: i, label: p.headline }))}
                    onChange={setPresetIdx}
                  />
                  <div className="flex items-center justify-between rounded-[10px] border border-border bg-bg/60 px-3 py-2 text-[12px]">
                    <span className="text-muted">Sentiment impact</span>
                    <SentimentChip value={preset.sentiment} />
                  </div>
                </>
              ) : (
                <p className="text-[12px] text-dim">Presets unavailable (backend offline).</p>
              )
            ) : (
              <>
                <div>
                  <label htmlFor="custom-headline" className="mb-1.5 block text-[12px] font-medium text-muted">
                    Headline
                  </label>
                  <textarea
                    id="custom-headline"
                    value={headline}
                    maxLength={200}
                    onChange={(e) => setHeadline(e.target.value)}
                    rows={2}
                    placeholder="Enter a financial headline…"
                    className="w-full resize-none rounded-[10px] border border-border bg-card p-2.5 text-[13px] text-text focus:border-border-strong focus:outline-none"
                  />
                </div>
                {finbertAvailable ? (
                  <Button variant="secondary" onClick={scoreFinbert} disabled={!headline.trim() || scoring}>
                    {scoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Sparkles className="h-3.5 w-3.5 text-warn" aria-hidden />}
                    {scoring ? 'Scoring (first call loads the model)…' : 'Score with FinBERT'}
                  </Button>
                ) : (
                  <p className="text-[11px] text-dim">FinBERT is not installed on the server; set the sentiment manually.</p>
                )}
                {scoreNote && <p className="font-mono text-[11px] text-indigo-200">{scoreNote}</p>}
                <Slider
                  label="Sentiment"
                  value={manual}
                  min={-1}
                  max={1}
                  step={0.05}
                  onChange={setManual}
                  format={(v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2))}
                />
              </>
            )}
            <Button variant="secondary" onClick={addNews} disabled={!canAdd}>
              <Plus className="h-3.5 w-3.5 text-up" aria-hidden /> Add News Event
            </Button>

            {form.news.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[12px] font-semibold text-text">Queued events ({form.news.length})</span>
                  <Button variant="ghost" onClick={() => setForm({ ...form, news: [] })} className="text-[11px] text-rose-300">
                    <Trash2 className="h-3 w-3" aria-hidden /> Clear all
                  </Button>
                </div>
                <ul className="flex flex-col gap-2">
                  {form.news.map((n, i) => {
                    const bad = invalidNews.includes(n);
                    return (
                      <li
                        key={`${n.offset}-${i}`}
                        className={cn('flex items-start justify-between gap-2 rounded-[10px] border bg-card px-3 py-2', bad ? 'border-down/60' : 'border-border')}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 font-mono text-[11px] text-text">
                            <span>{n.offset}</span>
                            <SentimentChip value={n.sentiment} />
                          </div>
                          <p className="mt-1 truncate text-[12px] text-muted" title={n.headline}>
                            {n.headline}
                          </p>
                          {bad && <p className="text-[11px] text-rose-300">Outside the selected session</p>}
                        </div>
                        <button
                          type="button"
                          aria-label={`Remove news at ${n.offset}`}
                          onClick={() => setForm({ ...form, news: form.news.filter((_, j) => j !== i) })}
                          className="rounded p-0.5 text-dim hover:text-rose-300"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Run block (sticky) */}
      <div className="border-t border-border bg-sidebar px-5 py-4">
        {running ? (
          <div className="flex flex-col gap-2">
            <Button variant="primary" disabled className="w-full">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {progress!.status === 'queued' ? 'Queued…' : `Running · ${fmtElapsed(progress!.elapsed)}`}
            </Button>
            <button type="button" onClick={onCancel} className="text-center text-[12px] text-muted underline-offset-2 hover:text-text hover:underline">
              Cancel
            </button>
          </div>
        ) : (
          <Button variant="primary" className="w-full" onClick={onRun} disabled={!seedValid || invalidNews.length > 0}>
            <Play className="h-4 w-4 fill-white" aria-hidden /> Run Simulation
          </Button>
        )}
        <div className="mt-3">
          <Select
            label="Load saved run"
            value={displayedRunId ?? ''}
            options={[
              ...(displayedRunId && !runs.some((r) => r.run_id === displayedRunId) ? [{ value: displayedRunId, label: displayedRunId }] : []),
              ...(runs.length === 0 ? [{ value: '', label: 'No saved runs yet' }] : []),
              ...runs.map((r) => ({
                value: r.run_id,
                label: `seed ${r.params.seed} · ${r.params.end_time.slice(0, 5)} · ${r.params.news.length} news · ${new Date(r.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`,
              })),
            ]}
            onChange={(v) => v && onLoadRun(v)}
          />
        </div>
      </div>
    </aside>
  );
}

function fmtOffset(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
