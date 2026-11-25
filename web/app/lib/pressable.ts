import type { KeyboardEvent } from 'react'

/**
 * Props that make an element that is not a button operable like one: focusable,
 * announced as a button, and triggered by Enter or Space as well as a click.
 * For rows and cards whose layout a real <button> would break.
 */
export function pressable(onPress: () => void) {
  return {
    role: 'button' as const,
    tabIndex: 0,
    onClick: onPress,
    onKeyDown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onPress()
      }
    },
  }
}
