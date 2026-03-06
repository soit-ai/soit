import { create } from 'zustand'

interface ChatState {
  conversationMap: Map<string, string>
  setConversationId: (appId: string, conversationId: string | null) => void
  getConversationId: (appId: string) => string | null
  reset: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversationMap: new Map(),
  setConversationId: (appId, conversationId) => set((state) => {
    const newMap = new Map(state.conversationMap)
    if (conversationId === null) {
      newMap.delete(appId)
    } else {
      newMap.set(appId, conversationId)
    }
    return { conversationMap: newMap }
  }),
  getConversationId: (appId) => get().conversationMap.get(appId) || null,
  reset: () => set({ conversationMap: new Map() }),
}))

// 导出一个可以在函数组件外使用的 store 实例
export const chatStore = useChatStore.getState()
