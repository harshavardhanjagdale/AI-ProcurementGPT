'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Send, Loader2, Bot, User, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import api from '@/services/api';
import {
  workflowService,
  type ConversationMessage,
} from '@/services/workflow.service';
import { QuotationComparison } from './QuotationComparison';

interface ChatPanelProps {
  sessionId: string | null;
  currentStep?: string | null;
  sessionStatus?: string | null;
  onMessageSent?: (result: any) => void;
}

const DECISION_STEPS = new Set(['present_recommendation', 'user_decision_gate']);
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

export function ChatPanel({ sessionId, currentStep, sessionStatus, onMessageSent }: ChatPanelProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [decidingOn, setDecidingOn] = useState<string | null>(null);
  const [decisionSubmitted, setDecisionSubmitted] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasLoadedRef = useRef(false);

  const loadMessages = useCallback(async () => {
    if (!sessionId) return;
    // Only show the full-panel spinner on the first load for this session -
    // background polling/refreshes should update silently, not flicker.
    const silent = hasLoadedRef.current;
    if (!silent) setLoading(true);
    try {
      const data = await workflowService.getChat(sessionId);
      setMessages(data.messages);
      hasLoadedRef.current = true;
    } catch {
      // silent
    } finally {
      if (!silent) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    hasLoadedRef.current = false;
    if (!sessionId) {
      setMessages([]);
      return;
    }
    loadMessages();
  }, [sessionId, loadMessages]);

  // Poll for new messages so auto-resumed workflow steps (e.g. a supplier
  // reply arriving and OCR/analysis completing) show up without user action.
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(loadMessages, 3000);
    return () => clearInterval(interval);
  }, [sessionId, loadMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // The backend now processes a submitted decision (PDF gen + real email send,
  // for "approve") in the background rather than within the request, so the
  // POST response comes back almost instantly - well before current_step has
  // actually moved on. Keep the buttons hidden until polling observes the step
  // actually change, so a slow background run can't be double-submitted.
  useEffect(() => {
    setDecisionSubmitted(false);
  }, [currentStep]);

  const showDecisionActions =
    !!sessionId &&
    !decidingOn &&
    !decisionSubmitted &&
    !!currentStep &&
    DECISION_STEPS.has(currentStep) &&
    !(sessionStatus && TERMINAL_STATUSES.has(sessionStatus));

  const handleDecision = async (decision: 'approve' | 'negotiate' | 'cancel') => {
    if (!sessionId || decidingOn) return;
    setDecidingOn(decision);
    try {
      const result = await workflowService.submitDecision(sessionId, decision);
      setDecisionSubmitted(true);
      await loadMessages();
      onMessageSent?.(result);
    } catch (err: any) {
      const errorMsg: ConversationMessage = {
        id: `err-${Date.now()}`,
        role: 'system',
        content: `Error: ${err?.response?.data?.detail || err.message || 'Something went wrong'}`,
        message_type: 'text',
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setDecidingOn(null);
    }
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  const handleCheckEmails = async () => {
    if (!sessionId || checkingEmail) return;
    setCheckingEmail(true);
    try {
      const { data } = await api.post(`/workflow/${sessionId}/check-emails`);
      if (data.emails_found > 0) {
        // Reload messages to show the new system message
        await loadMessages();
        onMessageSent?.(data);
      } else {
        const noMailMsg: ConversationMessage = {
          id: `sys-${Date.now()}`,
          role: 'system',
          content: 'No new supplier replies found yet. Will keep checking automatically.',
          message_type: 'event',
          metadata: null,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, noMailMsg]);
      }
    } catch {
      // silent
    } finally {
      setCheckingEmail(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !sessionId || sending) return;

    const userMessage = input.trim();
    setInput('');
    setSending(true);

    // Optimistically add user message
    const tempUserMsg: ConversationMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      message_type: 'text',
      metadata: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const result = await workflowService.continueSession(sessionId, userMessage);

      // Reload from the server (rather than appending a synthetic message)
      // so this doesn't create duplicates once background polling picks up
      // the same messages the backend already persisted.
      await loadMessages();

      onMessageSent?.(result);
    } catch (err: any) {
      const errorMsg: ConversationMessage = {
        id: `err-${Date.now()}`,
        role: 'system',
        content: `Error: ${err?.response?.data?.detail || err.message || 'Something went wrong'}`,
        message_type: 'text',
        metadata: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Bot className="w-8 h-8 text-blue-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            ProcureGPT Workspace
          </h2>
          <p className="text-gray-500 text-sm">
            Select a conversation from the sidebar or start a new procurement
            to begin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-white min-h-0 min-w-0">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-6 space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {sending && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Extracted quotation comparison - shown once quotations have been analyzed */}
      <QuotationComparison sessionId={sessionId} currentStep={currentStep} />

      {/* Decision actions - shown once the AI recommendation is ready */}
      {showDecisionActions && (
        <div className="border-t border-gray-200 px-4 py-3 bg-blue-50/50">
          <div className="flex items-center justify-center gap-2 max-w-4xl mx-auto">
            <button
              onClick={() => handleDecision('approve')}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {decidingOn === 'approve' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Approve &amp; Create PO
            </button>
            <button
              onClick={() => handleDecision('negotiate')}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {decidingOn === 'negotiate' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Negotiate
            </button>
            <button
              onClick={() => handleDecision('cancel')}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl border border-gray-300 text-gray-600 text-sm font-medium hover:bg-gray-100 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {decidingOn === 'cancel' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Cancel RFQ
            </button>
          </div>
        </div>
      )}

      {/* Decision processing - shown right after submitting, until polling confirms the step moved on */}
      {decisionSubmitted && !!currentStep && DECISION_STEPS.has(currentStep) && (
        <div className="border-t border-gray-200 px-4 py-3 bg-blue-50/50">
          <div className="flex items-center justify-center gap-2 max-w-4xl mx-auto text-sm text-blue-700">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Processing your decision — generating documents and notifying the supplier...
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <div className="flex items-end gap-2 max-w-4xl mx-auto">
          <button
            onClick={handleCheckEmails}
            disabled={checkingEmail}
            className="p-3 rounded-xl border border-gray-300 hover:bg-blue-50 hover:border-blue-300 text-gray-500 hover:text-blue-600 transition-colors flex-shrink-0"
            title="Check for supplier emails"
          >
            {checkingEmail ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Mail className="w-4 h-4" />
            )}
          </button>
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Describe what you need to procure..."
              rows={1}
              className="w-full resize-none px-4 py-3 pr-12 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className={cn(
                'absolute right-2 bottom-2 p-2 rounded-lg transition-colors',
                input.trim() && !sending
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              )}
            >
              {sending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
        <p className="text-center text-[11px] text-gray-400 mt-2">
          ProcureGPT can make mistakes. Verify important procurement decisions.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isEvent = message.message_type === 'event';

  if (isEvent || isSystem) {
    return (
      <div className="flex justify-center">
        <div className={cn(
          'px-3 py-1.5 rounded-full text-xs',
          isSystem ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
        )}>
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser ? 'bg-gray-800' : 'bg-blue-600'
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-blue-600 text-white rounded-tr-sm'
            : 'bg-gray-100 text-gray-900 rounded-tl-sm'
        )}
      >
        <div className="whitespace-pre-wrap break-words">
          {message.content.split('**').map((part, i) =>
            i % 2 === 1 ? (
              <strong key={i}>{part}</strong>
            ) : (
              <span key={i}>{part}</span>
            )
          )}
        </div>
      </div>
    </div>
  );
}
