import { CheckSquare } from 'lucide-react';
import type { TodoItem } from '@/types';
import { cn } from '@/utils/cn';

interface TodoListProps {
  readonly todos: TodoItem[];
}

export function TodoList({ todos }: TodoListProps) {
  const sorted = [...todos].sort(
    (a, b) => a.sortOrder - b.sortOrder || a.timestamp.getTime() - b.timestamp.getTime(),
  );

  return (
    <div className="w-fit max-w-full p-3 rounded-lg bg-gray-800/50 border border-gray-700/30 space-y-1">
      <div className="flex items-center gap-2 mb-2">
        <CheckSquare className="w-3.5 h-3.5 text-aqua-400/80" />
        <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
          Tasks
        </span>
      </div>
      <ul className="space-y-1.5">
        {sorted.map((todo) => (
          <li
            key={todo.id}
            className="flex items-start gap-2 text-[11px] text-gray-300"
          >
            <input
              type="checkbox"
              checked={todo.status === 'completed'}
              readOnly
              disabled
              className="mt-0.5 h-3 w-3 shrink-0 rounded border-gray-600 bg-gray-800 accent-aqua-400 cursor-default"
            />
            <span
              className={cn(
                'flex-1 min-w-0',
                todo.status === 'completed' && 'line-through text-gray-500',
              )}
            >
              {todo.content}
            </span>
            {todo.status !== 'completed' && (
              <span
                className={cn(
                  'shrink-0 px-1.5 py-0.5 rounded text-[9px] font-medium',
                  todo.status === 'in_progress'
                    ? 'bg-amber-500/20 text-amber-400'
                    : 'bg-gray-700/50 text-gray-500',
                )}
              >
                {todo.status === 'in_progress' ? 'In Progress' : 'Pending'}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
