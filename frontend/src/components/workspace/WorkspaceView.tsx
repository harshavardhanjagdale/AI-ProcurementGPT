'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authService } from '@/services/auth.service';
import { workflowService, type WorkflowStep, type WorkflowSessionDetail, type WorkflowSessionSummary, type ConversationMessage } from '@/services/workflow.service';
import { useWorkflowSocket } from '@/hooks/useWorkflowSocket';
import { WorkspaceSidebar } from './WorkspaceSidebar';
import { ChatPanel } from './ChatPanel';
import { WorkflowProgress } from './WorkflowProgress';
import { EventTimeline } from './EventTimeline';
import { LogOut, History, X, Sparkles, Plus, ChevronDown } from 'lucide-react';

const STATUS_PILL: Record<string, string> = {
  active: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300',
  waiting: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
  completed: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
  failed: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300',
  cancelled: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
};

interface WorkspaceViewProps {
  /** When embedded inside the dashboard chrome, hide the redundant user chip / logout. */
  embedded?: boolean;
}

export function WorkspaceView({ embedded = false }: WorkspaceViewProps) {
  const router = useRouter();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<WorkflowSessionDetail | null>(null);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [showTimeline, setShowTimeline] = useState(false);
  const [userName, setUserName] = useState('');
  const [incomingMessage, setIncomingMessage] = useState<ConversationMessage | null>(null);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      router.push('/login');
      return;
    }
    authService.getMe().then((u) => setUserName(u.full_name)).catch(() => {});
  }, [router]);

  const loadSession = useCallback(async (id: string) => {
    try {
      const data = await workflowService.getSession(id);
      setSession(data);
      setSteps(data.steps || []);
    } catch {
      // silent
    }
  }, []);

  // WebSocket real-time updates
  const { connected } = useWorkflowSocket(activeSessionId, {
    onProgress(event) {
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          current_step: event.currentStep ?? prev.current_step,
          current_agent: event.currentAgent ?? prev.current_agent,
          progress_percentage: event.progress ?? prev.progress_percentage,
          status: event.status ?? prev.status,
          title: event.title ?? prev.title,
        };
      });
      if (event.steps) setSteps(event.steps);
      if (event.chatMessage) setIncomingMessage(event.chatMessage);
    },
    onComplete(event) {
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          current_step: event.currentStep ?? prev.current_step,
          status: event.status ?? 'completed',
          progress_percentage: event.progress ?? prev.progress_percentage,
        };
      });
      if (event.steps) setSteps(event.steps);
      if (event.chatMessage) setIncomingMessage(event.chatMessage);
    },
    onError(event) {
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          status: 'failed',
          current_step: event.currentStep ?? prev.current_step,
        };
      });
      if (event.chatMessage) setIncomingMessage(event.chatMessage);
    },
    onStateSync(event) {
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          current_step: event.currentStep ?? prev.current_step,
          current_agent: event.currentAgent ?? prev.current_agent,
          progress_percentage: event.progress ?? prev.progress_percentage,
          status: event.status ?? prev.status,
          title: event.title ?? prev.title,
        };
      });
      if (event.steps) setSteps(event.steps);
    },
  });

  useEffect(() => {
    if (!activeSessionId) {
      setSession(null);
      setSteps([]);
      return;
    }
    loadSession(activeSessionId);
  }, [activeSessionId, loadSession]);

  // Always poll as baseline — fast (3s) when WS is down, slow (10s) when WS is up
  useEffect(() => {
    if (!activeSessionId) return;
    const interval = setInterval(() => loadSession(activeSessionId), connected ? 10000 : 3000);
    return () => clearInterval(interval);
  }, [activeSessionId, connected, loadSession]);

  const handleNewSession = async () => {
    try {
      const newSession = await workflowService.createSession();
      setActiveSessionId(newSession.id);
    } catch {
      // silent
    }
  };

  const handleMessageSent = (result: any) => {
    if (result?.steps) setSteps(result.steps);
    if (result?.session) setSession(result.session);
  };

  const [embeddedSessions, setEmbeddedSessions] = useState<WorkflowSessionSummary[]>([]);
  const [showSessionPicker, setShowSessionPicker] = useState(false);

  useEffect(() => {
    if (!embedded) return;
    workflowService.listSessions({ limit: 20 }).then((d) => setEmbeddedSessions(d.items)).catch(() => {});
    const interval = setInterval(() => {
      workflowService.listSessions({ limit: 20 }).then((d) => setEmbeddedSessions(d.items)).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [embedded]);

  const hasWorkflow = steps.length > 0 && session?.current_step !== 'waiting_input';
  const statusKey = session?.status || 'active';

  return (
    <div className="relative h-full flex overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Left rail — sessions (hidden when embedded in dashboard) */}
      {!embedded && (
        <WorkspaceSidebar
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          onNewSession={handleNewSession}
        />
      )}

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-5 bg-white/80 dark:bg-slate-900/80 backdrop-blur flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {embedded && (
              <div className="relative">
                <button
                  onClick={() => setShowSessionPicker(!showSessionPicker)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors text-sm"
                >
                  <span className="text-slate-700 font-medium truncate max-w-[180px]">
                    {session?.title || 'Select session'}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                </button>
                {showSessionPicker && (
                  <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-50 py-2 max-h-64 overflow-y-auto">
                    <button
                      onClick={() => { handleNewSession(); setShowSessionPicker(false); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-indigo-600 font-medium hover:bg-indigo-50 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      New Procurement
                    </button>
                    <div className="h-px bg-slate-100 my-1" />
                    {embeddedSessions.filter(s => s.status !== 'cancelled').map((s) => (
                      <button
                        key={s.id}
                        onClick={() => { setActiveSessionId(s.id); setShowSessionPicker(false); }}
                        className={`w-full flex items-center justify-between px-4 py-2 text-sm hover:bg-slate-50 transition-colors ${activeSessionId === s.id ? 'bg-indigo-50 text-indigo-700' : 'text-slate-700'}`}
                      >
                        <span className="truncate">{s.title}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_PILL[s.status] || ''}`}>
                          {s.status}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!embedded && (
              session ? (
                <>
                  <h1 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate max-w-[360px]">
                    {session.title}
                  </h1>
                  <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium capitalize ${STATUS_PILL[statusKey] || STATUS_PILL.active}`}>
                    {session.status}
                  </span>
                </>
              ) : (
                <div className="flex items-center gap-2 text-slate-400">
                  <Sparkles className="w-4 h-4" />
                  <span className="text-sm font-medium">ProcureGPT Workspace</span>
                </div>
              )
            )}
          </div>
          <div className="flex items-center gap-2">
            {session && (
              <button
                onClick={() => setShowTimeline(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-xs font-medium"
                title="Activity timeline"
              >
                <History className="w-4 h-4" />
                <span className="hidden sm:inline">Timeline</span>
              </button>
            )}
            {!embedded && (
              <>
                <div className="flex items-center gap-2 pl-3 pr-1 py-1 rounded-full bg-slate-100 dark:bg-slate-800">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-[10px] font-bold text-white">
                    {(userName || 'U').charAt(0).toUpperCase()}
                  </div>
                  <span className="text-xs text-slate-700 dark:text-slate-200 pr-1">{userName || 'User'}</span>
                </div>
                <button
                  onClick={() => authService.logout()}
                  className="p-2 rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/50 transition-colors"
                  title="Log out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </header>

        {/* Progress on top */}
        {hasWorkflow && (
          <div className="flex-shrink-0 border-b border-slate-200 dark:border-slate-800 shadow-sm">
            <WorkflowProgress
              steps={steps}
              currentStep={session?.current_step || null}
              currentAgent={session?.current_agent || null}
              progress={session?.progress_percentage || 0}
              status={session?.status || null}
            />
          </div>
        )}

        {/* Chat below */}
        <ChatPanel
          sessionId={activeSessionId}
          currentStep={session?.current_step}
          sessionStatus={session?.status}
          onMessageSent={handleMessageSent}
          incomingMessage={incomingMessage}
          wsConnected={connected}
        />
      </div>

      {/* Timeline slide-over */}
      {showTimeline && activeSessionId && (
        <div className="absolute inset-0 z-40 flex justify-end">
          <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm" onClick={() => setShowTimeline(false)} />
          <div className="relative w-full max-w-sm h-full bg-white dark:bg-slate-900 shadow-2xl flex flex-col animate-fade-in-up">
            <div className="h-14 flex items-center justify-between px-5 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
              <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
                <History className="w-4 h-4" />
                <span className="text-sm font-semibold">Activity Timeline</span>
              </div>
              <button onClick={() => setShowTimeline(false)} className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-slim">
              <EventTimeline sessionId={activeSessionId} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
