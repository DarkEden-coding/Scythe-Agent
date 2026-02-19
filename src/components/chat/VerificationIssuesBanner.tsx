import { AlertTriangle } from 'lucide-react';
import type { VerificationIssues } from '@/types';
import { cn } from '@/utils/cn';

interface VerificationIssuesBannerProps {
  readonly issues: VerificationIssues;
  readonly isActive?: boolean;
}

export function VerificationIssuesBanner({ issues, isActive }: VerificationIssuesBannerProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 px-4 py-2.5 rounded-xl border',
        'bg-amber-500/5 border-amber-500/20 text-gray-300',
      )}
    >
      <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500/80" />
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm">{issues.summary}</span>
        {isActive && (
          <span className="text-xs text-gray-500">Asking agent to verify and fix.</span>
        )}
      </div>
    </div>
  );
}
