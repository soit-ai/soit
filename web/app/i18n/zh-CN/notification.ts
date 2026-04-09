const notification = {
  title: '通知',
  description: '查看系统、工作区与 Agent 的最新动态。',
  actions: {
    markAllRead: '全部标为已读',
    markRead: '标记为已读',
    archive: '归档',
    refresh: '刷新',
    loadMore: '加载更多',
  },
  search: {
    placeholder: '搜索通知...',
  },
  filters: {
    button: '筛选',
    status: {
      label: '状态',
      all: '全部',
      unread: '未读',
      read: '已读',
      archived: '已归档',
    },
    severity: {
      label: '级别',
      all: '全部',
      info: '信息',
      warning: '警告',
      error: '错误',
      success: '成功',
    },
    type: {
      label: '类型',
      all: '全部',
      system: '系统',
      message: '消息',
      alert: '告警',
      reminder: '提醒',
      custom: '自定义',
    },
  },
  list: {
    title: '通知列表',
    description: '查看所有通知及其处理状态。',
    loading: '加载通知中...',
    loadingMore: '加载更多中...',
    empty: '暂无通知',
    summary: '显示 {{filtered}} 条通知（共 {{total}} 条）',
    table: {
      id: 'ID',
      title: '标题',
      type: '类型',
      severity: '级别',
      status: '状态',
      createdAt: '提交时间',
      updatedAt: '更新时间',
      actions: '操作',
    },
  },
  pagination: {
    prev: '上一页',
    next: '下一页',
  },
  item: {
    status: {
      unread: '未读',
      read: '已读',
      archived: '已归档',
    },
    type: {
      system: '系统',
      message: '消息',
      alert: '告警',
      reminder: '提醒',
      custom: '自定义',
    },
  },
}

export default notification
