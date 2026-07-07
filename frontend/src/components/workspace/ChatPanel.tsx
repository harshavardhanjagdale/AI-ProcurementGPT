'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send,
  Loader2,
  Bot,
  User,
  Mail,
  CheckCircle2,
  Handshake,
  XCircle,
  Sparkles,
  ArrowDown,
  ChevronDown,
  ChevronUp,
  Award,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import api from '@/services/api';
import {
  workflowService,
  type ConversationMessage,
  type Quotation,
} from '@/services/workflow.service';

interface ChatPanelProps {
  sessionId: string | null;
  currentStep?: string | null;
  sessionStatus?: string | null;
  onMessageSent?: (result: any) => void;
  incomingMessage?: ConversationMessage | null;
  wsConnected?: boolean;
}

const STEPS_ACCEPTING_CHAT = new Set(['waiting_input', 'parse_request']);
const DECISION_STEPS = new Set(['ocr_extract', 'user_decision_gate']);
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const QUOTATIONS_READY_STEPS = new Set([
  'ocr_extract',
  'user_decision_gate',
  'negotiate_with_suppliers',
  'generate_purchase_order',
  'send_po_email',
]);

const SUGGESTIONS = [
  'Buy 10 Dell Latitude laptops',
  'Purchase 50 office chairs from ErgoSupply',
  'I need 100 USB-C cables, find me the best price',
];

export function ChatPanel({ sessionId, currentStep, sessionStatus, onMessageSent, incomingMessage, wsConnected = false }: ChatPanelProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [decidingOn, setDecidingOn] = useState<string | null>(null);
  const [decisionSubmitted, setDecisionSubmitted] = useState(false);
  const [submittedDecision, setSubmittedDecision] = useState<string | null>(null);
  const [negotiateMode, setNegotiateMode] = useState(false);
  const [negotiateAmount, setNegotiateAmount] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasLoadedRef = useRef(false);
  const isNearBottomRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const userSentRef = useRef(false);

  // Quotation state (inline collapsible)
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [quotationsOpen, setQuotationsOpen] = useState(true);
  const quotationReady = !!sessionId && !!currentStep && QUOTATIONS_READY_STEPS.has(currentStep);

  const loadMessages = useCallback(async () => {
    if (!sessionId) return;
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

  // Always poll messages — fast (3s) when WS is down, slow (10s) when WS is up
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(loadMessages, wsConnected ? 10000 : 3000);
    return () => clearInterval(interval);
  }, [sessionId, wsConnected, loadMessages]);

  // Append live WebSocket messages (dedup by id)
  useEffect(() => {
    if (!incomingMessage) return;
    setMessages((prev) => {
      if (prev.some((m) => m.id === incomingMessage.id)) return prev;
      return [...prev, incomingMessage];
    });
  }, [incomingMessage]);

  useEffect(() => {
    if (isNearBottomRef.current || userSentRef.current) {
      scrollToBottom();
      userSentRef.current = false;
    } else {
      setShowScrollBtn(true);
    }
  }, [messages]);

  // Load quotations when ready
  useEffect(() => {
    if (!quotationReady) {
      setQuotations([]);
      return;
    }
    const loadQuotations = async () => {
      try {
        const data = await workflowService.getQuotations(sessionId!);
        setQuotations(data.quotations);
      } catch { /* silent */ }
    };
    loadQuotations();
    const interval = setInterval(loadQuotations, 5000);
    return () => clearInterval(interval);
  }, [sessionId, quotationReady]);

  useEffect(() => {
    setDecisionSubmitted(false);
    setSubmittedDecision(null);
    setNegotiateMode(false);
    setNegotiateAmount('');
  }, [currentStep]);

  useEffect(() => {
    if (sessionStatus && TERMINAL_STATUSES.has(sessionStatus)) {
      setDecisionSubmitted(false);
      setSubmittedDecision(null);
    }
  }, [sessionStatus]);

  const topQuote = quotations.find((q) => q.is_recommended) || quotations[0];
  // Negotiation is expressed as a per-piece rate. Total quantity across the quote's line
  // items lets us convert the per-piece counter to the order total the backend expects.
  const negoQty = topQuote?.items?.reduce((sum, it) => sum + (it.quantity || 0), 0) || 1;
  const negoCurrentPerPiece = topQuote ? topQuote.total_amount / (negoQty || 1) : 0;

  const showDecisionActions =
    !!sessionId &&
    !decidingOn &&
    !decisionSubmitted &&
    !!currentStep &&
    DECISION_STEPS.has(currentStep) &&
    quotations.length > 0 &&
    !(sessionStatus && TERMINAL_STATUSES.has(sessionStatus));

  const handleDecision = async (decision: 'approve' | 'negotiate' | 'cancel', targetPrice?: number) => {
    if (!sessionId || decidingOn || decisionSubmitted) return;
    // Hide the confirmation UI immediately so it can't be double-clicked / double-submitted;
    // the "processing" indicator takes over until polling shows the step advanced.
    setDecisionSubmitted(true);
    setSubmittedDecision(decision);
    setNegotiateMode(false);
    setDecidingOn(decision);
    try {
      const result = await workflowService.submitDecision(sessionId, decision, targetPrice);
      await loadMessages();
      onMessageSent?.(result);
    } catch (err: any) {
      setDecisionSubmitted(false);
      setSubmittedDecision(null);
      pushSystem(err?.response?.data?.detail || err.message || 'Something went wrong');
    } finally {
      setDecidingOn(null);
    }
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setShowScrollBtn(false);
    }
  };

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    isNearBottomRef.current = distanceFromBottom < 100;
    if (isNearBottomRef.current) setShowScrollBtn(false);
  };

  const pushSystem = (content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        role: 'system',
        content,
        message_type: 'event',
        metadata: null,
        created_at: new Date().toISOString(),
      },
    ]);
  };

  const handleCheckEmails = async () => {
    if (!sessionId || checkingEmail) return;
    setCheckingEmail(true);
    try {
      const { data } = await api.post(`/workflow/${sessionId}/check-emails`);
      if (data.emails_found > 0) {
        await loadMessages();
        onMessageSent?.(data);
      } else {
        pushSystem('No new supplier replies found yet. Will keep checking automatically.');
      }
    } catch {
      // silent
    } finally {
      setCheckingEmail(false);
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || !sessionId || sending) return;
    const userMessage = text.trim();
    setInput('');
    setSending(true);
    userSentRef.current = true;

    setMessages((prev) => [
      ...prev,
      {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: userMessage,
        message_type: 'text',
        metadata: null,
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const result = await workflowService.continueSession(sessionId, userMessage);
      await loadMessages();
      onMessageSent?.(result);
    } catch (err: any) {
      pushSystem(err?.response?.data?.detail || err.message || 'Something went wrong');
    } finally {
      setSending(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-6">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-lg shadow-indigo-500/25">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
            Welcome to ProcureGPT
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed">
            Start a new procurement from the sidebar, or pick up an existing conversation.
            Describe what you need and I&apos;ll handle sourcing, RFQs, quote analysis and purchase orders.
          </p>
        </div>
      </div>
    );
  }

  const showSuggestions = !loading && messages.filter((m) => m.role === 'user').length === 0;

  return (
    <div className="flex-1 flex flex-col bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900 min-h-0 min-w-0">
      {/* Messages area */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto scrollbar-slim px-4 md:px-8 py-6">
        <div className="max-w-2xl mx-auto space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-slate-300" />
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}

          {/* Inline quotation comparison */}
          {quotationReady && quotations.length > 0 && (
            <div className="my-4">
              <InlineQuotationPanel
                quotations={quotations}
                open={quotationsOpen}
                onToggle={() => setQuotationsOpen(!quotationsOpen)}
              />
            </div>
          )}

          {sending && <TypingBubble />}

          {showSuggestions && (
            <div className="pt-4 flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs text-slate-600 dark:text-slate-300 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Scroll to bottom FAB */}
      {showScrollBtn && (
        <div className="relative">
          <button
            onClick={scrollToBottom}
            className="absolute -top-12 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-lg text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-indigo-50 hover:border-indigo-300 dark:hover:bg-indigo-950 transition-all"
          >
            <ArrowDown className="w-3.5 h-3.5" />
            New messages
          </button>
        </div>
      )}

      {/* Decision actions */}
      {showDecisionActions && !negotiateMode && (
        <div className="border-t border-slate-200 dark:border-slate-800 px-4 md:px-6 py-3 bg-gradient-to-r from-indigo-50/60 to-violet-50/60 dark:from-indigo-950/30 dark:to-violet-950/30">
          <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl mx-auto">
            <span className="text-xs text-slate-500 dark:text-slate-400 mr-1 hidden sm:inline">
              Ready to decide:
            </span>
            <button
              onClick={() => handleDecision('approve')}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm shadow-emerald-600/20"
            >
              {decidingOn === 'approve' ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Approve &amp; Create PO
            </button>
            <button
              onClick={() => setNegotiateMode(true)}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm shadow-amber-500/20"
            >
              <Handshake className="w-4 h-4" />
              Negotiate
            </button>
            <button
              onClick={() => handleDecision('cancel')}
              disabled={!!decidingOn}
              className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {decidingOn === 'cancel' ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Negotiate amount entry (colorful, inline) */}
      {showDecisionActions && negotiateMode && (
        <div className="border-t border-amber-200 dark:border-amber-900/50 px-4 md:px-6 py-4 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/40 dark:to-orange-950/30">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-amber-500 flex items-center justify-center flex-shrink-0">
                <Handshake className="w-4 h-4 text-white" />
              </div>
              <div className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                Send a counter-offer{topQuote ? ` to ${topQuote.supplier_name}` : ''}
              </div>
            </div>
            {topQuote && (
              <p className="text-xs text-amber-800/80 dark:text-amber-300/80 mb-3 ml-9">
                They quoted <span className="font-semibold">{topQuote.currency} {negoCurrentPerPiece.toLocaleString(undefined, { maximumFractionDigits: 2 })}/pc</span>
                {' '}for <span className="font-semibold">{negoQty}</span> units.
                Enter your target <span className="font-semibold">rate per piece</span> — I&apos;ll draft &amp; send the counter-offer.
              </p>
            )}
            <div className="flex items-center gap-2 ml-9">
              <div className="relative flex-1 max-w-xs">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-amber-700 dark:text-amber-400 font-medium">
                  {topQuote?.currency || '₹'}
                </span>
                <input
                  type="number"
                  value={negotiateAmount}
                  onChange={(e) => setNegotiateAmount(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && negotiateAmount && !decidingOn) {
                      handleDecision('negotiate', Number(negotiateAmount) * negoQty);
                    }
                  }}
                  placeholder="Rate per piece"
                  autoFocus
                  className="w-full pl-12 pr-14 py-2 rounded-xl border border-amber-300 dark:border-amber-800 bg-white dark:bg-slate-900 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-amber-600/70">/pc</span>
              </div>
              <button
                onClick={() => handleDecision('negotiate', Number(negotiateAmount) * negoQty)}
                disabled={!!decidingOn || !negotiateAmount || Number(negotiateAmount) <= 0}
                className="px-4 py-2 rounded-xl bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm shadow-amber-600/20"
              >
                {decidingOn === 'negotiate' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Send counter-offer
              </button>
              <button
                onClick={() => { setNegotiateMode(false); setNegotiateAmount(''); }}
                disabled={!!decidingOn}
                className="px-3 py-2 rounded-xl border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-sm font-medium hover:bg-amber-100 dark:hover:bg-amber-950/50 disabled:opacity-50 transition-colors"
              >
                Back
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Decision processing indicator */}
      {decisionSubmitted && !!currentStep && DECISION_STEPS.has(currentStep) && (
        <div className={cn(
          'border-t px-4 md:px-6 py-3',
          submittedDecision === 'cancel'
            ? 'border-slate-200 dark:border-slate-700 bg-slate-50/60 dark:bg-slate-900/40'
            : 'border-slate-200 dark:border-slate-800 bg-indigo-50/60 dark:bg-indigo-950/30'
        )}>
          <div className={cn(
            'flex items-center justify-center gap-2 max-w-2xl mx-auto text-sm',
            submittedDecision === 'cancel'
              ? 'text-slate-600 dark:text-slate-400'
              : 'text-indigo-700 dark:text-indigo-300'
          )}>
            <Loader2 className="w-4 h-4 animate-spin" />
            {submittedDecision === 'cancel'
              ? 'Cancelling this RFQ…'
              : submittedDecision === 'negotiate'
                ? 'Sending counter-offer to the supplier…'
                : 'Generating documents and notifying the supplier…'}
          </div>
        </div>
      )}

      {/* Input */}
      <InputBar
        currentStep={currentStep}
        sessionStatus={sessionStatus}
        input={input}
        setInput={setInput}
        sending={sending}
        sendMessage={sendMessage}
        checkingEmail={checkingEmail}
        handleCheckEmails={handleCheckEmails}
      />
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center flex-shrink-0 shadow-sm">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5">
          {[0, 150, 300].map((d) => (
            <span
              key={d}
              className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

type StatusCardStyle = {
  bg: string;
  border: string;
  icon: React.ReactNode;
  iconBg: string;
  text: string;
};

function detectStatusCard(content: string, role: string): StatusCardStyle | null {
  const c = content.toLowerCase();

  if (c.includes('cancelled as requested') || c.includes('rfq has been cancelled')) {
    return {
      bg: 'bg-rose-50 dark:bg-rose-950/30',
      border: 'border-rose-200 dark:border-rose-800/60',
      icon: <XCircle className="w-4 h-4" />,
      iconBg: 'bg-rose-500',
      text: 'text-rose-700 dark:text-rose-300',
    };
  }
  if (role === 'user' && c.startsWith('decision: cancel')) {
    return {
      bg: 'bg-rose-50 dark:bg-rose-950/30',
      border: 'border-rose-200 dark:border-rose-800/60',
      icon: <XCircle className="w-4 h-4" />,
      iconBg: 'bg-rose-500',
      text: 'text-rose-700 dark:text-rose-300',
    };
  }
  if (role === 'user' && c.startsWith('decision: approve')) {
    return {
      bg: 'bg-emerald-50 dark:bg-emerald-950/30',
      border: 'border-emerald-200 dark:border-emerald-800/60',
      icon: <CheckCircle2 className="w-4 h-4" />,
      iconBg: 'bg-emerald-500',
      text: 'text-emerald-700 dark:text-emerald-300',
    };
  }
  if (role === 'user' && c.startsWith('decision: negotiate')) {
    return {
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-200 dark:border-amber-800/60',
      icon: <Handshake className="w-4 h-4" />,
      iconBg: 'bg-amber-500',
      text: 'text-amber-700 dark:text-amber-300',
    };
  }
  if (c.includes('purchase order') && (c.includes('sent') || c.includes('generated'))) {
    return {
      bg: 'bg-emerald-50 dark:bg-emerald-950/30',
      border: 'border-emerald-200 dark:border-emerald-800/60',
      icon: <CheckCircle2 className="w-4 h-4" />,
      iconBg: 'bg-emerald-500',
      text: 'text-emerald-700 dark:text-emerald-300',
    };
  }
  if (c.includes('something went wrong') || c.includes('error')) {
    return {
      bg: 'bg-rose-50 dark:bg-rose-950/30',
      border: 'border-rose-200 dark:border-rose-800/60',
      icon: <XCircle className="w-4 h-4" />,
      iconBg: 'bg-rose-500',
      text: 'text-rose-700 dark:text-rose-300',
    };
  }
  if (c.includes('negotiation email') && c.includes('sent')) {
    return {
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-200 dark:border-amber-800/60',
      icon: <Handshake className="w-4 h-4" />,
      iconBg: 'bg-amber-500',
      text: 'text-amber-700 dark:text-amber-300',
    };
  }
  return null;
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isEvent = message.message_type === 'event';

  if (isEvent || isSystem) {
    return (
      <div className="flex justify-center py-1">
        <div
          className={cn(
            'px-4 py-1.5 rounded-full text-[11px] font-medium max-w-[85%] text-center',
            isSystem
              ? 'bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-100 dark:border-rose-900/50'
              : 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-900/50'
          )}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const time = new Date(message.created_at).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const statusCard = detectStatusCard(message.content, message.role);

  if (statusCard) {
    return (
      <div className="flex justify-center py-1.5">
        <div className={cn(
          'flex items-center gap-3 px-5 py-3 rounded-xl border max-w-[85%] shadow-sm',
          statusCard.bg,
          statusCard.border,
        )}>
          <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-white', statusCard.iconBg)}>
            {statusCard.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className={cn('text-sm font-medium whitespace-pre-wrap break-words', statusCard.text)}>
              {message.content.split('**').map((part, i) =>
                i % 2 === 1 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>
              )}
            </div>
            <span className={cn('text-[10px] mt-0.5 block opacity-60', statusCard.text)}>{time}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex items-end gap-2.5', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm',
          isUser
            ? 'bg-gradient-to-br from-slate-700 to-slate-900'
            : 'bg-gradient-to-br from-indigo-500 to-violet-600'
        )}
      >
        {isUser ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5 text-white" />}
      </div>
      <div className={cn('flex flex-col gap-1', isUser ? 'items-end' : 'items-start', 'max-w-[75%]')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed shadow-sm',
            isUser
              ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-br-md'
              : 'bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-slate-800 dark:text-slate-100 rounded-bl-md'
          )}
        >
          <div className="whitespace-pre-wrap break-words">
            {message.content.split('**').map((part, i) =>
              i % 2 === 1 ? <strong key={i}>{part}</strong> : <span key={i}>{part}</span>
            )}
          </div>
        </div>
        <span className="text-[10px] text-slate-400 px-1">{time}</span>
      </div>
    </div>
  );
}

const STEP_PLACEHOLDERS: Record<string, string> = {
  await_supplier_replies: 'Waiting for supplier responses…',
  ocr_extract: 'Processing quotations…',
  user_decision_gate: 'Use the buttons above to approve, negotiate, or cancel',
  negotiate_with_suppliers: 'Negotiation in progress…',
  generate_purchase_order: 'Generating purchase order…',
  send_po_email: 'Sending purchase order…',
  generate_rfq_emails: 'Drafting RFQ emails…',
  send_rfq_emails: 'Sending RFQ emails…',
  select_vendors: 'Selecting vendors…',
};

function InputBar({
  currentStep,
  sessionStatus,
  input,
  setInput,
  sending,
  sendMessage,
  checkingEmail,
  handleCheckEmails,
}: {
  currentStep?: string | null;
  sessionStatus?: string | null;
  input: string;
  setInput: (v: string) => void;
  sending: boolean;
  sendMessage: (text: string) => void;
  checkingEmail: boolean;
  handleCheckEmails: () => void;
}) {
  const step = currentStep || 'waiting_input';
  const isTerminal = TERMINAL_STATUSES.has(sessionStatus || '');
  const acceptsInput = STEPS_ACCEPTING_CHAT.has(step) && !isTerminal
    || sessionStatus === 'failed';
  const placeholder = isTerminal
    ? sessionStatus === 'failed'
      ? 'This workflow encountered an issue. Start a new message to retry.'
      : sessionStatus === 'cancelled'
        ? 'This procurement was cancelled.'
        : 'This procurement is complete.'
    : acceptsInput
      ? 'Describe what you need to procure…'
      : STEP_PLACEHOLDERS[step] || 'Workflow is processing, please wait…';

  return (
    <div className="border-t border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 md:px-8 py-4">
      <div className="flex items-end gap-2.5 max-w-2xl mx-auto">
        <button
          onClick={handleCheckEmails}
          disabled={checkingEmail || isTerminal}
          className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:border-indigo-300 text-slate-500 hover:text-indigo-600 transition-colors flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          title="Check for supplier emails now"
        >
          {checkingEmail ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
        </button>
        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (acceptsInput) sendMessage(input);
              }
            }}
            placeholder={placeholder}
            disabled={!acceptsInput}
            rows={1}
            className={cn(
              'w-full resize-none px-4 py-3 pr-12 border rounded-xl text-sm transition-all',
              acceptsInput
                ? 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 focus:bg-white dark:focus:bg-slate-900 text-slate-800 dark:text-slate-100 placeholder:text-slate-400'
                : 'border-slate-100 dark:border-slate-800 bg-slate-100 dark:bg-slate-950 text-slate-400 dark:text-slate-500 cursor-not-allowed placeholder:text-slate-400 dark:placeholder:text-slate-600'
            )}
            style={{ maxHeight: '120px' }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || sending || !acceptsInput}
            className={cn(
              'absolute right-2 bottom-2 p-2 rounded-lg transition-all',
              input.trim() && !sending && acceptsInput
                ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-600/20'
                : 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed'
            )}
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {!acceptsInput && !isTerminal && (
        <p className="text-center text-[11px] text-amber-600 dark:text-amber-400 mt-2 font-medium">
          The workflow is in progress. Chat input is disabled until it needs your response.
        </p>
      )}
    </div>
  );
}

function InlineQuotationPanel({
  quotations,
  open,
  onToggle,
}: {
  quotations: Quotation[];
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/50 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-indigo-500" />
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
            Quotation Comparison ({quotations.length} quotes)
          </span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      {open && (
        <div className="border-t border-slate-100 dark:border-slate-700 overflow-x-auto max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 sticky top-0">
                <th className="text-left px-3 py-2 font-medium">Supplier</th>
                <th className="text-left px-3 py-2 font-medium">Items (Qty × Rate/pc)</th>
                <th className="text-right px-3 py-2 font-medium">Order Total</th>
                <th className="text-right px-3 py-2 font-medium">Delivery</th>
                <th className="text-right px-3 py-2 font-medium">Score</th>
                <th className="text-left px-3 py-2 font-medium">Terms</th>
              </tr>
            </thead>
            <tbody>
              {quotations.map((q) => (
                <tr
                  key={q.id}
                  className={cn(
                    'border-t border-slate-100 dark:border-slate-700 align-top',
                    q.is_recommended && 'bg-emerald-50/50 dark:bg-emerald-950/20'
                  )}
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {q.is_recommended && <Award className="w-3 h-3 text-emerald-600 flex-shrink-0" />}
                      <span className={cn('font-medium', q.is_recommended ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-800 dark:text-slate-100')}>
                        {q.supplier_name}
                      </span>
                    </div>
                    <span
                      className={cn(
                        'inline-block mt-1 text-[9px] px-1.5 py-0.5 rounded-full font-medium',
                        q.negotiation_round > 0
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                          : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                      )}
                    >
                      {q.negotiation_round > 0 ? `Revised · R${q.negotiation_round}` : 'Original'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="space-y-1">
                      {q.items.length === 0 && <span className="text-slate-400">—</span>}
                      {q.items.map((item, i) => (
                        <div key={i} className="whitespace-nowrap text-slate-700 dark:text-slate-200">
                          <span className="font-medium">{item.quantity}</span>
                          <span className="text-slate-400"> × </span>
                          <span className="font-medium">{q.currency} {item.unit_price.toLocaleString()}</span>
                          <span className="text-slate-400">/pc</span>
                          <span className="text-slate-500 dark:text-slate-400"> — {item.product_name}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap font-medium text-slate-800 dark:text-slate-100">
                    {q.currency} {q.total_amount.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-slate-600 dark:text-slate-300">
                    {q.delivery_days != null ? `${q.delivery_days} days` : '—'}
                  </td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-300 max-w-[180px] truncate">
                    {q.payment_terms || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
