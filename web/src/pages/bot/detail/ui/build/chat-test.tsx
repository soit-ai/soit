import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SendHorizontal, SplitSquareHorizontal, ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import ChatTestCard from './chat-test-card'

interface ChatTestProps {
  testMessage: string
  setTestMessage: (message: string) => void
  testHistory: Array<{ role: string; content: string }>
  handleSendTest: (message: string) => void
}

export const ChatTest: React.FC<ChatTestProps> = ({ testMessage, setTestMessage, testHistory, handleSendTest }) => {
  const [cardCount, setCardCount] = useState(1)
  const [selectedModels, setSelectedModels] = useState<Record<number, string>>({
    0: "gpt-4"
  })

  const handleModelChange = (index: number, model: string) => {
    setSelectedModels(prev => ({
      ...prev,
      [index]: model
    }))
  }

  const handleReset = (index: number) => {
    // TODO: Implement reset functionality for individual cards
    console.log(`Reset card ${index}`)
  }

  const renderChatCards = () => {
    const cards = []
    for (let i = 0; i < cardCount; i++) {
      cards.push(
        <ChatTestCard
          key={i}
          index={i}
          testHistory={testHistory}
          selectedModel={selectedModels[i] || "gpt-4"}
          onModelChange={(model) => handleModelChange(i, model)}
          onReset={() => handleReset(i)}
        />
      )
    }
    return cards
  }

  return (
    <div className="flex flex-col h-full relative">
      <div className={`flex-1 ${cardCount === 4 ? 'grid grid-cols-2 grid-rows-2' : 'flex'} pb-[72px]`}>
        {renderChatCards()}
      </div>
      <div className="absolute bottom-0 left-0 right-0 border-t bg-background p-3">
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2 h-9">
                <SplitSquareHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => setCardCount(1)}>Single View</DropdownMenuItem>
              <DropdownMenuItem onClick={() => setCardCount(2)}>Dual View</DropdownMenuItem>
              {/* <DropdownMenuItem onClick={() => setCardCount(3)}>Three View</DropdownMenuItem> */}
              <DropdownMenuItem onClick={() => setCardCount(4)}>Quad View</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Input
            placeholder="Type a message to test..."
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSendTest(testMessage)
              }
            }}
            className="flex-1"
          />
          <Button size="icon" onClick={() => handleSendTest(testMessage)} disabled={!testMessage.trim()}>
            <SendHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ChatTest
