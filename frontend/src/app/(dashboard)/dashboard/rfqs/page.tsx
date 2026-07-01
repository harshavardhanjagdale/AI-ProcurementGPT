"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { rfqService } from "@/services/rfq.service";
import { formatDate, formatCurrency, getStatusColor } from "@/lib/utils";
import { Plus, Search, FileText, ArrowRight } from "lucide-react";
import type { RFQ } from "@/types";

export default function RFQsPage() {
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    rfqService.list({ limit: 50 }).then((data) => {
      setRfqs(data.items || data as any);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const filtered = rfqs.filter(
    (r) =>
      r.title.toLowerCase().includes(search.toLowerCase()) ||
      r.rfq_number.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">RFQ Management</h1>
          <p className="text-muted-foreground mt-1">Track and manage requests for quotation</p>
        </div>
        <Link href="/dashboard/rfqs/new">
          <Button>
            <Plus className="w-4 h-4 mr-2" /> New RFQ (AI Chat)
          </Button>
        </Link>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input className="pl-9" placeholder="Search RFQs..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-white border animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((rfq) => (
            <Link key={rfq.id} href={`/dashboard/rfqs/${rfq.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer mb-3">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <FileText className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{rfq.title}</h3>
                          <Badge className={getStatusColor(rfq.status)}>
                            {rfq.status.replace(/_/g, " ")}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                          <span className="font-mono">{rfq.rfq_number}</span>
                          <span>{rfq.items?.length || 0} items</span>
                          {rfq.budget_max && <span>Budget: {formatCurrency(rfq.budget_max, rfq.currency)}</span>}
                          <span>{formatDate(rfq.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No RFQs yet</p>
          <p className="text-sm mt-1">Start by chatting with our AI to create one</p>
        </div>
      )}
    </div>
  );
}
