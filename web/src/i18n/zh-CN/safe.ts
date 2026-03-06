const safe = {
  custom: '自定义',
  upgradeTip: {
    prefix: '升级你的计划以',
    suffix: '自定义你的品牌。',
  },
  center: {
    breadcrumb: {
      root: '全部收件箱',
    },
    title: '安全中心',
    refresh: '刷新数据',
  },
  sidebar: {
    title: '安全中心',
    searchPlaceholder: '搜索安全设置...',
    sections: {
      main: '安全中心',
      management: '安全管理',
    },
    items: {
      guardrail: {
        label: '安全护栏',
        description: '配置内容过滤和安全防护规则。',
      },
      alerts: {
        label: '安全事件',
        description: '查看和处理安全事件提醒。',
      },
      sensitive: {
        label: '敏感词管理',
        description: '管理敏感词库和处理规则。',
      },
      access: {
        label: '访问控制',
        description: '管理用户访问权限和身份验证。',
      },
      user: {
        label: '用户行为',
        description: '监控用户行为和异常操作。',
      },
      privacy: {
        label: '隐私保护',
        description: '保护用户隐私和敏感信息。',
      },
      audit: {
        label: '审计日志',
        description: '查看和分析系统操作日志。',
      },
      settings: {
        label: '安全设置',
        description: '配置系统安全选项。',
      },
    },
    score: {
      title: '安全评分',
      updatedAt: '更新于: {{time}}',
      guardrailStatus: '护栏状态',
      systemStatus: '系统状态',
      report: '安全报告',
      export: '导出数据',
    },
  },

  auditLogs: {
    header: {
      title: '审计日志',
      description: '查看和分析系统操作日志',
    },
    card: {
      title: '审计日志',
      description: '记录所有系统操作和安全相关事件',
    },
    searchPlaceholder: '搜索日志...',
    filters: {
      action: {
        label: '操作类型',
        all: '全部操作',
        login: '登录',
        create: '创建',
        update: '更新',
        delete: '删除',
        permission: '权限',
        backup: '备份',
      },
      status: {
        label: '状态',
        all: '全部状态',
        success: '成功',
        failure: '失败',
        warning: '警告',
      },
      time: {
        label: '时间范围',
        all: '全部时间',
        today: '今天',
        yesterday: '昨天',
        week: '本周',
      },
    },
    table: {
      time: '时间',
      user: '用户',
      action: '操作',
      resource: '资源',
      details: '详情',
      ip: 'IP地址',
      status: '状态',
      operations: '操作',
    },
    empty: '没有找到符合条件的日志记录',
    summary: '显示 {{filtered}} 条日志，共 {{total}} 条',
    pagination: {
      prev: '上一页',
      next: '下一页',
    },
    counts: {
      success: '成功: {{count}}',
      failure: '失败: {{count}}',
      warning: '警告: {{count}}',
    },
    actions: {
      refresh: '刷新',
      export: '导出',
      exportFiltered: '导出筛选结果',
    },
    action: {
      login: '登录',
      create: '创建',
      update: '更新',
      delete: '删除',
      permission: '权限',
      backup: '备份',
    },
    status: {
      success: '成功',
      failure: '失败',
      warning: '警告',
    },
    charts: {
      actionDistribution: '操作类型分布',
      actionChart: '操作类型分布图表',
      userActivity: '用户活动',
      userChart: '用户活动图表',
      timeDistribution: '时间分布',
      timeChart: '时间分布图表',
      placeholderNote: '（此处可集成实际的图表组件）',
    },
  },
  accessControl: {
    header: {
      title: '访问控制',
      description: '管理API访问权限和调用限制',
    },
    actions: {
      refresh: '刷新',
      reset: '重置默认值',
      save: '保存设置',
    },
    apiKeys: {
      title: 'API密钥管理',
      description: '创建和管理API密钥，控制对系统的访问权限',
      table: {
        name: '名称',
        key: '密钥',
        status: '状态',
        permissions: '权限',
        created: '创建时间',
        lastUsed: '最后使用',
        actions: '操作',
      },
      status: {
        active: '活跃',
        inactive: '停用',
      },
      permissions: {
        read: '读取',
        write: '写入',
        admin: '管理',
        readOnly: '只读',
        readWrite: '读写',
      },
      fields: {
        name: 'API密钥名称',
        permission: '权限',
      },
      placeholders: {
        name: '输入名称...',
      },
      actions: {
        create: '创建密钥',
      },
    },
    ipWhitelist: {
      title: 'IP白名单',
      description: '限制只允许特定IP地址访问API',
      table: {
        ip: 'IP地址/范围',
        description: '描述',
        created: '添加时间',
        actions: '操作',
      },
      fields: {
        ip: 'IP地址/范围',
        description: '描述',
      },
      placeholders: {
        ip: '例如: 192.168.1.1 或 10.0.0.0/24',
        description: '描述...',
      },
      actions: {
        add: '添加',
      },
    },
    settings: {
      title: '访问控制设置',
      description: '配置全局访问控制策略',
      apiKeyAuth: '启用API密钥验证',
      ipAllowlist: '启用IP白名单',
      rateLimit: '启用速率限制',
      userAuth: '启用用户身份验证',
    },
  },

  securityAlerts: {
    header: {
      title: '安全事件监控',
      description: '监控和管理系统安全事件',
    },
    tabs: {
      all: '全部事件',
      high: '高风险',
      pending: '待处理',
      resolved: '已处理',
    },
    table: {
      description: '描述',
      severity: '风险等级',
      status: '状态',
      user: '用户',
      time: '时间',
      actions: '操作',
    },
    empty: '没有找到符合条件的安全事件',
    severity: {
      high: '高风险',
      medium: '中风险',
      low: '低风险',
      unknown: '未知',
    },
    status: {
      resolved: '已处理',
      pending: '待处理',
    },
    actions: {
      viewDetails: '查看详情',
      exportReport: '导出报告',
      refresh: '刷新',
    },
    summary: {
      title: '安全事件统计',
      description: '过去30天内的安全事件统计数据',
      highRisk: '高风险事件',
      pending: '待处理事件',
      affectedUsers: '受影响用户',
    },
  },
}
export default safe
