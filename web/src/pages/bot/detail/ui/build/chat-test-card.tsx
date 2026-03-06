import React from 'react'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Bot, RefreshCw, MessageSquare } from 'lucide-react'
import { SelectModel } from '@/components/ui/form/select-model'

interface ChatTestCardProps {
  index: number
  testHistory: Array<{ role: string; content: string }>
  selectedModel: string
  onModelChange: (model: string) => void
  onReset: () => void
}

export const ChatTestCard: React.FC<ChatTestCardProps> = ({
  index,
  testHistory,
  selectedModel,
  onModelChange,
  onReset,
}) => {
  return (
    <div className="flex-1 overflow-hidden p-4">
      <div className="flex flex-col h-full rounded-lg border bg-background">
        <div className="flex items-center justify-between p-3 border-b bg-background">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            <h2 className="font-medium">Chat Test #{index + 1}</h2>
          </div>
          <div className="flex items-center gap-2">
            <SelectModel
              value={selectedModel}
              onChange={onModelChange}
              className="w-[200px]"
              triggerClassName="h-8"
            />
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onReset}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Reset Conversation</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="flex flex-col space-y-4">
            {/* Welcome message */}
            <div className="flex items-start gap-3">
              <Avatar className="h-8 w-8 mt-1">
                <AvatarImage src="/bot-avatar.png" alt="Bot" />
                <AvatarFallback className="bg-primary/10 text-primary">
                  <Bot className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 rounded-lg bg-muted/30 p-3 text-sm">
                <p>Hello! Welcome to SOIT AI Assistant! I'm here to help you test your configuration. Please let me know what you'd like to know, and I'll respond based on your system prompts and settings.</p>
              </div>
            </div>

            {/* User messages and assistant replies */}
            {testHistory.map((msg, index) => (
              <div key={index} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <Avatar className="h-8 w-8 mt-1">
                    <AvatarImage src="/bot-avatar.png" alt="Bot" />
                    <AvatarFallback className="bg-primary/10 text-primary">
                      <Bot className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                )}
                <div className={`flex-1 rounded-lg p-3 text-sm ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted/30'}`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                {msg.role === 'user' && (
                  <Avatar className="h-8 w-8 mt-1">
                    <AvatarImage src="/user-avatar.png" alt="User" />
                    <AvatarFallback>U</AvatarFallback>
                  </Avatar>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatTestCard 