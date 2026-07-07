'use client';

import { useEffect, useRef } from 'react';
import {
  FileText,
  FilePlus2,
  Target,
  Users,
  PenLine,
  Send,
  Inbox,
  ScanLine,
  BarChart3,
  UserCheck,
  Handshake,
  FileCheck2,
  MailCheck,
  Check,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WorkflowStep } from '@/services/workflow.service';

interface WorkflowProgressProps {
  steps: WorkflowStep[];
  currentStep: string | null;
  currentAgent: string | null;
  progress: number;
  status?: string | null;
}

type StepMeta = { short: string; icon: LucideIcon; phase: string };

const STEP_META: Record<string, StepMeta> = {
  parse_request:           { short: 'Understanding',    icon: FileText,     phase: 'Request' },
  create_rfq_record:       { short: 'Creating RFQ',     icon: FilePlus2,    phase: 'Finding Suppliers' },
  resolve_direct_supplier: { short: 'Direct Match',     icon: Target,       phase: 'Finding Suppliers' },
  select_vendors:          { short: 'Picking Vendors',  icon: Users,        phase: 'Finding Suppliers' },
  generate_rfq_emails:     { short: 'Writing Emails',   icon: PenLine,      phase: 'Sending Quotes' },
  send_rfq_emails:         { short: 'Sending RFQ',      icon: Send,         phase: 'Sending Quotes' },
  await_supplier_replies:  { short: 'Waiting Reply',    icon: Inbox,        phase: 'Waiting' },
  ocr_extract:             { short: 'OCR Extract',      icon: ScanLine,     phase: 'Comparing' },
  user_decision_gate:      { short: 'Approve/Reject',   icon: UserCheck,    phase: 'Finalizing' },
  negotiate_with_suppliers:{ short: 'Negotiating',      icon: Handshake,    phase: 'Finalizing' },
  generate_purchase_order: { short: 'Creating PO',      icon: FileCheck2,   phase: 'Finalizing' },
  send_po_email:           { short: 'Sending PO',       icon: MailCheck,    phase: 'Finalizing' },
};

const PHASES = ['Request', 'Finding Suppliers', 'Sending Quotes', 'Waiting', 'Comparing', 'Finalizing'] as const;
const PHASE_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  'Request': { bg: 'bg-blue-50 dark:bg-blue-950/40', text: 'text-blue-700 dark:text-blue-300', icon: 'text-blue-500' },
  'Finding Suppliers': { bg: 'bg-purple-50 dark:bg-purple-950/40', text: 'text-purple-700 dark:text-purple-300', icon: 'text-purple-500' },
  'Sending Quotes': { bg: 'bg-cyan-50 dark:bg-cyan-950/40', text: 'text-cyan-700 dark:text-cyan-300', icon: 'text-cyan-500' },
  'Waiting': { bg: 'bg-amber-50 dark:bg-amber-950/40', text: 'text-amber-700 dark:text-amber-300', icon: 'text-amber-500' },
  'Comparing': { bg: 'bg-teal-50 dark:bg-teal-950/40', text: 'text-teal-700 dark:text-teal-300', icon: 'text-teal-500' },
  'Finalizing': { bg: 'bg-emerald-50 dark:bg-emerald-950/40', text: 'text-emerald-700 dark:text-emerald-300', icon: 'text-emerald-500' },
};

const PHASE_ICON: Record<string, LucideIcon> = {
  'Request': FileText,
  'Finding Suppliers': Users,
  'Sending Quotes': Send,
  'Waiting': Inbox,
  'Comparing': BarChart3,
  'Finalizing': FileCheck2,
};

type Status = 'completed' | 'running' | 'failed' | 'pending' | 'skipped' | 'cancelled';

/**
 * Derive the effective status of each step.
 * - completed session: all steps → completed
 * - failed session: failed step stays failed, rest → completed
 * - cancelled session: steps before/at decision → completed, rest → skipped
 * - Otherwise: before currentStep → completed, at → running, after → pending
 */
function getEffectiveStatus(
  step: WorkflowStep,
  currentStep: string | null,
  allSteps: WorkflowStep[],
  sessionStatus: string | null | undefined
): Status {
  if (sessionStatus === 'completed') return 'completed';

  if (sessionStatus === 'failed') {
    // Only mark as completed if the backend actually completed it
    if (step.status === 'failed') return 'failed';
    if (step.status === 'completed') return 'completed';
    return 'pending';
  }

  if (sessionStatus === 'cancelled') {
    const currentIdx = allSteps.findIndex((s) => s.name === currentStep);
    const thisIdx = allSteps.findIndex((s) => s.id === step.id);
    if (currentIdx === -1) return step.status === 'completed' ? 'completed' : 'skipped';
    if (thisIdx <= currentIdx) return step.status === 'completed' ? 'completed' : 'skipped';
    return 'skipped';
  }

  // Use actual backend status when available — trust the source of truth
  if (step.status === 'completed') return 'completed';
  if (step.status === 'failed') return 'failed';
  if (step.status === 'running') return 'running';

  if (!currentStep) return (step.status as Status) || 'pending';

  const currentIdx = allSteps.findIndex((s) => s.name === currentStep);
  const thisIdx = allSteps.findIndex((s) => s.id === step.id);

  if (currentIdx === -1) return (step.status as Status) || 'pending';

  if (thisIdx < currentIdx) return 'completed';
  if (thisIdx === currentIdx) return 'running';
  return 'pending';
}

function phaseStatus(
  phase: string,
  steps: WorkflowStep[],
  currentStep: string | null,
  sessionStatus: string | null | undefined
): Status {
  const members = steps.filter((s) => STEP_META[s.name]?.phase === phase);
  if (members.length === 0) return 'pending';

  const statuses = members.map((s) => getEffectiveStatus(s, currentStep, steps, sessionStatus));
  if (statuses.some((s) => s === 'failed')) return 'failed';
  if (statuses.every((s) => s === 'skipped' || s === 'cancelled')) return 'skipped';
  if (statuses.some((s) => s === 'running')) return 'running';
  if (statuses.every((s) => s === 'completed' || s === 'skipped')) return 'completed';
  if (statuses.some((s) => s === 'completed')) return 'running';
  return 'pending';
}

export function WorkflowProgress({
  steps,
  currentStep,
  currentAgent,
  progress,
  status,
}: WorkflowProgressProps) {
  const stripRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
  }, [currentStep, status]);

  if (steps.length === 0) {
    return (
      <div className="px-5 py-4 text-center text-sm text-slate-400 dark:text-slate-500">
        The workflow will appear here once your procurement starts.
      </div>
    );
  }

  const activeMeta = currentStep ? STEP_META[currentStep] : null;
  const isDone = status === 'completed';
  const isCancelled = status === 'cancelled';
  const isFailed = status === 'failed';
  const isTerminal = isDone || isCancelled || isFailed;
  const pct = Math.round(progress);

  return (
    <div className="px-5 pt-4 pb-3 bg-white dark:bg-slate-900">
      {/* Header row with large progress bar */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Workflow
          </span>
          {activeMeta && !isTerminal && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 text-[11px] font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
              </span>
              {currentAgent || activeMeta.short}
            </span>
          )}
          {isDone && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-[11px] font-medium">
              <Check className="w-3 h-3" /> Done
            </span>
          )}
          {isCancelled && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-[11px] font-medium">
              Cancelled
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 text-[11px] font-medium">
              Failed
            </span>
          )}
        </div>
        <div className="flex items-center gap-2.5">
          <div className="w-36 h-2.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden shadow-inner">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-1000 ease-out',
                isDone && 'bg-gradient-to-r from-emerald-400 to-green-500',
                isCancelled && 'bg-slate-400 dark:bg-slate-500',
                isFailed && 'bg-gradient-to-r from-rose-400 to-red-500',
                !isTerminal && 'bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500'
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-sm font-bold tabular-nums text-slate-600 dark:text-slate-300 min-w-[36px] text-right">
            {pct}%
          </span>
        </div>
      </div>

      {/* Macro phase row - Always colorful, static display */}
      <div className="flex items-center gap-0.5 mb-4">
        {PHASES.map((phase, i) => {
          const Icon = PHASE_ICON[phase];
          const colors = PHASE_COLORS[phase];
          const st = phaseStatus(phase, steps, currentStep, status);
          const isActive = st === 'running' || st === 'completed';
          return (
            <div key={phase} className="flex-1 flex items-center gap-0.5 min-w-0">
              <div
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[11px] font-medium whitespace-nowrap',
                  colors.bg,
                  colors.text,
                  isActive && 'ring-1 ring-offset-1 dark:ring-offset-slate-900'
                )}
              >
                <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${colors.icon}`} />
                <span className="hidden lg:inline">{phase}</span>
              </div>
              {i < PHASES.length - 1 && (
                <div className="flex-1 h-[3px] rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800 mx-0.5">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-700',
                      st === 'completed' && 'w-full bg-emerald-400',
                      st === 'running' && 'w-1/2 bg-indigo-400 animate-pulse',
                      (st === 'pending' || st === 'failed' || st === 'skipped' || st === 'cancelled') && 'w-0'
                    )}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Micro step strip */}
      <div ref={stripRef} className="overflow-x-auto scrollbar-slim -mx-1 px-1 pb-1">
        <div className="flex items-stretch gap-0 min-w-max">
          {steps.map((step, idx) => {
            const meta = STEP_META[step.name];
            if (!meta) return null;
            const Icon = meta.icon;
            const st = getEffectiveStatus(step, currentStep, steps, status);
            const shouldScrollTo = st === 'running' || st === 'failed';
            const isLast = idx === steps.length - 1;

            return (
              <div key={step.id} className="flex items-center">
                <div
                  ref={shouldScrollTo ? activeRef : undefined}
                  className="flex flex-col items-center gap-1.5 w-[88px] px-0.5 group"
                >
                  <div
                    className={cn(
                      'relative flex items-center justify-center w-9 h-9 rounded-xl border-2 transition-all duration-500',
                      st === 'completed' && 'bg-emerald-500 border-emerald-500 text-white shadow-sm shadow-emerald-500/25',
                      st === 'running' && 'bg-gradient-to-br from-indigo-500 to-violet-600 border-indigo-400 text-white shadow-lg shadow-indigo-500/30 scale-110',
                      st === 'failed' && 'bg-rose-500 border-rose-500 text-white shadow-sm shadow-rose-500/25',
                      (st === 'pending' || st === 'skipped' || st === 'cancelled') &&
                        'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500'
                    )}
                  >
                    {st === 'running' && (
                      <span className="absolute inset-0 rounded-xl border-2 border-indigo-400 animate-ping opacity-30" />
                    )}
                    {st === 'completed' ? (
                      <Check className="w-4 h-4" />
                    ) : (
                      <Icon className="w-4 h-4" />
                    )}
                  </div>
                  <span
                    className={cn(
                      'text-[10px] leading-tight text-center font-medium transition-colors duration-300',
                      shouldScrollTo
                        ? 'text-indigo-700 dark:text-indigo-300 font-semibold'
                        : st === 'completed'
                          ? 'text-slate-600 dark:text-slate-400'
                          : 'text-slate-400 dark:text-slate-600'
                    )}
                  >
                    {meta.short}
                  </span>
                </div>
                {!isLast && (
                  <div
                    className={cn(
                      'h-[3px] w-4 rounded-full mb-5 transition-all duration-700',
                      st === 'completed'
                        ? 'bg-emerald-400'
                        : st === 'running'
                          ? 'bg-indigo-300 animate-pulse'
                          : (st === 'skipped' || st === 'cancelled')
                            ? 'bg-slate-200/50 dark:bg-slate-800'
                            : 'bg-slate-200 dark:bg-slate-700'
                    )}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
