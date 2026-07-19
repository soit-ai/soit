const translation = {
  header: {
    githubLabel: 'GitHub 仓库',
    searchPlaceholder: '搜索模型、数据集、工作流...',
    apiKey: {
      label: 'API 密钥',
      title: 'API 密钥管理',
      view: '查看 API 密钥',
      docs: 'API 文档',
    },
    notifications: {
      label: '通知',
      title: '通知',
      markAllRead: '全部标为已读',
      loading: '加载通知中...',
      empty: '暂无通知',
      viewAll: '查看全部通知',
      items: {
        modelDeploy: {
          title: '模型部署完成',
          message: '您的自定义模型已成功部署并可以使用',
          time: '10 分钟前',
        },
        knowledgeWarning: {
          title: '知识库处理警告',
          message: '数据集「客户反馈」处理过程中发现异常数据',
          time: '1 小时前',
        },
        systemUpdate: {
          title: '系统更新通知',
          message: '系统将于今晚 22:00-23:00 进行维护更新',
          time: '3 小时前',
        },
        apiUsage: {
          title: 'API 额度提醒',
          message: '您的 API 调用额度已使用 80%，请考虑升级计划',
          time: '昨天',
        },
      },
    },
    help: {
      label: '帮助',
      title: '帮助与支持',
      docs: '文档中心',
      contact: '联系客服',
      about: '关于系统',
    },
    language: {
      label: '切换语言',
    },
    settings: {
      label: '设置',
    },
  },
  search: {
    title: '搜索工作区',
    description: '查找当前工作区中的 Agent、工作流、知识库、插件、模型、会话和运行记录。',
    inputLabel: '工作区搜索关键词',
    action: '搜索',
    filtersLabel: '资源类型筛选',
    resultSummary: '“{{query}}”的搜索结果：{{count}} 条',
    startHint: '输入至少两个字符开始搜索。',
    loading: '正在搜索工作区...',
    failed: '工作区搜索失败，请重试。',
    emptyTitle: '没有匹配的资源',
    emptyDescription: '请更换关键词，或清除资源类型筛选。',
    kinds: {
      all: '全部',
      agent: 'Agent',
      workflow: '工作流',
      knowledge: '知识库',
      plugin: '插件',
      model: '模型',
      thread: '会话',
      run: '运行',
    },
  },
}

export default translation
