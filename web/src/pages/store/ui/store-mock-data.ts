import type { StoreItemProps } from './store-item-card'
import type { FeaturedItemProps } from './store-featured'

// 生成模拟商店项目数据
export const mockStoreItems: StoreItemProps[] = [
  // 大模型
  {
    id: 'model-1',
    title: 'OpenAI 模型服务',
    description: '提供GPT-4、GPT-3.5等高性能大语言模型API接入',
    author: 'OpenAI',
    type: 'model',

    rating: 4.9,
    downloads: 25600,
    tags: ['GPT-4', 'GPT-3.5', 'API接入'],
    imageUrl: 'https://placehold.co/600x400/4338ca/white?text=OpenAI',
    isInstalled: true
  },
  {
    id: 'model-2',
    title: 'Anthropic Claude 模型服务',
    description: '提供Claude系列大语言模型API接入，支持长上下文对话',
    author: 'Anthropic',
    type: 'model',

    rating: 4.8,
    downloads: 18700,
    tags: ['Claude', '长上下文', 'API接入'],
    imageUrl: 'https://placehold.co/600x400/6366f1/white?text=Anthropic'
  },
  {
    id: 'model-3',
    title: '智谱AI模型服务',
    description: '提供GLM系列大语言模型API接入，支持中英双语对话',
    author: '智谱AI',
    type: 'model',

    rating: 4.7,
    downloads: 15200,
    tags: ['GLM', '中文优化', 'API接入'],
    imageUrl: 'https://placehold.co/600x400/4f46e5/white?text=智谱AI'
  },
  {
    id: 'model-4',
    title: '百度文心一言模型服务',
    description: '提供文心一言系列大语言模型API接入，支持多模态交互',
    author: '百度',
    type: 'model',

    rating: 4.6,
    downloads: 14300,
    tags: ['文心一言', '多模态', 'API接入'],
    imageUrl: 'https://placehold.co/600x400/3730a3/white?text=百度'
  },
  
  // 插件
  {
    id: 'plugin-1',
    title: '高级数据分析插件',
    description: '强大的数据分析工具，支持多种数据源和可视化功能',
    author: 'SOIT团队',
    type: 'plugin',

    rating: 4.8,
    downloads: 12500,
    tags: ['数据分析', '可视化', '报表'],
    imageUrl: 'https://placehold.co/600x400/2563eb/white?text=数据分析',
    isInstalled: true
  },
  {
    id: 'plugin-2',
    title: 'PDF文档处理工具',
    description: '全面的PDF处理功能，支持转换、编辑、注释和签名',
    author: 'DocTools Inc.',
    type: 'plugin',

    rating: 4.6,
    downloads: 8300,
    tags: ['PDF', '文档处理', '编辑器'],
    imageUrl: 'https://placehold.co/600x400/dc2626/white?text=PDF工具'
  },
  {
    id: 'plugin-3',
    title: '代码质量检测插件',
    description: '实时检测代码质量，提供优化建议和自动修复功能',
    author: 'CodeQuality',
    type: 'plugin',

    rating: 4.5,
    downloads: 15200,
    tags: ['代码质量', '静态分析', '开发工具'],
    imageUrl: 'https://placehold.co/600x400/4f46e5/white?text=代码质量'
  },
  {
    id: 'plugin-4',
    title: '多语言翻译助手',
    description: '支持100+种语言实时翻译，适用于国际化项目',
    author: 'LangTech',
    type: 'plugin',

    rating: 4.7,
    downloads: 9800,
    tags: ['翻译', '国际化', '多语言'],
    imageUrl: 'https://placehold.co/600x400/0891b2/white?text=翻译助手'
  },
  
  // 智能体
  {
    id: 'agent-1',
    title: '智能客服助手',
    description: '24/7全天候客服智能体，自动回答常见问题',
    author: 'AI Service Co.',
    type: 'agent',

    rating: 4.9,
    downloads: 5600,
    tags: ['客服', '自动回复', 'AI对话'],
    imageUrl: 'https://placehold.co/600x400/8b5cf6/white?text=客服助手'
  },
  {
    id: 'agent-2',
    title: '数据分析师',
    description: '专业数据分析智能体，提供深度数据洞察和报告',
    author: 'DataMind',
    type: 'agent',

    rating: 4.7,
    downloads: 3200,
    tags: ['数据分析', '报表', '商业智能'],
    imageUrl: 'https://placehold.co/600x400/6d28d9/white?text=数据分析师'
  },
  {
    id: 'agent-3',
    title: '代码助手Pro',
    description: '高级编程助手，提供代码建议、重构和优化',
    author: 'SOIT团队',
    type: 'agent',

    rating: 4.8,
    downloads: 18900,
    tags: ['编程', '代码生成', '开发工具'],
    imageUrl: 'https://placehold.co/600x400/7c3aed/white?text=代码助手',
    isInstalled: true
  },
  {
    id: 'agent-4',
    title: '内容创作助手',
    description: '帮助创作高质量内容，提供创意和写作建议',
    author: 'CreativeAI',
    type: 'agent',

    rating: 4.6,
    downloads: 7800,
    tags: ['内容创作', '写作', '创意'],
    imageUrl: 'https://placehold.co/600x400/9333ea/white?text=创作助手'
  },
  
  // 服务
  {
    id: 'service-1',
    title: '高级API访问',
    description: '提供更高的API调用限制和优先处理',
    author: 'SOIT团队',
    type: 'service',

    rating: 4.5,
    downloads: 2100,
    tags: ['API', '高级服务', '性能'],
    imageUrl: 'https://placehold.co/600x400/d97706/white?text=高级API'
  },
  {
    id: 'service-2',
    title: '专业技术支持',
    description: '24小时专业技术支持服务，优先响应',
    author: 'SOIT团队',
    type: 'service',

    rating: 4.9,
    downloads: 1500,
    tags: ['技术支持', '客服', '优先响应'],
    imageUrl: 'https://placehold.co/600x400/b45309/white?text=技术支持'
  },
  {
    id: 'service-3',
    title: '数据备份服务',
    description: '自动数据备份和恢复服务，保障数据安全',
    author: 'DataSafe',
    type: 'service',

    rating: 4.7,
    downloads: 3200,
    tags: ['数据备份', '安全', '恢复'],
    imageUrl: 'https://placehold.co/600x400/92400e/white?text=数据备份'
  },
  {
    id: 'service-4',
    title: '定制开发服务',
    description: '根据需求提供定制化开发和解决方案',
    author: 'SOIT团队',
    type: 'service',

    rating: 4.8,
    downloads: 850,
    tags: ['定制开发', '解决方案', '专业服务'],
    imageUrl: 'https://placehold.co/600x400/f59e0b/white?text=定制开发'
  },
  
  // 模板
  {
    id: 'template-1',
    title: '企业网站模板',
    description: '专业企业网站模板，包含多种页面布局和组件',
    author: 'WebDesign Pro',
    type: 'template',

    rating: 4.6,
    downloads: 8700,
    tags: ['网站', '企业', '响应式'],
    imageUrl: 'https://placehold.co/600x400/16a34a/white?text=企业网站'
  },
  {
    id: 'template-2',
    title: '数据可视化模板',
    description: '丰富的数据可视化模板，支持多种图表和交互',
    author: 'DataViz',
    type: 'template',

    rating: 4.7,
    downloads: 5400,
    tags: ['数据可视化', '图表', '仪表盘'],
    imageUrl: 'https://placehold.co/600x400/059669/white?text=数据可视化'
  },
  {
    id: 'template-3',
    title: '电子商务解决方案',
    description: '完整的电子商务网站模板，包含商品、购物车和支付功能',
    author: 'E-Commerce Solutions',
    type: 'template',

    rating: 4.8,
    downloads: 4200,
    tags: ['电子商务', '购物车', '支付'],
    imageUrl: 'https://placehold.co/600x400/10b981/white?text=电子商务'
  },
  {
    id: 'template-4',
    title: '项目管理模板',
    description: '专业项目管理模板，包含任务、日程和团队协作功能',
    author: 'ProjectPro',
    type: 'template',

    rating: 4.6,
    downloads: 3800,
    tags: ['项目管理', '任务', '团队协作'],
    imageUrl: 'https://placehold.co/600x400/047857/white?text=项目管理'
  }
]

// 生成模拟特色项目数据
export const mockFeaturedItems: FeaturedItemProps[] = [
  {
    id: 'featured-1',
    title: '企业智能套件',
    description: '全面的企业智能解决方案，包含多种工具和服务',
    imageUrl: 'https://placehold.co/1200x600/3b82f6/white?text=企业智能套件',
    badgeText: '热门推荐',
    buttonText: '了解详情'
  },
  {
    id: 'featured-2',
    title: '开发者工具包',
    description: '专为开发者打造的工具集，提升开发效率',
    imageUrl: 'https://placehold.co/1200x600/8b5cf6/white?text=开发者工具包',
    badgeText: '新品',
    buttonText: '立即体验'
  },
  {
    id: 'featured-3',
    title: '数据科学平台',
    description: '强大的数据分析和机器学习平台，助力数据驱动决策',
    imageUrl: 'https://placehold.co/1200x600/ec4899/white?text=数据科学平台',
    badgeText: '限时优惠',
    buttonText: '立即获取'
  }
]

// 按类别过滤商店项目
export const filterItemsByCategory = (items: StoreItemProps[], category: string): StoreItemProps[] => {
  if (category === 'all') return items
  return items.filter(item => item.type === category)
}

// 按搜索查询过滤商店项目
export const filterItemsByQuery = (items: StoreItemProps[], query: string): StoreItemProps[] => {
  if (!query) return items
  const lowerQuery = query.toLowerCase()
  return items.filter(item => 
    item.title.toLowerCase().includes(lowerQuery) || 
    item.description.toLowerCase().includes(lowerQuery) ||
    item.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
  )
}

// 获取推荐商店项目
export const getRecommendedItems = (items: StoreItemProps[], count: number = 4): StoreItemProps[] => {
  return [...items]
    .sort((a, b) => b.rating - a.rating)
    .slice(0, count)
}

// 获取热门商店项目
export const getPopularItems = (items: StoreItemProps[], count: number = 4): StoreItemProps[] => {
  return [...items]
    .sort((a, b) => b.downloads - a.downloads)
    .slice(0, count)
}

// 获取最新商店项目
export const getNewestItems = (items: StoreItemProps[], count: number = 4): StoreItemProps[] => {
  // 这里假设最新的项目是列表中的前几个
  return items.slice(0, count)
}

// 获取可用商店项目
export const getFreeItems = (items: StoreItemProps[], count: number = 4): StoreItemProps[] => {
  return items.filter(item => true).slice(0, count) // 所有项目都可用
}
