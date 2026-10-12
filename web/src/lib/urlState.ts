// View state in the URL so a view can be shared and reloaded (spec 7.1).
// The tab lives in the hash (#agents); everything else in the query string.

import { useCallback, useEffect, useState } from 'react';

export type TabId = 'overview' | 'agents' | 'news' | 'health' | 'realism';
const TABS: TabId[] = ['overview', 'agents', 'news', 'health', 'realism'];

function readTab(): TabId {
  const h = window.location.hash.replace('#', '') as TabId;
  return TABS.includes(h) ? h : 'overview';
}

export function useTab(): [TabId, (t: TabId) => void] {
  const [tab, setTab] = useState<TabId>(readTab);
  useEffect(() => {
    const on = () => setTab(readTab());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const set = useCallback((t: TabId) => {
    const url = new URL(window.location.href);
    url.hash = t;
    window.history.replaceState(null, '', url);
    setTab(t);
  }, []);
  return [tab, set];
}

/** A string-valued query parameter with a default, kept in sync with the URL. */
export function useQueryParam(key: string, fallback: string): [string, (v: string) => void] {
  const read = () => new URL(window.location.href).searchParams.get(key) ?? fallback;
  const [value, setValue] = useState<string>(read);
  const set = useCallback(
    (v: string) => {
      const url = new URL(window.location.href);
      if (v === fallback) url.searchParams.delete(key);
      else url.searchParams.set(key, v);
      window.history.replaceState(null, '', url);
      setValue(v);
    },
    [key, fallback],
  );
  return [value, set];
}

/** Boolean query flag ("1"/"0"). */
export function useQueryFlag(key: string, fallback: boolean): [boolean, (v: boolean) => void] {
  const [raw, setRaw] = useQueryParam(key, fallback ? '1' : '0');
  return [raw === '1', (v: boolean) => setRaw(v ? '1' : '0')];
}
