import { cn } from '@/utils/cn';

interface DiffPreviewProps {
  readonly diff?: string;
  readonly action: string;
}

export function DiffPreview({ diff, action }: DiffPreviewProps) {
  if (!diff) return null;

  const lines = diff.split('\n');

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700/30 bg-gray-950/70 text-[11px] font-mono leading-relaxed">
      <div className="max-h-[220px] overflow-y-auto">
        {lines.map((line, i) => {
          let bgClass = '';
          let textClass: string;
          if (line.startsWith('+')) {
            bgClass = 'bg-emerald-500/8';
            textClass = 'text-emerald-300/90';
          } else if (line.startsWith('-')) {
            bgClass = 'bg-red-500/8';
            textClass = 'text-red-300/80';
          } else if (line.startsWith('@@')) {
            bgClass = 'bg-aqua-500/5';
            textClass = 'text-aqua-400/60';
          } else {
            textClass = action === 'create' ? 'text-emerald-300/70' : 'text-gray-500';
            if (action === 'create') bgClass = 'bg-emerald-500/5';
          }

          let prefix: string;
          if (line.startsWith('+')) prefix = '+';
          else if (line.startsWith('-')) prefix = '-';
          else if (line.startsWith('@@')) prefix = '@';
          else prefix = ' ';
          const content = line.startsWith('+') || line.startsWith('-') ? line.slice(1) : line;

          return (
            <div key={`${i}-${line.slice(0, 30)}`} className={cn('flex', bgClass)}>
              <span className={cn('w-5 shrink-0 text-center select-none opacity-50', textClass)}>
                {prefix === ' ' ? '' : prefix}
              </span>
              <span className={cn('flex-1 px-2 py-px whitespace-pre', textClass)}>
                {content}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
