import { Position } from '@xyflow/react';
import { useLayoutStore } from '../layout-store';
import { useMemo } from 'react';

/**
 * Returns handle positions based on the current layout direction.
 * @returns The source and target handle positions.
 */
export function useNodeHandles() {
  const { direction } = useLayoutStore();
  
  return useMemo(() => {
    const sourcePosition = direction === 'LR' ? Position.Right : Position.Bottom;
    const targetPosition = direction === 'LR' ? Position.Left : Position.Top;
    
    return {
      sourcePosition,
      targetPosition
    };
  }, [direction]); // Recompute only when the layout direction changes.
}
