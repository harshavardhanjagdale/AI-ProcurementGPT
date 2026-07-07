'use client';

import { WorkspaceView } from '@/components/workspace/WorkspaceView';

// The AI Chat tab hosts the full procurement workspace inside the dashboard shell.
// The dashboard layout wraps children in `<main className="p-8">` below a 4rem header;
// `-m-8` cancels that padding and `h-[calc(100vh-4rem)]` fills the area edge-to-edge.
export default function AiChatPage() {
  return (
    <div className="-m-8 h-[calc(100vh-4rem)] overflow-hidden">
      <WorkspaceView embedded />
    </div>
  );
}
