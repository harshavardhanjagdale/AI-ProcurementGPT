'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertCircle, Activity, Zap } from 'lucide-react';

export default function WorkflowHelpPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">How to Monitor Your Workflows</h1>
        <p className="text-gray-600">
          Three simple ways to track your procurement workflows in real-time
        </p>
      </div>

      {/* Method 1: Dashboard */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-600" />
            Method 1: Web Dashboard (Easiest)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-gray-700">
            When you send an RFQ message, you'll get a direct link to monitor that workflow.
          </p>
          <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm space-y-2">
            <p>
              <strong>What you see:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 text-gray-700">
              <li>Current step with description</li>
              <li>Visual progress through all 15 workflow nodes</li>
              <li>RFQ details (items, suppliers, quotations)</li>
              <li>Real-time updates every 2 seconds</li>
              <li>Auto-refresh toggle</li>
            </ul>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="default">
              Go to Workflow Monitor
            </Button>
            <Button size="sm" variant="outline">
              View Workflows List
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Method 2: API */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-purple-600" />
            Method 2: REST API (For Scripts)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-gray-700">
            Programmatically check workflow status from any application.
          </p>
          <div className="bg-gray-900 text-gray-100 p-3 rounded text-xs font-mono space-y-2 overflow-auto">
            <div>GET /api/v1/chat/workflow/&#123;workflow_id&#125;/status</div>
            <div className="text-gray-500">Authorization: Bearer &#123;token&#125;</div>
            <div className="mt-2">Response:</div>
            <div className="text-green-400">
              <div>&#123;</div>
              <div className="ml-2">
                "current_step": "await_supplier_replies",
              </div>
              <div className="ml-2">
                "status": "running",
              </div>
              <div className="ml-2">
                "selected_suppliers_count": 5,
              </div>
              <div className="ml-2">
                "quotations_count": 3
              </div>
              <div>&#125;</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Method 3: Logs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-green-600" />
            Method 3: Server Logs (For Debugging)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-gray-700">
            Watch detailed transitions in your backend terminal with [WORKFLOW] prefix.
          </p>
          <div className="bg-gray-900 text-green-400 p-3 rounded text-xs font-mono space-y-1 overflow-auto max-h-40">
            <div>[WORKFLOW] Starting workflow abc123... for user user456...</div>
            <div>[WORKFLOW] Input: Buy 5 laptops...</div>
            <div>[WORKFLOW] abc123... reached step: select_vendors</div>
            <div>[WORKFLOW-STATE] abc123...:</div>
            <div className="ml-4">Current Step: select_vendors</div>
            <div className="ml-4">Parsed Intent: Laptops (complete: true)</div>
            <div className="ml-4">Items: 1 item(s)</div>
            <div className="ml-4">Selected Suppliers: 5 supplier(s)</div>
            <div className="ml-8">- TechSupply Corp (USA)</div>
            <div className="ml-8">- GlobalTech Ltd (India)</div>
          </div>
        </CardContent>
      </Card>

      {/* Workflow States */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow States at a Glance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">🔄 parse_user_request</span>
              <span className="text-gray-600">LLM converts natural language</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">✅ validate_rfq_data</span>
              <span className="text-gray-600">Checks mandatory fields</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">🎯 select_vendors</span>
              <span className="text-gray-600">Finds top 5 suppliers</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">✉️ send_rfq_emails</span>
              <span className="text-gray-600">Emails sent to suppliers</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">⏳ await_supplier_replies</span>
              <span className="text-gray-600">Waiting for responses</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">📊 analyze_quotations</span>
              <span className="text-gray-600">Comparing offers</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="font-medium">🛑 user_decision_gate</span>
              <span className="text-gray-600">PAUSED - Awaiting your input</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="font-medium">📄 generate_purchase_order</span>
              <span className="text-gray-600">Creating final PO</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pro Tips */}
      <Card className="border-amber-200 bg-amber-50">
        <CardHeader>
          <CardTitle className="text-amber-900">💡 Pro Tips</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-amber-900">
          <p>
            <strong>Tip 1:</strong> Workflows pause at "user_decision_gate" waiting
            for your approval/negotiation decision. Check dashboard regularly.
          </p>
          <p>
            <strong>Tip 2:</strong> "await_supplier_replies" may take hours if
            waiting for real emails. Use demo data for instant testing.
          </p>
          <p>
            <strong>Tip 3:</strong> Open workflow monitor in a separate tab to watch
            progress while working on other RFQs.
          </p>
          <p>
            <strong>Tip 4:</strong> You don't need LangSmith for local development
            — your dashboard has everything!
          </p>
        </CardContent>
      </Card>

      {/* Call to Action */}
      <div className="flex gap-3">
        <Button size="lg" className="flex-1">
          Start New RFQ & Monitor
        </Button>
        <Button size="lg" variant="outline" className="flex-1">
          Read Full Guide
        </Button>
      </div>
    </div>
  );
}
