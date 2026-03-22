const notification = {
  title: 'Notifications',
  description: 'Stay on top of system, workspace, and app updates.',
  actions: {
    markAllRead: 'Mark all as read',
    markRead: 'Mark as read',
    archive: 'Archive',
    refresh: 'Refresh',
    loadMore: 'Load more',
  },
  search: {
    placeholder: 'Search notifications...',
  },
  filters: {
    button: 'Filter',
    status: {
      label: 'Status',
      all: 'All',
      unread: 'Unread',
      read: 'Read',
      archived: 'Archived',
    },
    severity: {
      label: 'Severity',
      all: 'All',
      info: 'Info',
      warning: 'Warning',
      error: 'Error',
      success: 'Success',
    },
    type: {
      label: 'Type',
      all: 'All',
      system: 'System',
      message: 'Message',
      alert: 'Alert',
      reminder: 'Reminder',
      custom: 'Custom',
    },
  },
  list: {
    title: 'Notification list',
    description: 'Review notification details and update their status.',
    loading: 'Loading notifications...',
    loadingMore: 'Loading more...',
    empty: 'No notifications yet',
    summary: 'Showing {{filtered}} of {{total}} notifications',
    table: {
      id: 'ID',
      title: 'Title',
      type: 'Type',
      severity: 'Severity',
      status: 'Status',
      createdAt: 'Created',
      updatedAt: 'Updated',
      actions: 'Actions',
    },
  },
  pagination: {
    prev: 'Previous',
    next: 'Next',
  },
  item: {
    status: {
      unread: 'Unread',
      read: 'Read',
      archived: 'Archived',
    },
    type: {
      system: 'System',
      message: 'Message',
      alert: 'Alert',
      reminder: 'Reminder',
      custom: 'Custom',
    },
  },
}

export default notification
