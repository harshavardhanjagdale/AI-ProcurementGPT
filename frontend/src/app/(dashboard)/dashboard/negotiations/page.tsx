"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { negotiationService } from "@/services/negotiation.service";
import { formatCurrency, getStatusColor } from "@/lib/utils";
import { Handshake, TrendingDown, ArrowRight, Check, X } from "lucide-react";
import type { Negotiation } from "@/types";

export default function NegotiationsPage() {
  const [negotiations, setNegotiations] = useState<Negotiation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadNegotiations(); }, []);

  async function loadNegotiations() {
    setLoading(true);
    try {
      const data = await negotiationService.list();
      setNegotiations(data.items || data as any);
    } catch { }
    setLoading(false);
  }

  async function handleAccept(id: string) {
    await negotiationService.accept(id);
    loadNegotiations();
  }

  async function handleReject(id: string) {
    await negotiationService.reject(id);
    loadNegotiations();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Handshake className="w-6 h-6 text-primary" /> Negotiations
        </h1>
        <p className="text-muted-foreground mt-1">AI-powered price negotiations with suppliers</p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      ) : negotiations.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {negotiations.map((neg) => {
            const savings = neg.original_price - (neg.negotiated_price || neg.target_price);
            const savingsPercent = ((savings / neg.original_price) * 100).toFixed(1);
            return (
              <Card key={neg.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Badge className={getStatusColor(neg.status)}>{neg.status}</Badge>
                      <span className="text-xs text-muted-foreground">Round {neg.round_number}</span>
                    </div>
                    {savings > 0 && (
                      <div className="flex items-center gap-1 text-green-600 text-sm font-medium">
                        <TrendingDown className="w-4 h-4" />
                        {savingsPercent}% saved
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between gap-2 mb-4">
                    <div className="text-center">
                      <p className="text-xs text-muted-foreground mb-1">Original</p>
                      <p className="font-semibold text-lg">{formatCurrency(neg.original_price)}</p>
                    </div>
                    <ArrowRight className="w-5 h-5 text-muted-foreground" />
                    <div className="text-center">
                      <p className="text-xs text-muted-foreground mb-1">Target</p>
                      <p className="font-semibold text-lg text-primary">{formatCurrency(neg.target_price)}</p>
                    </div>
                    {neg.negotiated_price && (
                      <>
                        <ArrowRight className="w-5 h-5 text-muted-foreground" />
                        <div className="text-center">
                          <p className="text-xs text-muted-foreground mb-1">Final</p>
                          <p className="font-semibold text-lg text-green-600">{formatCurrency(neg.negotiated_price)}</p>
                        </div>
                      </>
                    )}
                  </div>

                  {neg.status === "counter_received" && (
                    <div className="flex gap-2 pt-3 border-t">
                      <Button size="sm" className="flex-1" onClick={() => handleAccept(neg.id)}>
                        <Check className="w-3 h-3 mr-1" /> Accept
                      </Button>
                      <Button size="sm" variant="outline" className="flex-1" onClick={() => handleReject(neg.id)}>
                        <X className="w-3 h-3 mr-1" /> Reject
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <Handshake className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No negotiations yet</p>
          <p className="text-sm mt-1">AI will initiate negotiations when quotes are above target</p>
        </div>
      )}
    </div>
  );
}
