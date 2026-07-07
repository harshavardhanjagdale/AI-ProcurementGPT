'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Search, Trash2, Edit2, Check, X, Sparkles, LayoutDashboard } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  workflowService,
  type WorkflowSessionSummary,
} from '@/services/workflow.service';

interface WorkspaceSidebarProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

const STATUS_META: Record<string, { dot: string; label: string; text?: string }> = {
  active: { dot: 'bg-indigo-400', label: 'Active' },
  waiting: { dot: 'bg-amber-400', label: 'Waiting' },
  completed: { dot: 'bg-emerald-400', label: 'Done', text: 'text-emerald-400' },
  failed: { dot: 'bg-rose-400', label: 'Failed', text: 'text-rose-400' },
  cancelled: { dot: 'bg-slate-500', label: 'Cancelled', text: 'text-slate-500' },
};

export function WorkspaceSidebar({
  activeSessionId,
  onSelectSession,
  onNewSession,
}: WorkspaceSidebarProps) {
  const router = useRouter();
  const [sessions, setSessions] = useState<WorkflowSessionSummary[]>([]);
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(async () => {
    try {
      const data = await workflowService.listSessions({ limit: 50 });
      setSessions(data.items);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 10000);
    return () => clearInterval(interval);
  }, [loadSessions]);

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return;
    await workflowService.renameSession(id, editTitle.trim());
    setEditingId(null);
    loadSessions();
  };

  const handleDelete = async (id: string) => {
    await workflowService.deleteSession(id);
    loadSessions();
  };

  const filtered = sessions.filter(
    (s) => s.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <aside className="w-72 h-full bg-slate-950 text-white flex flex-col border-r border-slate-800/80">
      {/* Brand */}
      <div className="px-4 pt-4 pb-3 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold">ProcureGPT</p>
          <p className="text-[10px] text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Online
          </p>
        </div>
      </div>

      {/* New Procurement */}
      <div className="px-3 pb-2">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 transition-all text-sm font-medium shadow-lg shadow-indigo-900/40"
        >
          <Plus className="w-4 h-4" />
          New Procurement
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:border-indigo-600/70 focus:ring-2 focus:ring-indigo-600/20"
          />
        </div>
      </div>

      {/* Session list */}
      <nav className="flex-1 overflow-y-auto scrollbar-slim px-2 py-1 space-y-1">
        {loading ? (
          <div className="text-center py-8 text-slate-500 text-xs">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-10 px-4 text-slate-500 text-xs leading-relaxed">
            No conversations yet.
            <br />
            Click <span className="text-slate-300 font-medium">New Procurement</span> to start.
          </div>
        ) : (
          filtered.map((session) => {
            const isActive = activeSessionId === session.id;
            const meta = STATUS_META[session.status] || { dot: 'bg-slate-500', label: session.status };
            const pct = Math.round(session.progress_percentage || 0);
            return (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  'group relative rounded-xl cursor-pointer transition-colors px-3 py-2.5',
                  isActive ? 'bg-slate-800/90 ring-1 ring-indigo-500/40' : 'hover:bg-slate-900'
                )}
              >
                {editingId === session.id ? (
                  <div className="flex items-center gap-1">
                    <input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRename(session.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      className="flex-1 px-1.5 py-0.5 bg-slate-700 border border-slate-600 rounded text-xs text-white focus:outline-none"
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                    <button onClick={(e) => { e.stopPropagation(); handleRename(session.id); }} className="p-0.5 text-slate-400 hover:text-emerald-400">
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setEditingId(null); }} className="p-0.5 text-slate-400 hover:text-rose-400">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start justify-between gap-2">
                      <p className={cn(
                        'text-sm font-medium truncate flex-1',
                        session.status === 'cancelled' ? 'text-slate-500 line-through decoration-slate-600' :
                        session.status === 'failed' ? 'text-rose-300/80' :
                        isActive ? 'text-white' : 'text-slate-200'
                      )}>
                        {session.title}
                      </p>
                      <div className="hidden group-hover:flex items-center gap-0.5 -mr-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingId(session.id); setEditTitle(session.title); }}
                          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDelete(session.id); }}
                          className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-rose-400"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="flex items-center gap-1.5">
                        <span className={cn('w-1.5 h-1.5 rounded-full', meta.dot)} />
                        <span className={cn('text-[10px]', meta.text || 'text-slate-400')}>{meta.label}</span>
                      </span>
                      {session.current_agent && session.status !== 'cancelled' && (
                        <span className="text-[10px] text-slate-500 truncate">· {session.current_agent}</span>
                      )}
                    </div>
                    {/* Thin progress line for in-flight sessions */}
                    {!['completed', 'cancelled'].includes(session.status) && pct > 0 && (
                      <div className="mt-1.5 h-0.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div className={cn(
                          'h-full rounded-full transition-all duration-500',
                          session.status === 'failed' ? 'bg-rose-500/70' : 'bg-indigo-500/70'
                        )} style={{ width: `${pct}%` }} />
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </nav>

      {/* Back to Dashboard */}
      <div className="px-3 py-3 border-t border-slate-800/80">
        <button
          onClick={() => router.push('/dashboard')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition-colors text-xs font-medium"
        >
          <LayoutDashboard className="w-4 h-4" />
          Back to Dashboard
        </button>
      </div>
    </aside>
  );
}
