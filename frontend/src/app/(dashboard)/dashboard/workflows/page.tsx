'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react';

interface WorkflowStatus {
  workflow_id: string;
  current_step: string;
  status: string;
  rfq_id: string;
  parsed_intent: {
    title: string;
    is_complete: boolean;
    items_count: number;
  };
  selected_suppliers_count: number;
  quotations_count: number;
  user_decision: string | null;
  error: string | null;
  timestamp: string;
  next_nodes: string[];
}

const STEP_DESCRIPTIONS = {
  parse_user_request: 'Parsing your request',
  validate_rfq_data: 'Validating RFQ data',
  resolve_direct_supplier: 'Finding direct supplier',
  create_rfq_record: 'Creating RFQ record',
  select_vendors: 'Selecting vendors',
  generate_rfq_emails: 'Generating RFQ emails',
  send_rfq_emails: 'Sending emails to suppliers',
  await_supplier_replies: 'Waiting for supplier responses',
  process_attachments: 'Processing quotations',
  analyze_quotations: 'Analyzing quotes',
  present_recommendation: 'Preparing recommendation',
  user_decision_gate: 'Awaiting your decision',
  negotiate_with_suppliers: 'Negotiating with suppliers',
  generate_purchase_order: 'Generating purchase order',
  send_po_email: 'Sending purchase order',
};

const STEP_ORDER = [
  'parse_user_request',
  'validate_rfq_data',
  'resolve_direct_supplier',
  'create_rfq_record',
  'select_vendors',
  'generate_rfq_emails',
  'send_rfq_emails',
  'await_supplier_replies',
  'process_attachments',
  'analyze_quotations',
  'present_recommendation',
  'user_decision_gate',
  'negotiate_with_suppliers',
  'generate_purchase_order',
  'send_po_email',
];

export default function WorkflowMonitorPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflow_id');

  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!workflowId) {
      setError('No workflow ID provided');
      setLoading(false);
      return;
    }

    const fetchStatus = async () => {
      try {
        const response = await fetch(
          `/api/v1/chat/workflow/${workflowId}/status`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );

        if (!response.ok) throw new Error('Failed to fetch workflow status');

        const data = await response.json();
        setStatus(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch status');
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();

    if (autoRefresh) {
      const interval = setInterval(fetchStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [workflowId, autoRefresh]);

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
            <p>Loading workflow status...</p>
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

  if (!status) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6">
            <p>No status data available</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentStepIndex = STEP_ORDER.indexOf(status.current_step);

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Workflow Monitor</h1>
          <p className="text-gray-600 text-sm">Workflow ID: {workflowId}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            onClick={() => setAutoRefresh(!autoRefresh)}
            size="sm"
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </Button>
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
            size="sm"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Status Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Current Status</span>
            <Badge
              variant={
                status.status === 'running'
                  ? 'default'
                  : status.status === 'paused'
                    ? 'outline'
                    : 'secondary'
              }
            >
              {status.status.toUpperCase()}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-gray-600">Current Step</p>
            <p className="text-lg font-semibold">
              {STEP_DESCRIPTIONS[status.current_step as keyof typeof STEP_DESCRIPTIONS] || status.current_step}
            </p>
          </div>

          {status.error && (
            <div className="bg-red-50 border border-red-200 rounded p-3">
              <p className="text-sm font-medium text-red-800">Error</p>
              <p className="text-sm text-red-700">{status.error}</p>
            </div>
          )}

          <div className="text-xs text-gray-500">
            Last updated: {new Date(status.timestamp).toLocaleTimeString()}
          </div>
        </CardContent>
      </Card>

      {/* Workflow Progress */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {STEP_ORDER.map((step, index) => {
              const isActive = index === currentStepIndex;
              const isComplete = index < currentStepIndex;
              const isNext = status.next_nodes?.includes(step);

              return (
                <div key={step} className="flex items-center gap-3">
                  <div
                    className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold ${
                      isComplete
                        ? 'bg-green-500 text-white'
                        : isActive
                          ? 'bg-blue-500 text-white'
                          : isNext
                            ? 'bg-yellow-500 text-white'
                            : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    {isComplete ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : isActive ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      index + 1
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={`text-sm ${isActive ? 'font-semibold' : ''}`}>
                      {STEP_DESCRIPTIONS[step as keyof typeof STEP_DESCRIPTIONS] || step}
                    </p>
                    {isActive && (
                      <p className="text-xs text-blue-600">In progress...</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* RFQ Details */}
      {status.parsed_intent && (
        <Card>
          <CardHeader>
            <CardTitle>RFQ Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-gray-600">Title</p>
                <p className="text-sm font-semibold">
                  {status.parsed_intent.title || 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Items</p>
                <p className="text-sm font-semibold">
                  {status.parsed_intent.items_count}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Suppliers</p>
                <p className="text-sm font-semibold">
                  {status.selected_suppliers_count}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600">Quotations</p>
                <p className="text-sm font-semibold">
                  {status.quotations_count}
                </p>
              </div>
            </div>

            {status.user_decision && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <p className="text-sm font-medium text-blue-800">
                  User Decision: <span className="font-bold">{status.user_decision}</span>
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Debug Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Debug Information</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-48 text-gray-800">
            {JSON.stringify(
              {
                workflow_id: status.workflow_id,
                current_step: status.current_step,
                status: status.status,
                rfq_id: status.rfq_id,
                next_nodes: status.next_nodes,
              },
              null,
              2
            )}
          </pre>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() =>
            router.push(
              `/dashboard/workflows/quotations?workflow_id=${workflowId}`
            )
          }
        >
          View Quotations
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
