"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { rfqService } from "@/services/rfq.service";
import { quotationService } from "@/services/quotation.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import { BarChart3, Search, TrendingUp, Trophy, Clock, DollarSign, Check, X } from "lucide-react";
import type { RFQ, Quotation } from "@/types";

export default function QuotationsPage() {
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [selectedRfq, setSelectedRfq] = useState<string>("");
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    rfqService.list({ limit: 50 }).then((data) => {
      const items = data.items || (data as any);
      setRfqs(items);
    }).catch(console.error);
  }, []);

  async function loadQuotations(rfqId: string) {
    setSelectedRfq(rfqId);
    setLoading(true);
    try {
      const [quots, comp] = await Promise.all([
        quotationService.listByRfq(rfqId),
        quotationService.compare(rfqId).catch(() => null),
      ]);
      setQuotations(quots);
      setComparison(comp);
    } catch (err) { console.error(err); }
    setLoading(false);
  }

  async function handleAccept(id: string) {
    await quotationService.accept(id);
    if (selectedRfq) loadQuotations(selectedRfq);
  }

  async function handleReject(id: string) {
    await quotationService.reject(id);
    if (selectedRfq) loadQuotations(selectedRfq);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-primary" /> Quotation Analysis
        </h1>
        <p className="text-muted-foreground mt-1">Compare and analyze vendor quotations</p>
      </div>

      <Card>
        <CardContent className="p-4">
          <label className="text-sm font-medium mb-2 block">Select RFQ to view quotations</label>
          <select
            className="w-full p-2 border rounded-lg text-sm"
            value={selectedRfq}
            onChange={(e) => loadQuotations(e.target.value)}
          >
            <option value="">-- Select an RFQ --</option>
            {rfqs.map((rfq) => (
              <option key={rfq.id} value={rfq.id}>
                {rfq.rfq_number} - {rfq.title}
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      )}

      {!loading && quotations.length > 0 && (
        <>
          {comparison?.recommendation && (
            <Card className="border-primary/30 bg-primary/5">
              <CardContent className="p-5">
                <div className="flex items-start gap-3">
                  <Trophy className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-primary">AI Recommendation</h3>
                    <p className="text-sm mt-1">{comparison.recommendation}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {quotations.map((q, idx) => (
              <Card key={q.id} className={`relative ${q.ai_ranking === 1 ? "border-primary ring-1 ring-primary/20" : ""}`}>
                {q.ai_ranking === 1 && (
                  <div className="absolute -top-3 left-4">
                    <Badge className="bg-primary text-white">Best Match</Badge>
                  </div>
                )}
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span>{q.supplier_name || `Supplier ${idx + 1}`}</span>
                    <Badge className={getStatusColor(q.status)}>{q.status}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                        <DollarSign className="w-3 h-3" /> Total
                      </div>
                      <p className="font-semibold">{formatCurrency(q.total_amount, q.currency)}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                        <Clock className="w-3 h-3" /> Delivery
                      </div>
                      <p className="font-semibold">{q.delivery_days || "N/A"} days</p>
                    </div>
                  </div>

                  {q.ai_score !== undefined && q.ai_score !== null && (
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-primary" />
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${q.ai_score}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium">{q.ai_score}/100</span>
                    </div>
                  )}

                  {q.items?.length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {q.items.length} line items
                    </div>
                  )}

                  {q.payment_terms && (
                    <p className="text-xs text-muted-foreground">Payment: {q.payment_terms}</p>
                  )}

                  {q.status === "received" && (
                    <div className="flex gap-2 pt-2 border-t">
                      <Button size="sm" className="flex-1" onClick={() => handleAccept(q.id)}>
                        <Check className="w-3 h-3 mr-1" /> Accept
                      </Button>
                      <Button size="sm" variant="outline" className="flex-1" onClick={() => handleReject(q.id)}>
                        <X className="w-3 h-3 mr-1" /> Reject
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      {!loading && selectedRfq && quotations.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No quotations received for this RFQ yet</p>
        </div>
      )}
    </div>
  );
}
