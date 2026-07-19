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
  BarChart3,
  Clock,
  TrendingDown,
  PiggyBank,
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
  // Single-select: which quotation the user picks to approve (→ PO) or negotiate.
  const [selectedQuotationId, setSelectedQuotationId] = useState<string | null>(null);
  const quotationReady = !!sessionId && !!currentStep && QUOTATIONS_READY_STEPS.has(currentStep);

  // Default the selection to the recommended quote (else the first), and keep it valid as
  // more quotations arrive. Only auto-set when nothing valid is currently selected, so the
  // user's explicit pick is never overridden by a poll refresh.
  useEffect(() => {
    if (quotations.length === 0) return;
    setSelectedQuotationId((prev) => {
      if (prev && quotations.some((q) => q.id === prev)) return prev;
      return (quotations.find((q) => q.is_recommended) || quotations[0]).id;
    });
  }, [quotations]);

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

  // The quote the user selected drives both Approve (→ PO) and Negotiate.
  const selectedQuote =
    quotations.find((q) => q.id === selectedQuotationId) ||
    quotations.find((q) => q.is_recommended) ||
    quotations[0];
  // Negotiation is expressed as a per-piece rate. Total quantity across the quote's line
  // items lets us convert the per-piece counter to the order total the backend expects.
  const negoQty = selectedQuote?.items?.reduce((sum, it) => sum + (it.quantity || 0), 0) || 1;
  const negoCurrentPerPiece = selectedQuote ? selectedQuote.total_amount / (negoQty || 1) : 0;

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
      // Cancel needs no quotation; approve/negotiate act on the user's selected quote.
      const quotationId = decision === 'cancel' ? undefined : selectedQuote?.id;
      const result = await workflowService.submitDecision(sessionId, decision, targetPrice, quotationId);
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
            <ChatSkeleton />
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}
        </div>

        {/* Inline quotation comparison — wider than the chat column to use the space */}
        {quotationReady && quotations.length > 0 && (
          <div className="my-5 max-w-5xl mx-auto">
            <InlineQuotationPanel
              quotations={quotations}
              open={quotationsOpen}
              onToggle={() => setQuotationsOpen(!quotationsOpen)}
              selectedId={selectedQuotationId}
              onSelect={setSelectedQuotationId}
              selectable={showDecisionActions || (!!currentStep && DECISION_STEPS.has(currentStep))}
            />
          </div>
        )}

        <div className="max-w-2xl mx-auto space-y-5">
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

      {/* Decision actions — compact bar, shown only when a decision is needed */}
      {showDecisionActions && !negotiateMode && (
        <div className="border-t border-slate-200 dark:border-slate-800 px-4 md:px-6 py-2.5 bg-gradient-to-r from-indigo-50/60 to-violet-50/60 dark:from-indigo-950/30 dark:to-violet-950/30 animate-fade-in-up">
          <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl mx-auto">
            <span className="text-xs text-slate-500 dark:text-slate-400 mr-1 hidden sm:inline">
              {selectedQuote ? `${selectedQuote.supplier_name} selected —` : 'Ready to decide:'}
            </span>
            <button
              onClick={() => handleDecision('approve')}
              disabled={!!decidingOn}
              title="Approve the selected quotation and create a purchase order"
              className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-green-600 text-white text-[13px] font-medium hover:from-emerald-700 hover:to-green-700 disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-sm shadow-emerald-600/25"
            >
              {decidingOn === 'approve' ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Approve &amp; PO
            </button>
            <button
              onClick={() => setNegotiateMode(true)}
              disabled={!!decidingOn}
              title="Send a counter-offer to the selected supplier"
              className="px-3.5 py-1.5 rounded-lg bg-amber-500 text-white text-[13px] font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors flex items-center gap-1.5 shadow-sm shadow-amber-500/20"
            >
              <Handshake className="w-4 h-4" />
              Negotiate
            </button>
            <button
              onClick={() => handleDecision('cancel')}
              disabled={!!decidingOn}
              title="Cancel this procurement"
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-[13px] font-medium hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors flex items-center gap-1.5"
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
                Send a counter-offer{selectedQuote ? ` to ${selectedQuote.supplier_name}` : ''}
              </div>
            </div>
            {selectedQuote && (
              <p className="text-xs text-amber-800/80 dark:text-amber-300/80 mb-3 ml-9">
                They quoted <span className="font-semibold">{selectedQuote.currency} {negoCurrentPerPiece.toLocaleString(undefined, { maximumFractionDigits: 2 })}/pc</span>
                {' '}for <span className="font-semibold">{negoQty}</span> units.
                Enter your target <span className="font-semibold">rate per piece</span> — I&apos;ll draft &amp; send the counter-offer.
              </p>
            )}
            <div className="flex items-center gap-2 ml-9">
              <div className="relative flex-1 max-w-xs">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-amber-700 dark:text-amber-400 font-medium">
                  {selectedQuote?.currency || '₹'}
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

function ChatSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      {[
        { me: false, w: 'w-2/3' },
        { me: true, w: 'w-1/2' },
        { me: false, w: 'w-3/4' },
      ].map((r, i) => (
        <div key={i} className={cn('flex items-end gap-2.5', r.me && 'flex-row-reverse')}>
          <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-800 flex-shrink-0" />
          <div className={cn('h-14 rounded-2xl bg-slate-200 dark:bg-slate-800', r.w)} />
        </div>
      ))}
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
      <div className="flex justify-center py-1 animate-fade-in-up">
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
      <div className="flex justify-center py-1.5 animate-fade-in-up">
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
    <div className={cn('flex items-end gap-2.5 animate-fade-in-up', isUser && 'flex-row-reverse')}>
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

  // While the graph is mid-run (input not accepted, not terminal), collapse the whole
  // input bar to a slim, unobtrusive status chip instead of a disabled textarea + a
  // large "input disabled" banner — reclaiming vertical space for the conversation.
  const inProgress = !acceptsInput && !isTerminal;
  if (inProgress) {
    return (
      <div className="border-t border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 md:px-8 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-center">
          <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-100/80 dark:bg-slate-800/70 border border-slate-200/70 dark:border-slate-700/70 text-xs font-medium text-slate-500 dark:text-slate-400">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-500" />
            {STEP_PLACEHOLDERS[step] || 'Working…'}
          </span>
        </div>
      </div>
    );
  }

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
    </div>
  );
}

function InlineQuotationPanel({
  quotations,
  open,
  onToggle,
  selectedId,
  onSelect,
  selectable = false,
}: {
  quotations: Quotation[];
  open: boolean;
  onToggle: () => void;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  selectable?: boolean;
}) {
  const prices = quotations.map((q) => q.total_amount);
  const bestPrice = Math.min(...prices);
  const highestPrice = Math.max(...prices);
  const savings = highestPrice - bestPrice;
  const cur = quotations[0]?.currency || '';
  const bestSupplier = quotations.find((q) => q.total_amount === bestPrice);
  const deliveries = quotations.map((q) => q.delivery_days).filter((d): d is number => d != null);
  const fastest = deliveries.length ? Math.min(...deliveries) : null;
  const fastestSupplier = fastest != null ? quotations.find((q) => q.delivery_days === fastest) : null;
  const recommended = quotations.find((q) => q.is_recommended);
  const fmt = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

  return (
    <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/50 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm flex-shrink-0">
            <BarChart3 className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Quotation Comparison
          </span>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300">
            {quotations.length} quotes
          </span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      {open && (
        <div className="border-t border-slate-100 dark:border-slate-700">
          {/* Insight strip — key takeaways at a glance */}
          {quotations.length > 1 && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-slate-100 dark:bg-slate-700/60">
              <Insight tone="emerald" icon={<TrendingDown className="w-3.5 h-3.5" />} label="Best price" value={`${cur} ${fmt(bestPrice)}`} sub={bestSupplier?.supplier_name} />
              <Insight tone="emerald" icon={<PiggyBank className="w-3.5 h-3.5" />} label="Potential saving" value={`${cur} ${fmt(savings)}`} sub="vs highest quote" />
              <Insight tone="sky" icon={<Clock className="w-3.5 h-3.5" />} label="Fastest delivery" value={fastest != null ? `${fastest} days` : '—'} sub={fastestSupplier?.supplier_name} />
              <Insight tone="violet" icon={<Sparkles className="w-3.5 h-3.5" />} label="AI recommends" value={recommended?.supplier_name || '—'} sub={recommended ? 'top ranked' : 'analyzing…'} />
            </div>
          )}

          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 sticky top-0 z-10">
                  {selectable && <th className="text-center px-3 py-2.5 font-semibold w-10">Pick</th>}
                  <th className="text-left px-3 py-2.5 font-semibold">Supplier</th>
                  <th className="text-left px-3 py-2.5 font-semibold">Items (Qty × Rate/pc)</th>
                  <th className="text-right px-3 py-2.5 font-semibold">Order Total</th>
                  <th className="text-right px-3 py-2.5 font-semibold">Delivery</th>
                  <th className="text-left px-3 py-2.5 font-semibold">Payment Terms</th>
                </tr>
              </thead>
              <tbody>
                {quotations.map((q) => {
                  const isSelected = selectable && selectedId === q.id;
                  const isCheapest = q.total_amount === bestPrice;
                  const isFastest = fastest != null && q.delivery_days === fastest;
                  const delta = q.total_amount - bestPrice;
                  return (
                  <tr
                    key={q.id}
                    onClick={selectable ? () => onSelect?.(q.id) : undefined}
                    className={cn(
                      'border-t border-slate-100 dark:border-slate-700 align-top transition-colors',
                      selectable && 'cursor-pointer hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20',
                      isSelected
                        ? 'bg-indigo-50 dark:bg-indigo-950/30 ring-1 ring-inset ring-indigo-300 dark:ring-indigo-700'
                        : q.is_recommended && 'bg-emerald-50/40 dark:bg-emerald-950/20'
                    )}
                  >
                    {selectable && (
                      <td className="px-3 py-3 text-center">
                        <input
                          type="radio"
                          name="selected-quotation"
                          checked={isSelected}
                          onChange={() => onSelect?.(q.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 accent-indigo-600 cursor-pointer"
                          aria-label={`Select quotation from ${q.supplier_name}`}
                        />
                      </td>
                    )}
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={cn('font-semibold text-[13px]', q.is_recommended ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-800 dark:text-slate-100')}>
                          {q.supplier_name}
                        </span>
                        {q.is_recommended && (
                          <span className="inline-flex items-center gap-0.5 text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-emerald-500 to-green-500 text-white">
                            <Sparkles className="w-2.5 h-2.5" /> AI PICK
                          </span>
                        )}
                        {q.ai_ranking != null && (
                          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                            #{q.ai_ranking}
                          </span>
                        )}
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
                    <td className="px-3 py-3">
                      <div className="space-y-1">
                        {q.items.length === 0 && <span className="text-slate-400">—</span>}
                        {q.items.map((item, i) => (
                          <div key={i} className="whitespace-nowrap text-slate-700 dark:text-slate-200">
                            <span className="font-medium tabular-nums">{item.quantity}</span>
                            <span className="text-slate-400"> × </span>
                            <span className="font-medium tabular-nums">{q.currency} {item.unit_price.toLocaleString()}</span>
                            <span className="text-slate-400">/pc</span>
                            <span className="text-slate-500 dark:text-slate-400"> — {item.product_name}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap">
                      <div className="font-bold text-[13px] text-slate-900 dark:text-slate-50 tabular-nums">
                        {q.currency} {q.total_amount.toLocaleString()}
                      </div>
                      {isCheapest ? (
                        <div className="inline-flex items-center gap-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 mt-0.5">
                          <TrendingDown className="w-3 h-3" /> Lowest
                        </div>
                      ) : (
                        <div className="text-[10px] text-rose-500 dark:text-rose-400 font-medium mt-0.5 tabular-nums">
                          +{q.currency} {delta.toLocaleString()}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap text-slate-600 dark:text-slate-300">
                      <div className="tabular-nums">{q.delivery_days != null ? `${q.delivery_days} days` : '—'}</div>
                      {isFastest && <div className="text-[10px] font-medium text-sky-600 dark:text-sky-400 mt-0.5">Fastest</div>}
                    </td>
                    <td className="px-3 py-3 text-slate-600 dark:text-slate-300 max-w-[200px] truncate">
                      {q.payment_terms || '—'}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Insight({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  tone: 'emerald' | 'sky' | 'violet';
}) {
  const toneCls = {
    emerald: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40',
    sky: 'text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/40',
    violet: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-950/40',
  }[tone];
  return (
    <div className="bg-white dark:bg-slate-800 px-3.5 py-2.5 flex items-center gap-2.5">
      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', toneCls)}>{icon}</div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 font-semibold">{label}</div>
        <div className="text-[13px] font-bold text-slate-800 dark:text-slate-100 truncate">{value}</div>
        {sub && <div className="text-[10px] text-slate-400 dark:text-slate-500 truncate">{sub}</div>}
      </div>
    </div>
  );
}
