const chat = {
  dateGroups: {
    today: '今天',
    yesterday: '昨天',
    lastThreeDays: '最近3天',
    lastWeek: '最近一周',
    loadMore: '加载更多',
    loading: '加载中...',
    rename: '重命名',
    delete: '删除',
    archive: '归档',
    unarchive: '恢复',
  },
  errors: {
    loadFailed: '加载对话工作台失败',
  },
  custom: '定制',
  upgradeTip: {
    prefix: '升级您的计划以',
    suffix: '定制您的品牌。',
  },
  webapp: {
    title: '定制 WebApp 品牌',
    removeBrand: '移除 Powered by Soit',
    changeLogo: '更改 Powered by Brand 图片',
    changeLogoTip: 'SVG 或 PNG 格式，最小尺寸为 40x40px',
  },
  app: {
    title: '定制 Agent 对话头部品牌',
    changeLogoTip: 'SVG 或 PNG 格式，最小尺寸为 80x80px',
  },
  upload: '上传',
  uploading: '上传中',
  uploadedFail: '图片上传失败，请重新上传。',
  change: '更改',
  apply: '应用',
  restore: '恢复默认',
  customize: {
    contactUs: '联系我们',
    prefix: '如需在 Agent 对话工作台内自定义品牌图标，请',
    suffix: '升级至企业版。',
  },
  sidebar: {
    newChat: '新建对话',
    search: '输入搜索...',
    noConversations: '暂无对话',
    defaultTitle: '新对话',
    untitled: '未命名对话',
    deleteConfirmTitle: '确认删除对话？',
    deleteConfirmDescription: '删除后将无法恢复：“{{name}}”。',
    toast: {
      renameError: '重命名会话失败',
      deleteSuccess: '会话已删除',
      deleteError: '删除会话失败',
    },
    filter: {
      label: '筛选',
      all: '全部',
      active: '进行中',
      archived: '已归档',
    },
  },
  header: {
    defaultTitle: '新对话',
    share: '分享对话',
    shareCopied: '分享链接已复制',
    shareCopyFailed: '复制分享链接失败',
    shareEmpty: '开始对话后才能分享',
    refresh: '刷新对话',
    info: '对话信息',
  },
  thread: {
    scrollToBottom: '滚动到底部',
    assistant: {
      title: 'SOIT AI 助手',
      description: '您的智能助手，随时为您提供帮助和创意',
      disclaimer: 'SOIT AI 助手 | 智能生成内容 · 请遵守使用规范',
      capabilities: {
        multimodal: '多模态能力',
        codeGeneration: '代码生成',
        webSearch: '网络搜索'
      },
      suggestions: {
        title: '您可以尝试以下对话',
        items: {
          reactComponent: {
            title: '帮我编写一个简单的React组件',
            prompt: '帮我编写一个简单的React组件，用于显示用户资料卡片，包含头像、用户名、简介和关注按钮'
          },
          imageDescription: {
            title: '描述一下这张图片',
            prompt: '描述一下这张图片的内容和主题'
          },
          aiResearch: {
            title: '查找关于人工智能的最新进展',
            prompt: '查找关于人工智能的最新进展和应用'
          },
          creativeWriting: {
            title: '创意写作：未来科技',
            prompt: '请帮我写一篇关于未来科技如何改变人类生活的短文'
          }
        }
      }
    },
    composer: {
      placeholder: '向当前 Agent 发送消息...',
      tabCompletion: '按',
      tab: 'Tab',
      complete: '补全',
      editPrevious: '编辑上条消息',
      deepThinking: '深度思考',
      webSearch: '网络搜索',
      codeMode: '代码模式',
      multimodalHint: 'SOIT AI 助手 | 智能生成内容 · 请遵守使用规范',
      send: '发送消息',
      cancel: '取消生成',
      tooltips: {
        deepThinking: '启用深度思考模式，生成更详细的回答',
        webSearch: '允许AI助手搜索互联网获取最新信息',
        codeMode: '优化代码生成和解释能力'
      }
    },
    userLabel: '您',
    run: {
      viewRun: '查看运行详情',
      tokens: 'Tokens：提示 {{prompt}} · 补全 {{completion}} · 总计 {{total}}',
      budget: '预算：{{status}} · {{reason}}',
      budgetOk: '未超限',
      budgetExceeded: '已超限',
      cost: '成本：{{cost}}',
      finishReasonLabel: '结束原因',
      finishReasons: {
        stop: '正常结束',
        length: '达到长度限制',
        content_filter: '内容过滤',
        null: '—',
        _default: '其他',
      },
    },
    citations: {
      title: '引用来源',
      empty: '暂无引用',
      source: '来源',
      knowledge: '知识库',
    },
  },
}

export default chat
