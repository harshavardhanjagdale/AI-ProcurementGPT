'use client';

import { useEffect, useState } from 'react';
import { Clock, Zap, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { workflowService, type WorkflowEvent } from '@/services/workflow.service';

interface EventTimelineProps {
  sessionId: string | null;
}

export function EventTimeline({ sessionId }: EventTimelineProps) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setEvents([]);
      return;
    }
    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const loadEvents = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const data = await workflowService.getEvents(sessionId);
      setEvents(data.events);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
      case 'step_completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
      default:
        return <Zap className="w-3.5 h-3.5 text-blue-500" />;
    }
  };

  if (!sessionId) return null;

  return (
    <div className="border-t border-gray-200 bg-gray-50 max-h-48 overflow-y-auto">
      <div className="px-4 py-2 border-b border-gray-200 bg-white sticky top-0">
        <h4 className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          Timeline
        </h4>
      </div>
      <div className="px-4 py-2 space-y-2">
        {events.length === 0 && !loading && (
          <p className="text-xs text-gray-400 text-center py-2">No events yet</p>
        )}
        {events.map((event) => (
          <div key={event.id} className="flex items-start gap-2">
            <div className="mt-0.5">{getEventIcon(event.event_type)}</div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-800 truncate">{event.title}</p>
              <div className="flex items-center gap-2">
                {event.agent && (
                  <span className="text-[10px] text-gray-500">{event.agent}</span>
                )}
                <span className="text-[10px] text-gray-400">
                  {new Date(event.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
