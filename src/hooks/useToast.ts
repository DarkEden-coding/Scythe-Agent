import { useState, useCallback } from 'react';

export function useToast() {
  const [showNotification, setShowNotification] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState('');

  const showToast = useCallback((message: string) => {
    setNotificationMessage(message);
    setShowNotification(true);
    setTimeout(() => setShowNotification(false), 3000);
  }, []);

  return { showNotification, notificationMessage, showToast };
}
