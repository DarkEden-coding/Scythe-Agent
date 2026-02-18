import { useEffect } from 'react';
import { Trash2 } from 'lucide-react';
import { Modal } from '@/components/Modal';

interface DeleteChatConfirmModalProps {
  readonly visible: boolean;
  readonly chatTitle: string;
  readonly onClose: () => void;
  readonly onConfirm: () => void | Promise<void>;
  readonly loading?: boolean;
}

export function DeleteChatConfirmModal({
  visible,
  chatTitle,
  onClose,
  onConfirm,
  loading = false,
}: DeleteChatConfirmModalProps) {
  const handleConfirm = async () => {
    await onConfirm();
    onClose();
  };

  useEffect(() => {
    if (!visible || loading) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleConfirm();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visible, loading, onConfirm, onClose]);

  return (
    <Modal
      visible={visible}
      onClose={onClose}
      title="Delete chat"
      subtitle={chatTitle ? `"${chatTitle}" will be permanently removed.` : 'This chat will be permanently removed.'}
      icon={<Trash2 className="w-5 h-5 text-red-400" />}
      maxWidth="max-w-sm"
      footer={
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700/60 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            {loading ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      }
    >
      {null}
    </Modal>
  );
}
