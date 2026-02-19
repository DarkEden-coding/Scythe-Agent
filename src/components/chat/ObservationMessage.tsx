import { useState } from 'react';
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';
import type { ObservationData } from '@/types';

interface ObservationMessageProps {
  readonly observation: ObservationData;
}

export function ObservationMessage({ observation }: ObservationMessageProps) {
  const [expanded, setExpanded] = useState(false);

  if (!observation.hasObservations || !observation.content) return null;

  const headerLabel = `Memory Observation${observation.generation !== undefined ? ` · Gen ${observation.generation}` : ''}${observation.tokenCount !== undefined ? ` · ${observation.tokenCount.toLocaleString()} tokens` : ''}`;

  const timestamp = observation.timestamp ? new Date(observation.timestamp) : null;
  const timeStr = timestamp
    ? timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div className="my-3 mx-2">
      <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 overflow-hidden">
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-violet-500/10 transition-colors"
        >
          <Brain className="w-3.5 h-3.5 text-violet-400 shrink-0" />
          <span className="text-xs font-medium text-violet-300 flex-1">{headerLabel}</span>
          {timeStr && (
            <span className="text-xs text-violet-500 mr-1">{timeStr}</span>
          )}
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-violet-500" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-violet-500" />
          )}
        </button>

        {/* Expanded content */}
        {expanded && (
          <div className="border-t border-violet-500/15 px-4 py-3 space-y-3">
            {/* Main content */}
            <pre className="whitespace-pre-wrap text-xs text-gray-300 font-mono leading-relaxed">
              {observation.content}
            </pre>

            {/* Current task */}
            {observation.currentTask && (
              <div className="rounded-lg bg-violet-500/10 border border-violet-500/20 px-3 py-2">
                <p className="text-xs font-medium text-violet-400 mb-0.5">Current Task</p>
                <p className="text-xs text-gray-300">{observation.currentTask}</p>
              </div>
            )}

            {/* Suggested response */}
            {observation.suggestedResponse && (
              <div className="rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-3 py-2">
                <p className="text-xs font-medium text-indigo-400 mb-0.5">Continuation Hint</p>
                <p className="text-xs text-gray-300">{observation.suggestedResponse}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
