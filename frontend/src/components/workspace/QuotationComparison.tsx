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
  'analyze_quotations',
  'present_recommendation',
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
    <div className="border-t border-gray-200 bg-white px-4 py-3 flex-shrink-0 max-h-[35vh] flex flex-col">
      <div className="max-w-4xl mx-auto w-full flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <h4 className="text-xs font-semibold text-gray-700">
            Quotation Comparison ({quotations.length})
          </h4>
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />}
        </div>
        <div className="overflow-auto rounded-lg border border-gray-200 min-h-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="text-left px-3 py-2 font-medium">Supplier</th>
                <th className="text-left px-3 py-2 font-medium">Items (Qty × Rate)</th>
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
                    'border-t border-gray-100 align-top',
                    q.is_recommended && 'bg-green-50'
                  )}
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {q.is_recommended && (
                        <Award className="w-3.5 h-3.5 text-green-600 flex-shrink-0" />
                      )}
                      <span className={cn('font-medium', q.is_recommended ? 'text-green-800' : 'text-gray-800')}>
                        {q.supplier_name}
                      </span>
                    </div>
                    {(q.strengths.length > 0 || q.weaknesses.length > 0) && (
                      <div className="mt-1 space-y-0.5">
                        {q.strengths.slice(0, 2).map((s, i) => (
                          <p key={`s-${i}`} className="text-[10px] text-green-700">+ {s}</p>
                        ))}
                        {q.weaknesses.slice(0, 1).map((w, i) => (
                          <p key={`w-${i}`} className="text-[10px] text-amber-700">- {w}</p>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="space-y-1">
                      {q.items.map((item, i) => (
                        <div key={i} className="whitespace-nowrap">
                          <span className="text-gray-800">{item.quantity} units</span>
                          <span className="text-gray-400"> × </span>
                          <span className="text-gray-800">
                            {q.currency} {item.unit_price.toLocaleString()}/unit
                          </span>
                          <span className="text-gray-500"> — {item.product_name}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-gray-800">
                    {q.currency} {q.total_amount.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap text-gray-600">
                    {q.delivery_days != null ? `${q.delivery_days}d` : '—'}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {q.ai_score != null ? (
                      <span className={cn('font-semibold', q.is_recommended ? 'text-green-700' : 'text-gray-700')}>
                        {q.ai_score.toFixed(1)}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-600">
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
