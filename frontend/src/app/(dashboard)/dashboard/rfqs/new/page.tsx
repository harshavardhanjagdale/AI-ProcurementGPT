"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { chatService } from "@/services/chat.service";
import { Bot, Send, User, Loader2, Sparkles } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, unknown>;
}

const SUGGESTIONS = [
  "I need to procure 500 units of industrial ball bearings (6205-2RS) for our manufacturing line",
  "Request quotes for 100 ergonomic office chairs with lumbar support for our new office",
  "We need 2000 meters of CAT6 ethernet cables and 50 network switches",
  "Procure 200 laptops (Intel i7, 16GB RAM, 512GB SSD) for new hires",
];

export default function NewRFQPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [workflowId, setWorkflowId] = useState<string | undefined>();
  const [rfqId, setRfqId] = useState<string | undefined>();
  const [awaitingDecision, setAwaitingDecision] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text?: string) {
    const msg = text || input;
    if (!msg.trim() || loading) return;

    const userMsg: Message = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await chatService.sendMessage(msg, rfqId, workflowId);
      const assistantMsg: Message = {
        role: "assistant",
        content: response.response || response.message || JSON.stringify(response),
        metadata: response,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (response.workflow_id) setWorkflowId(response.workflow_id);
      if (response.rfq_id) setRfqId(response.rfq_id);
      if (response.awaiting_decision) setAwaitingDecision(true);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.response?.data?.detail || err.message}` },
      ]);
    }
    setLoading(false);
  }

  async function handleDecision(decision: string) {
    if (!workflowId) return;
    setLoading(true);
    setAwaitingDecision(false);
    setMessages((prev) => [...prev, { role: "user", content: `Decision: ${decision}` }]);

    try {
      const response = await chatService.submitDecision(workflowId, decision);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.response || response.message || JSON.stringify(response) },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.response?.data?.detail || err.message}` },
      ]);
    }
    setLoading(false);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-primary" />
          AI Procurement Assistant
        </h1>
        <p className="text-muted-foreground mt-1">
          Describe what you need to procure in natural language
        </p>
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardContent className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Start a Procurement Request</h3>
              <p className="text-muted-foreground text-sm max-w-md mb-6">
                Tell me what you need to procure and I&apos;ll handle the entire RFQ process -
                from vendor selection to quotation analysis.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="text-left p-3 rounded-lg border hover:border-primary/30 hover:bg-primary/5 transition-all text-sm text-muted-foreground"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}
              <div
                className={`max-w-[70%] rounded-xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="bg-muted rounded-xl px-4 py-3">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            </div>
          )}

          {awaitingDecision && !loading && (
            <div className="flex gap-2 ml-11">
              <Button size="sm" onClick={() => handleDecision("accept")}>Accept Best Quote</Button>
              <Button size="sm" variant="outline" onClick={() => handleDecision("negotiate")}>Negotiate</Button>
              <Button size="sm" variant="ghost" onClick={() => handleDecision("reject_all")}>Reject All</Button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        <div className="p-4 border-t">
          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe what you need to procure..."
              className="min-h-[44px] max-h-32 resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
            <Button onClick={() => sendMessage()} disabled={!input.trim() || loading} size="icon" className="h-11 w-11">
              <Send className="w-4 h-4" />
            </Button>
          </div>
          {workflowId && (
            <div className="mt-2 flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">Workflow: {workflowId.slice(0, 8)}...</Badge>
              {rfqId && <Badge className="text-xs bg-green-100 text-green-700">RFQ Created</Badge>}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
