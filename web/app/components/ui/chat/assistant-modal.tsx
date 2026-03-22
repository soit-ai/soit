'use client'

import { BotIcon, ChevronDownIcon } from 'lucide-react'

import { useRef, useState, useEffect, type FC } from 'react'
import { AssistantModalPrimitive } from '@assistant-ui/react'

import { TooltipIconButton } from '@/components/ui/chat/tooltip-icon-button'
import { ChatBox } from '@/components/ui/chat/chat-box'

export const AssistantModal: FC = () => {
  const [position, setPosition] = useState({ x: 24, y: 24 })
  // Store the last position to calculate drag offset.
  const [lastPosition, setLastPosition] = useState({ x: 24, y: 24 })
  const [isDragging, setIsDragging] = useState(false)
  const [startPos, setStartPos] = useState({ x: 0, y: 0 })
  const anchorRef = useRef<HTMLDivElement>(null)
  
  // Handle mouse down.
  const handleMouseDown = (e: React.MouseEvent) => {
    // Do not start drag when clicking the button itself.
    if ((e.target as HTMLElement).closest('.assistant-button')) {
      return
    }
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
    setStartPos({
      x: e.clientX,
      y: e.clientY
    })
    setLastPosition(position)
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }
  
  // Handle touch start.
  const handleTouchStart = (e: React.TouchEvent) => {
    // Do not start drag when clicking the button itself.
    if ((e.target as HTMLElement).closest('.assistant-button')) {
      return
    }
    if (e.touches.length === 1) {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(true)
      setStartPos({
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
      })
      setLastPosition(position)
      
      document.addEventListener('touchmove', handleTouchMove, { passive: false })
      document.addEventListener('touchend', handleTouchEnd)
    }
  }
  
  // Handle mouse move.
  const handleMouseMove = (e: MouseEvent) => {
    if (isDragging) {
      // Calculate cursor delta.
      const deltaX = e.clientX - startPos.x
      const deltaY = e.clientY - startPos.y
      
      // Compute new position based on delta.
      const newX = Math.max(0, Math.min(window.innerWidth - 56, lastPosition.x - deltaX))
      const newY = Math.max(0, Math.min(window.innerHeight - 56, lastPosition.y - deltaY))
      
      setPosition({
        x: newX,
        y: newY
      })
    }
  }
  
  // Handle touch move.
  const handleTouchMove = (e: TouchEvent) => {
    if (isDragging && e.touches.length === 1) {
      e.preventDefault() // Prevent page scrolling.
      
      // Calculate touch delta.
      const deltaX = e.touches[0].clientX - startPos.x
      const deltaY = e.touches[0].clientY - startPos.y
      
      // Compute new position based on delta.
      const newX = Math.max(0, Math.min(window.innerWidth - 56, lastPosition.x - deltaX))
      const newY = Math.max(0, Math.min(window.innerHeight - 56, lastPosition.y - deltaY))
      
      setPosition({
        x: newX,
        y: newY
      })
    }
  }
  
  // Handle mouse release.
  const handleMouseUp = () => {
    setIsDragging(false)
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }
  
  // Handle touch end.
  const handleTouchEnd = () => {
    setIsDragging(false)
    document.removeEventListener('touchmove', handleTouchMove)
    document.removeEventListener('touchend', handleTouchEnd)
  }
  
  // Cleanup event listeners.
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleTouchEnd)
    }
  }, [])
  return (
    <AssistantModalPrimitive.Root>
        <AssistantModalPrimitive.Anchor 
          className="fixed size-14 z-50 touch-none" 
          style={{ 
            bottom: `${position.y}px`, 
            right: `${position.x}px`,
            transition: isDragging ? 'none' : 'all 0.3s ease',
            cursor: isDragging ? 'grabbing' : 'grab'
          }}
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
          ref={anchorRef}>
          <AssistantModalPrimitive.Trigger asChild>
            <AssistantModalButton />
          </AssistantModalPrimitive.Trigger>
        </AssistantModalPrimitive.Anchor>
        <AssistantModalPrimitive.Content
          sideOffset={16}
          className="bg-popover text-popover-foreground z-50 h-[700px] w-[400px] overflow-clip rounded-xl border p-0 shadow-md outline-none [&>.aui-thread-root]:bg-inherit data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out data-[state=open]:zoom-in data-[state=open]:slide-in-from-bottom-1/2 data-[state=open]:slide-in-from-right-1/2 data-[state=closed]:slide-out-to-bottom-1/2 data-[state=closed]:slide-out-to-right-1/2"
        >
          <ChatBox agentId="default" initInputPosition="bottom" isInModal={true} />
        </AssistantModalPrimitive.Content>
      </AssistantModalPrimitive.Root>
  )
}

type AssistantModalButtonProps = { 'data-state'?: 'open' | 'closed' }

const AssistantModalButton = ({ 'data-state': state, ...rest }: AssistantModalButtonProps) => {
  const tooltip = state === 'open' ? 'Close Assistant' : 'Open Assistant'

  return (
    <TooltipIconButton 
      variant="default" 
      tooltip={tooltip} 
      side="left" 
      {...rest} 
      className="assistant-button size-full rounded-full shadow-lg transition-all duration-300 hover:scale-110 active:scale-90 bg-gradient-to-br from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-2 border-white/20"
    >
      <div className="absolute inset-0 rounded-full bg-white/10 backdrop-blur-sm"></div>
      <div className="relative z-10 flex items-center justify-center">
        <BotIcon 
          data-state={state} 
          className="absolute size-6 text-white transition-all duration-300 data-[state=closed]:rotate-0 data-[state=open]:rotate-90 data-[state=closed]:scale-100 data-[state=open]:scale-0" 
        />
        <ChevronDownIcon
          data-state={state}
          className="absolute size-6 text-white transition-all duration-300 data-[state=closed]:-rotate-90 data-[state=open]:rotate-0 data-[state=closed]:scale-0 data-[state=open]:scale-100"
        />
      </div>
      <span className="sr-only">{tooltip}</span>
    </TooltipIconButton>
  )
}

AssistantModalButton.displayName = 'AssistantModalButton'
