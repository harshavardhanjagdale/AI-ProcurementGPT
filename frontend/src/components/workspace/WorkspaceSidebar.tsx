'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Plus, Search, Trash2, Edit2, Check, X } from 'lucide-react';
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

export function WorkspaceSidebar({
  activeSessionId,
  onSelectSession,
  onNewSession,
}: WorkspaceSidebarProps) {
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
    (s) =>
      s.status !== 'cancelled' &&
      s.title.toLowerCase().includes(search.toLowerCase())
  );

  const getStatusBadge = (s: WorkflowSessionSummary) => {
    const map: Record<string, { color: string; label: string }> = {
      active: { color: 'bg-blue-500', label: 'Active' },
      waiting: { color: 'bg-yellow-500', label: 'Waiting' },
      completed: { color: 'bg-green-500', label: 'Done' },
      failed: { color: 'bg-red-500', label: 'Failed' },
    };
    const info = map[s.status] || { color: 'bg-gray-400', label: s.status };
    return (
      <span className="flex items-center gap-1.5">
        <span className={cn('w-2 h-2 rounded-full', info.color)} />
        <span className="text-[11px] text-gray-500">{info.label}</span>
      </span>
    );
  };

  return (
    <aside className="w-72 h-full bg-gray-950 text-white flex flex-col border-r border-gray-800">
      {/* New Procurement Button */}
      <div className="p-3">
        <button
          onClick={onNewSession}
          className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-700 hover:bg-gray-800 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          New Procurement
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-9 pr-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-300 placeholder:text-gray-600 focus:outline-none focus:border-gray-600"
          />
        </div>
      </div>

      {/* Session List */}
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {loading ? (
          <div className="text-center py-8 text-gray-500 text-xs">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-xs">
            No conversations yet.
            <br />
            Click "New Procurement" to start.
          </div>
        ) : (
          filtered.map((session) => (
            <div
              key={session.id}
              className={cn(
                'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
                activeSessionId === session.id
                  ? 'bg-gray-800'
                  : 'hover:bg-gray-900'
              )}
              onClick={() => onSelectSession(session.id)}
            >
              <div className="flex-1 min-w-0">
                {editingId === session.id ? (
                  <div className="flex items-center gap-1">
                    <input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRename(session.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      className="flex-1 px-1 py-0.5 bg-gray-700 border border-gray-600 rounded text-xs text-white"
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRename(session.id);
                      }}
                      className="p-0.5 hover:text-green-400"
                    >
                      <Check className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingId(null);
                      }}
                      className="p-0.5 hover:text-red-400"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ) : (
                  <>
                    <p className="text-sm font-medium text-gray-200 truncate">
                      {session.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {getStatusBadge(session)}
                      {session.current_agent && (
                        <span className="text-[10px] text-gray-500 truncate">
                          {session.current_agent}
                        </span>
                      )}
                    </div>
                  </>
                )}
              </div>

              {/* Actions (only visible on hover) */}
              {editingId !== session.id && (
                <div className="hidden group-hover:flex items-center gap-0.5">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingId(session.id);
                      setEditTitle(session.title);
                    }}
                    className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(session.id);
                    }}
                    className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-red-400"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800">
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center">
            <span className="text-[10px] font-bold">AI</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-300">ProcureGPT</p>
            <p className="text-[10px] text-green-500">● Online</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
