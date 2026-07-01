"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { rfqService } from "@/services/rfq.service";
import { formatDate, formatCurrency, getStatusColor } from "@/lib/utils";
import { ArrowLeft, Send, Package, Users } from "lucide-react";
import type { RFQ } from "@/types";

export default function RFQDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [rfq, setRfq] = useState<RFQ | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (id) {
      rfqService.get(id).then(setRfq).catch(console.error).finally(() => setLoading(false));
    }
  }, [id]);

  async function handleSendRFQ() {
    if (!rfq) return;
    setSending(true);
    try {
      await rfqService.sendEmails(rfq.id);
      const updated = await rfqService.get(rfq.id);
      setRfq(updated);
    } catch (err) { console.error(err); }
    setSending(false);
  }

  if (loading) {
    return <div className="h-64 rounded-xl bg-white border animate-pulse" />;
  }

  if (!rfq) {
    return <div className="text-center py-12 text-muted-foreground">RFQ not found</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/dashboard/rfqs">
          <Button variant="ghost" size="icon"><ArrowLeft className="w-5 h-5" /></Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{rfq.title}</h1>
            <Badge className={getStatusColor(rfq.status)}>{rfq.status.replace(/_/g, " ")}</Badge>
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            {rfq.rfq_number} • Created {formatDate(rfq.created_at)}
          </p>
        </div>
        {rfq.status === "vendors_selected" && (
          <Button onClick={handleSendRFQ} disabled={sending}>
            <Send className="w-4 h-4 mr-2" /> {sending ? "Sending..." : "Send RFQ Emails"}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Package className="w-5 h-5" /> Items ({rfq.items?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-3 pr-4">Product</th>
                      <th className="pb-3 pr-4">Qty</th>
                      <th className="pb-3 pr-4">Unit</th>
                      <th className="pb-3">Est. Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rfq.items?.map((item) => (
                      <tr key={item.id} className="border-b last:border-0">
                        <td className="py-3 pr-4">
                          <div className="font-medium">{item.product_name}</div>
                          {item.specifications && (
                            <div className="text-xs text-muted-foreground mt-0.5">{item.specifications}</div>
                          )}
                        </td>
                        <td className="py-3 pr-4">{item.quantity}</td>
                        <td className="py-3 pr-4">{item.unit}</td>
                        <td className="py-3">
                          {item.estimated_unit_price ? formatCurrency(item.estimated_unit_price, rfq.currency) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {rfq.description && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Description</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{rfq.description}</p>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-lg">Details</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {rfq.budget_min && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Min Budget</span>
                  <span className="font-medium">{formatCurrency(rfq.budget_min, rfq.currency)}</span>
                </div>
              )}
              {rfq.budget_max && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Max Budget</span>
                  <span className="font-medium">{formatCurrency(rfq.budget_max, rfq.currency)}</span>
                </div>
              )}
              {rfq.delivery_deadline && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Deadline</span>
                  <span className="font-medium">{formatDate(rfq.delivery_deadline)}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Currency</span>
                <span className="font-medium">{rfq.currency}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Users className="w-5 h-5" /> Suppliers ({rfq.suppliers?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {rfq.suppliers?.length > 0 ? (
                <div className="space-y-2">
                  {rfq.suppliers.map((s) => (
                    <div key={s.id} className="flex items-center justify-between text-sm p-2 rounded-lg bg-muted">
                      <span className="font-medium">{s.supplier_id.slice(0, 8)}...</span>
                      <Badge className={getStatusColor(s.status)} >{s.status}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No suppliers assigned yet</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
