'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authService } from '@/services/auth.service';
import { workflowService, type WorkflowStep, type WorkflowSessionDetail } from '@/services/workflow.service';
import { WorkspaceSidebar } from '@/components/workspace/WorkspaceSidebar';
import { ChatPanel } from '@/components/workspace/ChatPanel';
import { WorkflowGraph } from '@/components/workspace/WorkflowGraph';
import { EventTimeline } from '@/components/workspace/EventTimeline';
import { LogOut, PanelRightClose, PanelRightOpen, User } from 'lucide-react';

export default function WorkspacePage() {
  const router = useRouter();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<WorkflowSessionDetail | null>(null);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [showPanel, setShowPanel] = useState(true);
  const [userName, setUserName] = useState('');

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

  useEffect(() => {
    if (!activeSessionId) {
      setSession(null);
      setSteps([]);
      return;
    }
    loadSession(activeSessionId);
  }, [activeSessionId, loadSession]);

  // Poll session updates when active
  useEffect(() => {
    if (!activeSessionId) return;
    const interval = setInterval(() => loadSession(activeSessionId), 3000);
    return () => clearInterval(interval);
  }, [activeSessionId, loadSession]);

  const handleNewSession = async () => {
    try {
      const newSession = await workflowService.createSession();
      setActiveSessionId(newSession.id);
    } catch {
      // silent
    }
  };

  const handleMessageSent = (result: any) => {
    if (result.steps) setSteps(result.steps);
    if (result.session) setSession(result.session);
  };

  return (
    <div className="h-screen flex overflow-hidden bg-white">
      {/* Left Sidebar - ChatGPT style */}
      <WorkspaceSidebar
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewSession={handleNewSession}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-12 border-b border-gray-200 flex items-center justify-between px-4 bg-white flex-shrink-0">
          <div className="flex items-center gap-3">
            {session && (
              <>
                <h1 className="text-sm font-semibold text-gray-900 truncate max-w-[300px]">
                  {session.title}
                </h1>
                <span className="text-[10px] px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                  {session.status}
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowPanel(!showPanel)}
              className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
              title={showPanel ? 'Hide workflow panel' : 'Show workflow panel'}
            >
              {showPanel ? (
                <PanelRightClose className="w-4 h-4" />
              ) : (
                <PanelRightOpen className="w-4 h-4" />
              )}
            </button>
            <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-100">
              <User className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-xs text-gray-700">{userName}</span>
            </div>
            <button
              onClick={() => authService.logout()}
              className="p-2 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Split Content */}
        <div className="flex-1 flex min-h-0">
          {/* Chat Panel */}
          <ChatPanel
            sessionId={activeSessionId}
            currentStep={session?.current_step}
            sessionStatus={session?.status}
            onMessageSent={handleMessageSent}
          />

          {/* Right Panel - Workflow Visualization */}
          {showPanel && (
            <div className="w-[380px] border-l border-gray-200 flex flex-col bg-white flex-shrink-0">
              <div className="flex-1 min-h-0">
                <WorkflowGraph
                  steps={steps}
                  currentStep={session?.current_step || null}
                  currentAgent={session?.current_agent || null}
                  progress={session?.progress_percentage || 0}
                />
              </div>
              <EventTimeline sessionId={activeSessionId} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
