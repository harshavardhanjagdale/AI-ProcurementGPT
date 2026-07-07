'use client';

import { useEffect, useState } from 'react';
import { Award, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { workflowService, type Quotation } from '@/services/workflow.service';

interface QuotationComparisonProps {
  sessionId: string | null;
  currentStep?: string | null;
}

const QUOTATIONS_READY_STEPS = new Set([
  'ocr_extract',
  'user_decision_gate',
  'negotiate_with_suppliers',
  'generate_purchase_order',
  'send_po_email',
]);

export function QuotationComparison({ sessionId, currentStep }: QuotationComparisonProps) {
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [loading, setLoading] = useState(false);

  const ready = !!sessionId && !!currentStep && QUOTATIONS_READY_STEPS.has(currentStep);

  useEffect(() => {
    if (!ready) {
      setQuotations([]);
      return;
    }
    loadQuotations();
    const interval = setInterval(loadQuotations, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, ready]);

  const loadQuotations = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const data = await workflowService.getQuotations(sessionId);
      setQuotations(data.quotations);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  if (!ready || quotations.length === 0) return null;

  return (
    <div className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 md:px-6 py-3 flex-shrink-0 max-h-[35vh] flex flex-col">
      <div className="max-w-4xl mx-auto w-full flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
            <Award className="w-3.5 h-3.5 text-indigo-500" />
            Quotation Comparison ({quotations.length})
          </h4>
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />}
        </div>
        <div className="overflow-auto scrollbar-slim rounded-xl border border-slate-200 dark:border-slate-800 min-h-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 sticky top-0">
                <th className="text-left px-3 py-2 font-medium">Supplier</th>
                <th className="text-left px-3 py-2 font-medium">Items (Qty × Rate)</th>
                <th className="text-right px-3 py-2 font-medium">Subtotal</th>
                <th className="text-right px-3 py-2 font-medium">Tax</th>
                <th className="text-right px-3 py-2 font-medium">Total</th>
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
                    'border-t border-slate-100 dark:border-slate-800 align-top',
                    q.is_recommended && 'bg-emerald-50 dark:bg-emerald-950/30'
                  )}
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {q.is_recommended && (
                        <Award className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                      )}
                      <span className={cn('font-medium', q.is_recommended ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-800 dark:text-slate-100')}>
                        {q.supplier_name}
                      </span>
                    </div>
                    {(q.strengths.length > 0 || q.weaknesses.length > 0) && (
                      <div className="mt-1 space-y-0.5">
                        {q.strengths.slice(0, 2).map((s, i) => (
                          <p key={`s-${i}`} className="text-[10px] text-emerald-700 dark:text-emerald-400">+ {s}</p>
                        ))}
                        {q.weaknesses.slice(0, 1).map((w, i) => (
                          <p key={`w-${i}`} className="text-[10px] text-amber-700 dark:text-amber-400">- {w}</p>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="space-y-1">
                      {q.items.map((item, i) => (
                        <div key={i} className="whitespace-nowrap">
                          <span className="text-slate-800 dark:text-slate-100">{item.quantity} units</span>
                          <span className="text-slate-400"> × </span>
                          <span className="text-slate-800 dark:text-slate-100">
                            {q.currency} {item.unit_price.toLocaleString()}/unit
                          </span>
                          <span className="text-slate-500"> — {item.product_name}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-slate-700 dark:text-slate-200">
                    {q.currency} {q.total_amount.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-slate-500 dark:text-slate-400 text-[10px]">
                    {q.tax_percent ? (
                      <div>
                        <div className="font-medium">{q.tax_percent}% GST</div>
                        {q.tax_amount != null && (
                          <div>{q.currency} {q.tax_amount.toLocaleString()}</div>
                        )}
                      </div>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-slate-800 dark:text-slate-100 font-semibold">
                    {q.grand_total
                      ? `${q.currency} ${q.grand_total.toLocaleString()}`
                      : `${q.currency} ${q.total_amount.toLocaleString()}`}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-slate-600 dark:text-slate-300">
                    {q.delivery_days != null ? `${q.delivery_days}d` : '—'}
                  </td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-300">
                    <div className="max-w-[220px] truncate" title={`${q.payment_terms || ''} · ${q.warranty_terms || ''}`}>
                      {q.payment_terms || '—'}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
