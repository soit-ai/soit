import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable'
import type { FC, PropsWithChildren } from 'react'

import { ChatBox } from '@/components/ui/chat/chat-box'

export const AssistantSidebar: FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="flex flex-1 fixed top-0 right-0 bottom-0 flex-col h-full w-[500px]">
      <ResizablePanelGroup direction="horizontal">
        {/* <ResizablePanel>{children}</ResizablePanel> */}
        <ResizableHandle />
        <ResizablePanel>
          <ChatBox appId="default" conversationId="" initInputPosition="center" />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
