const safe = {
  custom: 'Customization',
  upgradeTip: {
    prefix: 'Upgrade your plan to',
    suffix: 'customize your brand.',
  },
  center: {
    breadcrumb: {
      root: 'All Inboxes',
    },
    title: 'Safety Center',
    refresh: 'Refresh data',
  },
  sidebar: {
    title: 'Safety Center',
    searchPlaceholder: 'Search safety settings...',
    sections: {
      main: 'Safety Center',
      management: 'Safety Management',
    },
    items: {
      guardrail: {
        label: 'Safety Guardrail',
        description: 'Configure content filters and safety guardrails.',
      },
      alerts: {
        label: 'Security Alerts',
        description: 'Review and handle security notifications.',
      },
      sensitive: {
        label: 'Sensitive Words',
        description: 'Manage sensitive word lists and rules.',
      },
      access: {
        label: 'Access Control',
        description: 'Manage access permissions and authentication.',
      },
      user: {
        label: 'User Behavior',
        description: 'Monitor user behavior and anomalies.',
      },
      privacy: {
        label: 'Privacy Protection',
        description: 'Protect user privacy and sensitive data.',
      },
      audit: {
        label: 'Audit Logs',
        description: 'Review and analyze system audit logs.',
      },
      settings: {
        label: 'Security Settings',
        description: 'Configure system security options.',
      },
    },
    score: {
      title: 'Security score',
      updatedAt: 'Updated: {{time}}',
      guardrailStatus: 'Guardrail status',
      systemStatus: 'System status',
      report: 'Security report',
      export: 'Export data',
    },
  },

  auditLogs: {
    header: {
      title: 'Audit logs',
      description: 'Review and analyze system operations',
    },
    card: {
      title: 'Audit logs',
      description: 'Record all system operations and security events',
    },
    searchPlaceholder: 'Search logs...',
    filters: {
      action: {
        label: 'Action',
        all: 'All actions',
        login: 'Login',
        create: 'Create',
        update: 'Update',
        delete: 'Delete',
        permission: 'Permission',
        backup: 'Backup',
      },
      status: {
        label: 'Status',
        all: 'All statuses',
        success: 'Success',
        failure: 'Failure',
        warning: 'Warning',
      },
      time: {
        label: 'Time range',
        all: 'All time',
        today: 'Today',
        yesterday: 'Yesterday',
        week: 'This week',
      },
    },
    table: {
      time: 'Time',
      user: 'User',
      action: 'Action',
      resource: 'Resource',
      details: 'Details',
      ip: 'IP address',
      status: 'Status',
      operations: 'Actions',
    },
    empty: 'No logs found',
    summary: 'Showing {{filtered}} logs out of {{total}}',
    pagination: {
      prev: 'Previous',
      next: 'Next',
    },
    counts: {
      success: 'Success: {{count}}',
      failure: 'Failure: {{count}}',
      warning: 'Warning: {{count}}',
    },
    actions: {
      refresh: 'Refresh',
      export: 'Export',
      exportFiltered: 'Export filtered results',
    },
    action: {
      login: 'Login',
      create: 'Create',
      update: 'Update',
      delete: 'Delete',
      permission: 'Permission',
      backup: 'Backup',
    },
    status: {
      success: 'Success',
      failure: 'Failure',
      warning: 'Warning',
    },
    charts: {
      actionDistribution: 'Action distribution',
      actionChart: 'Action distribution chart',
      userActivity: 'User activity',
      userChart: 'User activity chart',
      timeDistribution: 'Time distribution',
      timeChart: 'Time distribution chart',
      placeholderNote: '(Chart component can be integrated here)',
    },
  },
  accessControl: {
    header: {
      title: 'Access control',
      description: 'Manage API access permissions and limits',
    },
    actions: {
      refresh: 'Refresh',
      reset: 'Reset defaults',
      save: 'Save settings',
    },
    apiKeys: {
      title: 'API key management',
      description: 'Create and manage API keys and access permissions',
      table: {
        name: 'Name',
        key: 'Key',
        status: 'Status',
        permissions: 'Permissions',
        created: 'Created',
        lastUsed: 'Last used',
        actions: 'Actions',
      },
      status: {
        active: 'Active',
        inactive: 'Inactive',
      },
      permissions: {
        read: 'Read',
        write: 'Write',
        admin: 'Admin',
        readOnly: 'Read only',
        readWrite: 'Read & write',
      },
      fields: {
        name: 'API key name',
        permission: 'Permission',
      },
      placeholders: {
        name: 'Enter name...',
      },
      actions: {
        create: 'Create key',
      },
    },
    ipWhitelist: {
      title: 'IP allowlist',
      description: 'Restrict API access to allowed IP ranges',
      table: {
        ip: 'IP / Range',
        description: 'Description',
        created: 'Added',
        actions: 'Actions',
      },
      fields: {
        ip: 'IP / Range',
        description: 'Description',
      },
      placeholders: {
        ip: 'e.g. 192.168.1.1 or 10.0.0.0/24',
        description: 'Description...',
      },
      actions: {
        add: 'Add',
      },
    },
    settings: {
      title: 'Access control settings',
      description: 'Configure global access control policies',
      apiKeyAuth: 'Enable API key authentication',
      ipAllowlist: 'Enable IP allowlist',
      rateLimit: 'Enable rate limiting',
      userAuth: 'Enable user authentication',
    },
  },

  securityAlerts: {
    header: {
      title: 'Security alerts',
      description: 'Monitor and manage system security events',
    },
    tabs: {
      all: 'All events',
      high: 'High risk',
      pending: 'Pending',
      resolved: 'Resolved',
    },
    table: {
      description: 'Description',
      severity: 'Severity',
      status: 'Status',
      user: 'User',
      time: 'Time',
      actions: 'Actions',
    },
    empty: 'No security events found',
    severity: {
      high: 'High risk',
      medium: 'Medium risk',
      low: 'Low risk',
      unknown: 'Unknown',
    },
    status: {
      resolved: 'Resolved',
      pending: 'Pending',
    },
    actions: {
      viewDetails: 'View details',
      exportReport: 'Export report',
      refresh: 'Refresh',
    },
    summary: {
      title: 'Security event summary',
      description: 'Security event statistics for the last 30 days',
      highRisk: 'High risk events',
      pending: 'Pending events',
      affectedUsers: 'Affected users',
    },
  },
}
export default safe
