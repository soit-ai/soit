import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { CurrentUser } from '@/services/identity-service'

export type NavUserInfo = {
  name: string
  email: string
  avatar: string
}

const DEFAULT_NAV_USER: NavUserInfo = {
  name: 'Guest',
  email: '-',
  avatar: '',
}

const toNavUser = (user: CurrentUser | null): NavUserInfo => {
  if (!user) {
    return DEFAULT_NAV_USER
  }
  const profile = user.profile || {}
  const avatar = typeof profile.avatar === 'string' ? profile.avatar : ''
  return {
    name: user.name || user.email || DEFAULT_NAV_USER.name,
    email: user.email || DEFAULT_NAV_USER.email,
    avatar,
  }
}

interface UserState {
  currentUser: CurrentUser | null
  navUser: NavUserInfo
  setCurrentUser: (user: CurrentUser | null) => void
  clearUser: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      currentUser: null,
      navUser: DEFAULT_NAV_USER,
      setCurrentUser: (user) =>
        set({
          currentUser: user,
          navUser: toNavUser(user),
        }),
      clearUser: () =>
        set({
          currentUser: null,
          navUser: DEFAULT_NAV_USER,
        }),
    }),
    {
      name: 'soit-user-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        currentUser: state.currentUser,
        navUser: state.navUser,
      }),
    }
  )
)

