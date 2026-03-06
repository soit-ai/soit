import { create } from 'zustand';

// Layout direction type.
export type LayoutDirection = 'LR' | 'TB';

// Layout state shape.
interface LayoutState {
  direction: LayoutDirection;
  setDirection: (direction: LayoutDirection) => void;
}

// Layout state store.
export const useLayoutStore = create<LayoutState>((set) => ({
  direction: 'LR', // Default to horizontal layout.
  setDirection: (direction) => set({ direction }),
}));
