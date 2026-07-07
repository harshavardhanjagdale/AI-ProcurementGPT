'use client';

import { useEffect, useState } from 'react';
import { Zap, CheckCircle2, AlertCircle, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';
import { workflowService, type WorkflowEvent } from '@/services/workflow.service';

interface EventTimelineProps {
  sessionId: string | null;
}

export function EventTimeline({ sessionId }: EventTimelineProps) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setEvents([]);
      return;
    }
    let active = true;
    const load = async () => {
      try {
        const data = await workflowService.getEvents(sessionId, 100);
        if (active) setEvents(data.events);
      } catch {
        // silent
      } finally {
        if (active) setLoaded(true);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [sessionId]);

  const iconFor = (type: string) => {
    switch (type) {
      case 'error':
        return { Icon: AlertCircle, wrap: 'bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400' };
      case 'email_received':
        return { Icon: Mail, wrap: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400' };
      case 'step_completed':
        return { Icon: CheckCircle2, wrap: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400' };
      default:
        return { Icon: Zap, wrap: 'bg-sky-100 text-sky-600 dark:bg-sky-950/60 dark:text-sky-400' };
    }
  };

  if (loaded && events.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-slate-400 dark:text-slate-500">
        No activity yet. Events will appear here as the workflow runs.
      </div>
    );
  }

  return (
    <div className="p-5">
      <ol className="relative">
        {events.map((event, i) => {
          const { Icon, wrap } = iconFor(event.event_type);
          const isLast = i === events.length - 1;
          return (
            <li key={event.id} className="relative flex gap-3 pb-5 animate-fade-in-up">
              {/* Connector rail */}
              {!isLast && (
                <span className="absolute left-[15px] top-8 bottom-0 w-px bg-slate-200 dark:bg-slate-700" />
              )}
              <div className={cn('relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center', wrap)}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0 pt-0.5">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-tight">
                  {event.title}
                </p>
                {event.description && (
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
                    {event.description}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  {event.agent && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                      {event.agent}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-400 dark:text-slate-500">
                    {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
