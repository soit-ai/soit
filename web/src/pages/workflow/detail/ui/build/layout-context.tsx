import React, { createContext, useContext, useState } from 'react';

// Layout direction type.
export type LayoutDirection = 'LR' | 'TB';

// Layout context type.
interface LayoutContextType {
  direction: LayoutDirection;
  setDirection: (direction: LayoutDirection) => void;
}

// Create the layout context.
const LayoutContext = createContext<LayoutContextType>({
  direction: 'LR', // Default to horizontal layout.
  setDirection: () => {},
});

// Layout provider component.
export const LayoutProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [direction, setDirection] = useState<LayoutDirection>('LR');

  return (
    <LayoutContext.Provider value={{ direction, setDirection }}>
      {children}
    </LayoutContext.Provider>
  );
};

// Hook for accessing the layout context.
export const useLayout = () => useContext(LayoutContext);
