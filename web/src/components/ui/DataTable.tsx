import { Fragment, useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight, ArrowDown, ArrowUp } from 'lucide-react';
import { cn } from '../../lib/cn';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
  align?: 'left' | 'right';
  className?: string;
}

/** Sortable table with optional row click and expandable rows. */
export function DataTable<T>({
  rows,
  columns,
  rowKey,
  initialSort,
  onRowClick,
  selectedKey,
  expand,
  caption,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  initialSort?: { key: string; dir: 'asc' | 'desc' };
  onRowClick?: (row: T) => void;
  selectedKey?: string | number;
  expand?: (row: T) => ReactNode;
  caption: string;
}) {
  const [sort, setSort] = useState(initialSort);
  const [open, setOpen] = useState<Set<string | number>>(new Set());

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const sv = col.sortValue;
    return [...rows].sort((a, b) => {
      const x = sv(a);
      const y = sv(b);
      const r = x < y ? -1 : x > y ? 1 : 0;
      return sort.dir === 'asc' ? r : -r;
    });
  }, [rows, columns, sort]);

  const toggle = (k: string | number) =>
    setOpen((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border">
            {expand && <th className="w-8" aria-label="Expand" />}
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={cn('px-3 py-2 font-semibold whitespace-nowrap', c.align === 'right' ? 'text-right' : 'text-left')}
                  aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {c.sortValue ? (
                    <button
                      type="button"
                      onClick={() => setSort({ key: c.key, dir: active && sort!.dir === 'desc' ? 'asc' : 'desc' })}
                      className="micro inline-flex items-center gap-1 hover:text-text"
                    >
                      {c.header}
                      {active && (sort!.dir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
                    </button>
                  ) : (
                    <span className="micro">{c.header}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const k = rowKey(row);
            const isOpen = open.has(k);
            return (
              <Fragment key={k}>
                <tr
                  className={cn(
                    'border-b border-border/70 transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-card-hover',
                    selectedKey === k && 'bg-accent/10',
                  )}
                  onClick={() => (onRowClick ? onRowClick(row) : expand && toggle(k))}
                  tabIndex={onRowClick || expand ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onRowClick ? onRowClick(row) : expand && toggle(k);
                    }
                  }}
                >
                  {expand && (
                    <td className="px-2 text-muted">
                      <button
                        type="button"
                        aria-label={isOpen ? 'Collapse row' : 'Expand row'}
                        aria-expanded={isOpen}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggle(k);
                        }}
                        className="rounded p-0.5 hover:text-text"
                      >
                        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                    </td>
                  )}
                  {columns.map((c) => (
                    <td key={c.key} className={cn('px-3 py-2.5', c.align === 'right' ? 'text-right' : 'text-left', c.className)}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
                {expand && isOpen && (
                  <tr className="border-b border-border/70 bg-bg/40">
                    <td colSpan={columns.length + 1} className="px-4 py-3">
                      {expand(row)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
