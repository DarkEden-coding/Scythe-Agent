import { useEffect, useState } from 'react';
import { Brain } from 'lucide-react';
import { cn } from '@/utils/cn';

export type ObservationStatus = 'idle' | 'observing' | 'reflecting' | 'done';

interface ObservationStatusIndicatorProps {
  readonly status: ObservationStatus;
}

export function ObservationStatusIndicator({ status }: ObservationStatusIndicatorProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (status === 'idle') {
      setVisible(false);
      return;
    }
    setVisible(true);
    if (status === 'done') {
      const timer = setTimeout(() => setVisible(false), 2500);
      return () => clearTimeout(timer);
    }
  }, [status]);

  if (!visible) return null;

  const label =
    status === 'observing'
      ? 'Observing...'
      : status === 'reflecting'
        ? 'Reflecting...'
        : 'Memory updated';

  const isPulsing = status === 'observing' || status === 'reflecting';

  return (
    <div
      className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-all',
        status === 'done'
          ? 'text-violet-400 bg-violet-500/10'
          : 'text-violet-300 bg-violet-500/15 border border-violet-500/20',
      )}
    >
      <Brain
        className={cn('w-3 h-3 text-violet-400', isPulsing && 'animate-pulse')}
      />
      <span>{label}</span>
    </div>
  );
}
