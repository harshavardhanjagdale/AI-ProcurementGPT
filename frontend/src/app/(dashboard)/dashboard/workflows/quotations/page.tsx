'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Mail, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

interface Quotation {
  quotation_id: string;
  supplier_name: string;
  supplier_email: string;
  total_amount: number;
  currency: string;
  delivery_days: number;
  warranty_terms: string;
  payment_terms: string;
  ai_score: number | null;
  ai_ranking: number | null;
  status: string;
  created_at: string;
}

interface WorkflowQuotations {
  workflow_id: string;
  rfq_id: string;
  rfq_number: string;
  quotations_count: number;
  quotations: Quotation[];
}

export default function QuotationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflow_id');

  const [quotations, setQuotations] = useState<WorkflowQuotations | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!workflowId) {
      setError('No workflow ID provided');
      setLoading(false);
      return;
    }

    fetchQuotations();
  }, [workflowId]);

  const fetchQuotations = async () => {
    if (!workflowId) return;

    try {
      setLoading(true);
      const response = await fetch(
        `/api/v1/chat/workflow/${workflowId}/quotations`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );

      if (!response.ok) throw new Error('Failed to fetch quotations');

      const data = await response.json();
      setQuotations(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch quotations');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckEmails = async () => {
    if (!workflowId) return;

    try {
      setChecking(true);
      const response = await fetch('/api/v1/chat/check-emails', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ workflow_id: workflowId }),
      });

      const data = await response.json();
      setCheckMessage(data.message);

      // Refresh quotations after check
      setTimeout(fetchQuotations, 1000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to check emails'
      );
    } finally {
      setChecking(false);
    }
  };

  if (!workflowId) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6">
            <p className="text-red-600">No workflow ID provided in URL</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p>Loading quotations...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const hasQuotations = quotations && quotations.quotations_count > 0;
  const hasAnalyzedQuotations = quotations?.quotations.some(q => q.ai_ranking);

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Quotations Received</h1>
          <p className="text-gray-600 text-sm">
            RFQ: {quotations?.rfq_number || 'N/A'} • Workflow: {workflowId}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleCheckEmails}
            disabled={checking}
            variant="default"
            className="gap-2"
          >
            {checking ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <Mail className="h-4 w-4" />
                Check Emails Now
              </>
            )}
          </Button>
          <Button
            onClick={fetchQuotations}
            disabled={loading}
            variant="outline"
            size="sm"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {checkMessage && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <p className="text-sm text-blue-900">{checkMessage}</p>
          </CardContent>
        </Card>
      )}

      {!hasQuotations ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <Mail className="h-12 w-12 mx-auto mb-3 text-gray-400" />
            <p className="text-gray-600 font-medium">No quotations received yet</p>
            <p className="text-sm text-gray-500 mt-1">
              Waiting for supplier responses. Click "Check Emails Now" to manually
              check, or wait for automatic email polling (every 60 seconds).
            </p>
            <Button
              onClick={handleCheckEmails}
              disabled={checking}
              className="mt-4"
              variant="default"
            >
              {checking ? 'Checking...' : 'Check Emails Now'}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>
                  {quotations.quotations_count} Quotation
                  {quotations.quotations_count !== 1 ? 's' : ''} Received
                </span>
                <Badge variant="default">
                  {hasAnalyzedQuotations ? '✓ Analyzed' : 'Pending Analysis'}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {quotations.quotations.map((q, idx) => (
                  <div
                    key={q.quotation_id}
                    className="border rounded p-4 hover:bg-gray-50"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="font-semibold text-lg">
                          {q.supplier_name}
                        </h3>
                        <p className="text-sm text-gray-600">{q.supplier_email}</p>
                      </div>
                      {q.ai_ranking && (
                        <div className="text-right">
                          <div className="text-3xl font-bold text-blue-600">
                            #{q.ai_ranking}
                          </div>
                          {q.ai_score && (
                            <div className="text-sm text-gray-600">
                              Score: {q.ai_score.toFixed(1)}/100
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      <div>
                        <p className="text-xs font-medium text-gray-500">
                          PRICE
                        </p>
                        <p className="text-lg font-bold">
                          {q.currency} {q.total_amount.toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs font-medium text-gray-500">
                          DELIVERY
                        </p>
                        <p className="text-lg font-bold">{q.delivery_days} days</p>
                      </div>

                      <div>
                        <p className="text-xs font-medium text-gray-500">
                          WARRANTY
                        </p>
                        <p className="text-sm font-medium truncate">
                          {q.warranty_terms || 'N/A'}
                        </p>
                      </div>

                      <div className="col-span-2 md:col-span-3">
                        <p className="text-xs font-medium text-gray-500">
                          PAYMENT TERMS
                        </p>
                        <p className="text-sm font-medium">
                          {q.payment_terms || 'N/A'}
                        </p>
                      </div>
                    </div>

                    {q.ai_ranking === 1 && (
                      <div className="mt-3 pt-3 border-t border-green-200 bg-green-50 rounded p-2">
                        <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                          <CheckCircle2 className="h-4 w-4" />
                          AI Recommendation: This is the best option
                        </div>
                      </div>
                    )}

                    <div className="text-xs text-gray-500 mt-3">
                      Received:{' '}
                      {new Date(q.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {hasAnalyzedQuotations && (
            <div className="bg-green-50 border border-green-200 rounded p-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-900">
                    Analysis Complete
                  </p>
                  <p className="text-sm text-green-800 mt-1">
                    The AI has analyzed all quotations and ranked them. Go to the
                    workflow monitor to approve the recommendation or negotiate.
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() =>
            router.push(
              `/dashboard/workflows?workflow_id=${workflowId}`
            )
          }
        >
          View Workflow Status
        </Button>
        <Button
          variant="outline"
          onClick={() => router.push('/dashboard/rfqs')}
        >
          Back to RFQs
        </Button>
      </div>
    </div>
  );
}
