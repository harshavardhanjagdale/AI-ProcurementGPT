"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { purchaseOrderService } from "@/services/purchase-order.service";
import { formatDate, formatCurrency, getStatusColor } from "@/lib/utils";
import { ShoppingCart, Download, Send, CheckCircle, FileText } from "lucide-react";
import type { PurchaseOrder } from "@/types";

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadOrders(); }, []);

  async function loadOrders() {
    setLoading(true);
    try {
      const data = await purchaseOrderService.list({ limit: 50 });
      setOrders(data.items || data as any);
    } catch { }
    setLoading(false);
  }

  async function handleApprove(id: string) {
    await purchaseOrderService.approve(id);
    loadOrders();
  }

  async function handleSend(id: string) {
    await purchaseOrderService.send(id);
    loadOrders();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShoppingCart className="w-6 h-6 text-primary" /> Purchase Orders
        </h1>
        <p className="text-muted-foreground mt-1">Manage and track purchase orders</p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      ) : orders.length > 0 ? (
        <div className="space-y-4">
          {orders.map((po) => (
            <Card key={po.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-emerald-50 flex items-center justify-center">
                      <FileText className="w-6 h-6 text-emerald-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-lg">{po.po_number}</h3>
                        <Badge className={getStatusColor(po.status)}>{po.status}</Badge>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                        <span>Amount: <strong>{formatCurrency(po.total_amount, po.currency)}</strong></span>
                        {po.delivery_date && <span>Delivery: {formatDate(po.delivery_date)}</span>}
                        <span>Created: {formatDate(po.created_at)}</span>
                      </div>
                      {po.payment_terms && (
                        <p className="text-xs text-muted-foreground mt-1">Payment: {po.payment_terms}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {po.status === "draft" && (
                      <Button size="sm" onClick={() => handleApprove(po.id)}>
                        <CheckCircle className="w-4 h-4 mr-1" /> Approve
                      </Button>
                    )}
                    {po.status === "approved" && (
                      <Button size="sm" onClick={() => handleSend(po.id)}>
                        <Send className="w-4 h-4 mr-1" /> Send
                      </Button>
                    )}
                    {po.pdf_path && (
                      <Button size="sm" variant="outline" asChild>
                        <a href={purchaseOrderService.getDownloadUrl(po.id)} target="_blank" rel="noopener noreferrer">
                          <Download className="w-4 h-4 mr-1" /> PDF
                        </a>
                      </Button>
                    )}
                  </div>
                </div>

                {po.items?.length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <div className="grid grid-cols-4 gap-2 text-xs text-muted-foreground mb-2">
                      <span>Product</span><span>Qty</span><span>Unit Price</span><span>Total</span>
                    </div>
                    {po.items.slice(0, 3).map((item, idx) => (
                      <div key={idx} className="grid grid-cols-4 gap-2 text-sm py-1">
                        <span className="truncate">{item.product_name}</span>
                        <span>{item.quantity}</span>
                        <span>{formatCurrency(item.unit_price, po.currency)}</span>
                        <span className="font-medium">{formatCurrency(item.total_price, po.currency)}</span>
                      </div>
                    ))}
                    {po.items.length > 3 && (
                      <p className="text-xs text-muted-foreground mt-1">+{po.items.length - 3} more items</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <ShoppingCart className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No purchase orders yet</p>
          <p className="text-sm mt-1">POs are generated after accepting quotations</p>
        </div>
      )}
    </div>
  );
}
