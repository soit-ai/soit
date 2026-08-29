import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
} from '@assistant-ui/react'
import { useTranslation } from 'react-i18next'
import type { FC } from 'react'
import {
  ArrowDownIcon,
  Atom,
  AudioLinesIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  Globe,
  PencilIcon,
  RefreshCwIcon,
  SendHorizontalIcon,
  StopCircleIcon,
  Webhook,
  Loader2Icon,
  AlertCircleIcon,
  ClockIcon,
  CheckCircle2Icon,
  Sparkles,
  ImageIcon,
  FileIcon,
  MicIcon,
  ThumbsUpIcon,
  ThumbsDownIcon,
  Share2Icon,
  MoreHorizontalIcon,
  LightbulbIcon,
  CodeIcon,
  SearchIcon,
  Activity,
  DownloadIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

import { ChevronDownIcon, ChevronUpIcon } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'

import { ScrollArea as ScrollAreaPrimitive } from '@base-ui/react/scroll-area'
import { Button } from '@/components/ui/button'
import { MarkdownText } from '@/components/ui/chat/markdown-text'
import { TooltipIconButton } from '@/components/ui/chat/tooltip-icon-button'
import { ScrollBar } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent } from '@/components/ui/card'
import { ToolFallback } from '@/components/ui/chat/tool-fallback'
import { Reasoning, ReasoningGroup } from '@/components/ui/chat/reasoning'
import { ApprovalInterrupts } from '@/components/ui/chat/approval-interrupts'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

import { Bold, Italic, Underline } from 'lucide-react'
import { ModelIcon } from '@/components/ui/app/model-icon'
import { ComposerAddAttachment, ComposerAttachments, UserMessageAttachments } from './attachment'
import { Toggle } from '../toggle'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from '@/hooks/use-navigate'
import { debugLog } from '@/utils/debug'
import { downloadGovernedFile } from '@/services/attachment-service'
import {
  isCodeInterpreterEnabled,
  isWebSearchEnabled,
  setCodeInterpreterEnabled,
  setWebSearchEnabled,
} from '@/components/ui/chat/defaults'

const EMPTY_MESSAGE_METADATA: Readonly<Record<string, never>> = Object.freeze({})

export type ThreadProps = ThreadPrimitive.Root.Props & {
  onSend?: (message: string) => void
  initInputPosition?: 'center' | 'bottom'
  className?: string
  title?: string
  isInModal?: boolean
}

export const Thread: FC<ThreadProps & { ref?: React.RefObject<HTMLDivElement> }> = ({ onSend, initInputPosition = 'center', className = '', ref, title = '', isInModal = false }) => {
  const aui = useAui()
  const threadMessages = useAuiState(({ thread }) => thread.messages)
  const [inputPosition, setInputPosition] = useState<'center' | 'bottom'>(initInputPosition)
  const [topTitle, setTopTitle] = useState(title)
  const { t } = useTranslation()

  useEffect(() => {
    if (threadMessages.length >= 1) {
      const message = threadMessages[0]
      if (message?.content?.[0]?.type === 'text') {
        const _text = message.content[0].text
        if (_text) {
          setTopTitle(_text)
        }
      }
    }
  }, [threadMessages])

  useEffect(() => {
    debugLog('ThreadBox aui state:', {
      threadState: aui.thread().getState(),
      composerState: aui.composer().getState(),
      threadMessages: aui.thread().getState().messages,
    })
  }, [aui])

  return (
    <ScrollAreaPrimitive.Root
      render={
        <ThreadPrimitive.Root className="bg-background box-border flex h-full flex-col overflow-hidden " />
      }
      className={cn(
        'flex flex-col h-full w-full p-2 justify-center [--thread-max-width:100%] lg:[--thread-max-width:50rem] xl:[--thread-max-width:50rem] 2xl:[--thread-max-width:55rem] 3xl:[--thread-max-width:60rem]',
        className
      )}
    >
        <ScrollAreaPrimitive.Viewport
          className="thread-viewport flex h-full flex-col "
          render={
            <ThreadPrimitive.Viewport
              className={cn('flex h-full flex-col items-center self-stretch overflow-y-scroll bg-inherit px-4 pt-8 ')}
              style={{ scrollbarWidth: 'none' }}
            />
          }
        >
            <ThreadPrimitive.Empty>
              <div className={cn('flex h-full flex-col w-full  max-w-[var(--thread-max-width)] items-center justify-center mt-[0px]')}>
                <ThreadWelcome />
                {inputPosition === 'center' && <Composer className="bottom-0 mb-5 w-full max-w-[var(--thread-max-width)]" />}
                {/* {!isInModal && <ThreadWelcomeSuggestions />} */}
              </div>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{
                UserMessage: UserMessage,
                AssistantMessage: AssistantMessage,
                SystemMessage: SystemMessage,
                EditComposer: EditComposer,
              }}
            />
            <ThreadPrimitive.If empty={false}>
              <div className="min-h-8 flex-grow " />
            </ThreadPrimitive.If>
            <div className="fixed pl-3 pr-3 bottom-[150px] flex w-full min-w-auto max-w-[var(--thread-max-width)] flex-col items-end justify-end rounded-t-lg bg-inherit ">
              <ThreadScrollToBottom />
            </div>
        </ScrollAreaPrimitive.Viewport>
        <ScrollBar />
        <ApprovalInterrupts />
        <ThreadPrimitive.If empty={false}>
          <Composer className="bottom-0 w-full max-w-[var(--thread-max-width)] mx-2" />
        </ThreadPrimitive.If>
        <ThreadPrimitive.If empty={true}>{inputPosition === 'bottom' && <Composer className="bottom-0 w-full max-w-[var(--thread-max-width)]" />}</ThreadPrimitive.If>
    </ScrollAreaPrimitive.Root>
  )
}

const ThreadScrollToBottom: FC = () => {
  const { t } = useTranslation()
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton tooltip={t('chat.thread.scrollToBottom')} variant="outline" className="absolute -top-8 rounded-full cursor-pointer disabled:invisible">
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  )
}

const ThreadWelcome: FC = () => {
  const { t } = useTranslation()
  const [currentModelIndex, setCurrentModelIndex] = useState(0)
  const models = [
    { name: 'openai', type: 'logo' as const },
    { name: 'deepseek', type: 'logo' as const },
    { name: 'ollama', type: 'logo' as const },
    { name: 'claude', type: 'logo' as const },
    { name: 'gemini', type: 'logo' as const },
    { name: 'xai', type: 'logo' as const },
    { name: 'microsoft', type: 'logo' as const },
    { name: 'google', type: 'logo' as const },
    { name: 'anthropic', type: 'logo' as const },
  ]

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentModelIndex((prev) => (prev + 1) % models.length)
    }, 3000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex w-full max-w-[var(--thread-max-width)] flex-col items-center space-y-4 py-2">
      <div className="flex flex-col items-center justify-center text-center space-y-3">
        <div className="relative h-16 w-16 mb-4">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentModelIndex}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{
                type: 'spring',
                stiffness: 300,
                damping: 30,
              }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <div className="bg-gradient-to-br from-primary/20 to-primary/5 p-3 rounded-2xl shadow-sm">
                <ModelIcon name={models[currentModelIndex].name} type={models[currentModelIndex].type} size={40} />
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">{t('chat.thread.assistant.title')}</h2>

        <p className="text-muted-foreground text-lg max-w-md">{t('chat.thread.assistant.description')}</p>

        <div className="flex items-center gap-2 mt-2">
          <Badge variant="outline" className="bg-primary/5 text-primary hover:bg-primary/10 transition-colors">
            <Sparkles className="h-3 w-3 mr-1" />
            {t('chat.thread.assistant.capabilities.multimodal')}
          </Badge>
          <Badge variant="outline" className="bg-primary/5 text-primary hover:bg-primary/10 transition-colors">
            <CodeIcon className="h-3 w-3 mr-1" />
            {t('chat.thread.assistant.capabilities.codeGeneration')}
          </Badge>
          <Badge variant="outline" className="bg-primary/5 text-primary hover:bg-primary/10 transition-colors">
            <SearchIcon className="h-3 w-3 mr-1" />
            {t('chat.thread.assistant.capabilities.webSearch')}
          </Badge>
        </div>
      </div>

      <div className="w-full max-w-lg">
        <Separator className="my-4" />
        <h3 className="text-center text-sm font-medium text-muted-foreground mb-3 flex items-center justify-center">
          <LightbulbIcon className="h-4 w-4 mr-2" />
          {t('chat.thread.assistant.suggestions.title')}
        </h3>
      </div>
    </div>
  )
}

const ThreadWelcomeSuggestions: FC = () => {
  const { t } = useTranslation()
  const suggestions = [
    {
      icon: <CodeIcon className="h-4 w-4" />,
      title: t('chat.thread.assistant.suggestions.items.reactComponent.title'),
      prompt: t('chat.thread.assistant.suggestions.items.reactComponent.prompt'),
      color: 'from-cat-blue/20 to-cat-cyan/20',
    },
    {
      icon: <ImageIcon className="h-4 w-4" />,
      title: t('chat.thread.assistant.suggestions.items.imageDescription.title'),
      prompt: t('chat.thread.assistant.suggestions.items.imageDescription.prompt'),
      color: 'from-cat-purple/20 to-cat-pink/20',
    },
    {
      icon: <SearchIcon className="h-4 w-4" />,
      title: t('chat.thread.assistant.suggestions.items.aiResearch.title'),
      prompt: t('chat.thread.assistant.suggestions.items.aiResearch.prompt'),
      color: 'from-cat-amber/20 to-cat-amber/20',
    },
    {
      icon: <Sparkles className="h-4 w-4" />,
      title: t('chat.thread.assistant.suggestions.items.creativeWriting.title'),
      prompt: t('chat.thread.assistant.suggestions.items.creativeWriting.prompt'),
      color: 'from-cat-green/20 to-cat-green/20',
    },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl px-4 mt-4">
      {suggestions.map((suggestion, index) => (
        <ThreadPrimitive.Suggestion
          key={index}
          className={`bg-gradient-to-br ${suggestion.color} hover:opacity-90 flex flex-col items-start rounded-xl border border-border/40 p-4 transition-all duration-200 ease-in-out cursor-pointer shadow-sm hover:shadow-md`}
          prompt={suggestion.prompt}
          method="replace"
          autoSend
        >
          <div className="flex items-center gap-3 mb-1">
            <div className="bg-background/80 p-1.5 rounded-md">{suggestion.icon}</div>
            <span className="font-medium">{suggestion.title}</span>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2 pl-9">{suggestion.prompt}</p>
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  )
}

const Composer: FC<ComposerPrimitive.Root.Props> = (props) => {
  const { className, style, ...rest } = props
  const [isFocused, setIsFocused] = useState(false)
  const [charCount, setCharCount] = useState(0)
  const [deepThinkingEnabled, setDeepThinkingEnabled] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }
    return localStorage.getItem('chat_deep_thinking') === '1'
  })
  const [webSearchEnabled, setWebSearchEnabledState] = useState(isWebSearchEnabled)
  const [codeInterpreterEnabled, setCodeInterpreterEnabledState] = useState(
    isCodeInterpreterEnabled
  )
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const text = useAuiState(({ composer }) => composer.text)
  const { t } = useTranslation()

  useEffect(() => {
    setCharCount(text.length)
  }, [text])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    localStorage.setItem('chat_deep_thinking', deepThinkingEnabled ? '1' : '0')
  }, [deepThinkingEnabled])

  const handleWebSearchChange = (enabled: boolean) => {
    setWebSearchEnabledState(enabled)
    setWebSearchEnabled(enabled)
  }

  const handleCodeInterpreterChange = (enabled: boolean) => {
    setCodeInterpreterEnabledState(enabled)
    setCodeInterpreterEnabled(enabled)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Tab') {
      e.preventDefault()
      // Optional: implement tab completion here.
    }
  }

  return (
    <div className="flex flex-col w-full justify-center items-center text-center">
      <ComposerPrimitive.Root
        className={cn(
          'group flex w-full flex-wrap items-end rounded-xl border mb-4 px-3 py-1 shadow-md transition-all duration-300 ease-in-out bg-background/80 backdrop-blur-sm',
          isFocused ? 'ring-2 ring-primary/40 border-primary/40' : 'border-border/60 hover:border-primary/30',
          className
        )}
        style={{ ...style }}
        {...rest}
      >
        <ComposerAttachments />
        <div className="flex w-full flex-row px-2 max-h-24 relative">
          <ComposerPrimitive.Input
            ref={inputRef}
            rows={1}
            autoFocus
            placeholder={t('chat.thread.composer.placeholder')}
            className="placeholder:text-muted-foreground/70 h-full w-full flex-grow resize-none border-none bg-transparent py-3 text-sm outline-none focus:ring-0 disabled:cursor-not-allowed transition-all duration-200"
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            onKeyDown={handleKeyDown}
          />
          {isFocused && text.length === 0 && (
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 text-xs text-muted-foreground/50 pointer-events-none">
              {t('chat.thread.composer.tabCompletion')} <kbd className="px-1.5 py-0.5 bg-muted rounded-md border border-border/40 mx-1 text-[10px] font-mono">{t('chat.thread.composer.tab')}</kbd>{' '}
              {t('chat.thread.composer.complete')}
              <span className="mx-1">·</span>
              <kbd className="px-1.5 py-0.5 bg-muted rounded-md border border-border/40 mx-1 text-[10px] font-mono">↑</kbd> {t('chat.thread.composer.editPrevious')}
            </div>
          )}
        </div>
        <div className="flex w-full flex-row gap-2 px-1 py-1.5 border-t border-border/30 mt-1">
          <div className="flex flex-row gap-2 justify-start items-center">
            <div className="flex gap-2 items-center">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger render={<Toggle
                      pressed={deepThinkingEnabled}
                      onPressedChange={setDeepThinkingEnabled}
                      size="sm"
                      aria-label="Toggle deepthink"
                      className={cn(
                        'border-[1px] rounded-lg transition-all duration-200 hover:bg-muted',
                        deepThinkingEnabled
                          ? 'bg-[#daeeff] text-[#0285ff] border-[#7abfff] shadow-sm dark:bg-[#2a4a6d] dark:text-[#48aaff] dark:border-[#3f6b94]'
                          : 'border-[#0d0d0d1a] dark:border-[#0d0d0d1a]'
                      )}
                    >
                      <Atom className="h-3.5 w-3.5" />
                      <span className="text-xs font-medium">{t('chat.thread.composer.deepThinking')}</span>
                    </Toggle>} />
                  <TooltipContent side="top" className="text-xs">
                    {t('chat.thread.composer.tooltips.deepThinking')}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger render={<Toggle
                      pressed={webSearchEnabled}
                      onPressedChange={handleWebSearchChange}
                      size="sm"
                      aria-label="Toggle search"
                      className="transition-all duration-200 dark:data-[state=on]:bg-[#2a4a6d] data-[state=on]:text-[#0285ff] data-[state=on]:bg-[#daeeff] dark:data-[state=on]:text-[#48aaff] border-[1px] border-[#0d0d0d1a] dark:border-[#0d0d0d1a] rounded-lg hover:bg-muted"
                    >
                      <SearchIcon className="h-3.5 w-3.5" />
                      <span className="text-xs font-medium">{t('chat.thread.composer.webSearch')}</span>
                    </Toggle>} />
                  <TooltipContent side="top" className="text-xs">
                    {t('chat.thread.composer.tooltips.webSearch')}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger render={<Toggle
                      pressed={codeInterpreterEnabled}
                      onPressedChange={handleCodeInterpreterChange}
                      size="sm"
                      aria-label="Toggle code"
                      className="transition-all duration-200 dark:data-[state=on]:bg-[#2a4a6d] data-[state=on]:text-[#0285ff] data-[state=on]:bg-[#daeeff] dark:data-[state=on]:text-[#48aaff] border-[1px] border-[#0d0d0d1a] dark:border-[#0d0d0d1a] rounded-lg hover:bg-muted"
                    >
                      <CodeIcon className="h-3.5 w-3.5" />
                      <span className="text-xs font-medium">{t('chat.thread.composer.codeMode')}</span>
                    </Toggle>} />
                  <TooltipContent side="top" className="text-xs">
                    {t('chat.thread.composer.tooltips.codeMode')}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          <div className="flex flex-row gap-2 justify-end items-center ml-auto">
            {charCount > 0 && <div className={cn('text-xs transition-all duration-200', charCount > 2000 ? 'text-destructive' : 'text-muted-foreground/60')}>{charCount}/4000</div>}
            <ComposerAddAttachment />
            <ComposerAction />
          </div>
        </div>
      </ComposerPrimitive.Root>
      <div className="text-xs text-muted-foreground/60 mt-1 mb-1 flex items-center gap-1.5">
        <LightbulbIcon className="h-3 w-3" />
        <span>{t('chat.thread.composer.multimodalHint')}</span>
      </div>
    </div>
  )
}

const ComposerAction: FC = () => {
  const text = useAuiState(({ composer }) => composer.text)
  const attachmentCount = useAuiState(({ composer }) => composer.attachments.length)
  const { t } = useTranslation()
  const canSend = text.trim().length > 0 || attachmentCount > 0

  return (
    <>
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            tooltip={t('chat.thread.composer.send')}
            variant="default"
            className={cn(
              'my-1 size-9 p-2 text-primary-foreground rounded-lg transition-all duration-300 shadow-sm',
              canSend ? 'bg-primary hover:bg-primary/90 hover:shadow-md hover:scale-105 active:scale-95' : 'bg-primary/50 cursor-not-allowed'
            )}
            disabled={!canSend}
          >
            <SendHorizontalIcon className="size-4" />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel asChild>
          <TooltipIconButton tooltip={t('chat.thread.composer.cancel')} variant="destructive" className="my-1 size-9 p-2 rounded-lg transition-all duration-300 shadow-sm hover:shadow-md hover:scale-105 active:scale-95">
            <CircleStopIcon className="size-4 relative z-10" />
          </TooltipIconButton>
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </>
  )
}

const UserMessage: FC = () => {
  const { t } = useTranslation()

  return (
    <MessagePrimitive.Root className="flex flex-col auto-rows-auto gap-y-0 w-full max-w-[var(--thread-max-width)] py-3">
      <UserMessageAttachments />
      <div className="flex justify-end items-start gap-2">
        <div className="flex flex-col items-end gap-1 max-w-[calc(var(--thread-max-width)*0.8)]">
          <div className="bg-primary/10 dark:bg-primary/20 text-foreground break-words rounded-2xl rounded-tr-sm px-4 py-2.5">
            <MessagePrimitive.Parts />
          </div>

          <div className="h-5 flex items-center justify-end mr-1">
            <UserActionBar />
          </div>
        </div>

        <Avatar className="mt-0.5 flex-shrink-0 h-8 w-8 bg-primary/10">
          <AvatarFallback className="text-xs font-medium text-primary">{t('chat.thread.userLabel')}</AvatarFallback>
        </Avatar>
      </div>

      <BranchPicker hideWhenSingleBranch className="flex justify-end mt-1" />
    </MessagePrimitive.Root>
  )
}

// const UserActionBar: FC = () => {
//   return (
//     <ActionBarPrimitive.Root hideWhenRunning autohide="not-last" className="flex flex-row justify-center items-end col-start-1 row-start-2 mr-3 mt-2.5 mb-2.5">
//       <ActionBarPrimitive.Copy asChild>
//         <TooltipIconButton tooltip="Copy">
//           <MessagePrimitive.If copied>
//             <CheckIcon />
//           </MessagePrimitive.If>
//           <MessagePrimitive.If copied={false}>
//             <CopyIcon />
//           </MessagePrimitive.If>
//         </TooltipIconButton>
//       </ActionBarPrimitive.Copy>
//       <ActionBarPrimitive.Edit asChild>
//         <TooltipIconButton tooltip="Edit">
//           <PencilIcon />
//         </TooltipIconButton>
//       </ActionBarPrimitive.Edit>
//     </ActionBarPrimitive.Root>
//   )
// }
const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="text-muted-foreground flex justify-end gap-1 col-start-3 row-start-2 -ml-1 data-[floating]:bg-background data-[floating]:absolute data-[floating]:rounded-md data-[floating]:p-1 "
    >
      <MessagePrimitive.If speaking={false}>
        <ActionBarPrimitive.Speak asChild>
          <TooltipIconButton tooltip="Read aloud">
            <AudioLinesIcon />
          </TooltipIconButton>
        </ActionBarPrimitive.Speak>
      </MessagePrimitive.If>
      <MessagePrimitive.If speaking>
        <ActionBarPrimitive.StopSpeaking asChild>
          <TooltipIconButton tooltip="Stop">
            <StopCircleIcon />
          </TooltipIconButton>
        </ActionBarPrimitive.StopSpeaking>
      </MessagePrimitive.If>
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <MessagePrimitive.If copied>
            <CheckIcon />
          </MessagePrimitive.If>
          <MessagePrimitive.If copied={false}>
            <CopyIcon />
          </MessagePrimitive.If>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="Edit">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  )
}

const EditComposer: FC = () => {
  return (
    <ComposerPrimitive.Root className="bg-muted my-4 flex w-full max-w-[var(--thread-max-width)] flex-col gap-2 rounded-xl">
      <ComposerPrimitive.Input className="text-foreground flex h-8 w-full resize-none bg-transparent p-4 pb-0 outline-none" />
      <div className="mx-3 mb-3 flex items-center justify-center gap-2 self-end">
        <ComposerPrimitive.Cancel asChild>
          <Button variant="ghost">Cancel</Button>
        </ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send asChild>
          <Button>Send</Button>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  )
}

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-danger-foreground">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="flex flex-col auto-rows-auto w-full max-w-[var(--thread-max-width)] py-3">
      <div className="flex items-start gap-2">
        <Avatar className="mt-0.5 flex-shrink-0 h-8 w-8 bg-gradient-to-br from-primary/30 to-primary/20">
          <AvatarFallback className="text-xs font-medium text-primary">AI</AvatarFallback>
        </Avatar>

        <div className="flex flex-col gap-1 max-w-[calc(var(--thread-max-width)*0.8)]">
          <div className="bg-background border border-border/50 text-foreground break-words rounded-2xl rounded-tl-sm px-4 py-3 ">
            <MessagePrimitive.Parts
              components={{
                Text: MarkdownText,
                Reasoning,
                ReasoningGroup,
                tools: { Fallback: ToolFallback },
              }}
            />
            <MessageError />
          </div>

          <div className="h-5 flex items-center ml-1">
            <AssistantActionBar />
          </div>
          <AssistantMeta />
          <AssistantCitations />
          <AssistantArtifacts />
        </div>
      </div>

      <BranchPicker hideWhenSingleBranch className="flex justify-start ml-10 mt-1" />
    </MessagePrimitive.Root>
  )
}

const SystemMessage: FC = () => {
  return (
    <MessagePrimitive.Root className="flex flex-col auto-rows-auto w-full max-w-[var(--thread-max-width)] py-3">
      <div className="flex items-start gap-2">
        <div className="flex flex-col gap-1 max-w-[calc(var(--thread-max-width)*0.8)]">
          <div className="bg-background border border-border/50 text-foreground break-words rounded-2xl rounded-tl-sm px-4 py-3 ">
            <MessagePrimitive.Content />
          </div>  
        </div>
      </div>
    </MessagePrimitive.Root>
  )
}

const AssistantActionBar: FC = () => {
  const { t } = useTranslation()
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="text-muted-foreground flex gap-1 col-start-3 row-start-2 -ml-1 data-[floating]:bg-background data-[floating]:absolute data-[floating]:rounded-md  data-[floating]:p-1 "
    >
      <MessagePrimitive.If speaking={false}>
        <ActionBarPrimitive.Speak asChild>
          <TooltipIconButton tooltip="Read aloud">
            <AudioLinesIcon />
          </TooltipIconButton>
        </ActionBarPrimitive.Speak>
      </MessagePrimitive.If>
      <MessagePrimitive.If speaking>
        <ActionBarPrimitive.StopSpeaking asChild>
          <TooltipIconButton tooltip="Stop">
            <StopCircleIcon />
          </TooltipIconButton>
        </ActionBarPrimitive.StopSpeaking>
      </MessagePrimitive.If>
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <AuiIf condition={(s) => s.message.isCopied}>
            <CheckIcon />
          </AuiIf>
          <AuiIf condition={(s) => !s.message.isCopied}>
            <CopyIcon />
          </AuiIf>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip={t('chat.thread.actions.regenerate')}>
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
      <ActionBarPrimitive.FeedbackPositive asChild>
        <TooltipIconButton tooltip={t('chat.thread.actions.helpful')}>
          <ThumbsUpIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.FeedbackPositive>
      <ActionBarPrimitive.FeedbackNegative asChild>
        <TooltipIconButton tooltip={t('chat.thread.actions.unhelpful')}>
          <ThumbsDownIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.FeedbackNegative>
      <ActionBarMorePrimitive.Root>
        <ActionBarMorePrimitive.Trigger asChild>
          <TooltipIconButton
            tooltip="More"
            className="data-[state=open]:bg-accent"
          >
            <MoreHorizontalIcon />
          </TooltipIconButton>
        </ActionBarMorePrimitive.Trigger>
        <ActionBarMorePrimitive.Content
          side="bottom"
          align="start"
          className="aui-action-bar-more-content z-50 min-w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          <ActionBarPrimitive.ExportMarkdown asChild>
            <ActionBarMorePrimitive.Item className="aui-action-bar-more-item flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground">
              <DownloadIcon className="size-4" />
              Export as Markdown
            </ActionBarMorePrimitive.Item>
          </ActionBarPrimitive.ExportMarkdown>
        </ActionBarMorePrimitive.Content>
      </ActionBarMorePrimitive.Root>
    </ActionBarPrimitive.Root>
  )
}

const AssistantMeta: FC = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const selectedMetadata = useAuiState(({ message }) => message.metadata?.custom)
  const customMetadata = (selectedMetadata ?? EMPTY_MESSAGE_METADATA) as Record<string, any>
  const runId =
    customMetadata.run_id ||
    customMetadata.runId ||
    customMetadata.id ||
    customMetadata.runID ||
    ''
  const responseId = customMetadata.response_id ?? customMetadata.responseId ?? ''
  const taskId = customMetadata.task_id ?? customMetadata.taskId ?? ''
  const branchId = customMetadata.branch_id ?? customMetadata.branchId ?? ''
  const modelRef = customMetadata.model_ref ?? customMetadata.modelRef ?? ''
  const messageStatus = String(
    customMetadata.message_status ?? customMetadata.status ?? 'completed'
  ).toLowerCase()
  const tokensPrompt =
    customMetadata.tokens_prompt ??
    customMetadata.tokensPrompt ??
    null
  const tokensCompletion =
    customMetadata.tokens_completion ??
    customMetadata.tokensCompletion ??
    null
  const finishReason =
    customMetadata.finish_reason ??
    customMetadata.finishReason ??
    null
  const budgetExceeded =
    customMetadata.budget_exceeded ??
    customMetadata.budgetExceeded ??
    null
  const budgetReason =
    customMetadata.budget_reason ??
    customMetadata.budgetReason ??
    null
  const costTotal =
    customMetadata.cost_total ??
    customMetadata.costTotal ??
    null
  const hasTokens = tokensPrompt !== null || tokensCompletion !== null
  const hasBudget = budgetExceeded !== null || budgetReason !== null
  const hasCost = typeof costTotal === 'number'
  const totalTokens = (tokensPrompt ?? 0) + (tokensCompletion ?? 0)
  const toolCallCount = Array.isArray(customMetadata.tool_calls)
    ? customMetadata.tool_calls.length
    : typeof customMetadata.tool_calls === 'number'
      ? customMetadata.tool_calls
      : 0
  const statusKey = ['completed', 'succeeded', 'success'].includes(messageStatus)
    ? 'completed'
    : ['failed', 'error'].includes(messageStatus)
      ? 'failed'
      : ['cancelled', 'canceled'].includes(messageStatus)
        ? 'cancelled'
        : ['running', 'in_progress', 'pending'].includes(messageStatus)
          ? 'running'
          : 'unknown'
  const statusVariant = statusKey === 'completed'
    ? 'success'
    : statusKey === 'failed'
      ? 'destructive'
      : statusKey === 'running'
        ? 'info'
        : statusKey === 'cancelled'
          ? 'warning'
          : 'muted'
  const finishReasonKey = finishReason ? `chat.thread.run.finishReasons.${finishReason}` : ''
  const finishReasonTranslation = finishReasonKey ? t(finishReasonKey) : ''
  const finishReasonText = finishReason
    ? finishReasonTranslation !== finishReasonKey
      ? finishReasonTranslation
      : `${t('chat.thread.run.finishReasons._default')} (${finishReason})`
    : ''

  if (
    !runId && !responseId && !taskId && !modelRef && !branchId &&
    !hasTokens && !finishReason && !hasBudget && !hasCost && !toolCallCount
  ) {
    return null
  }

  return (
    <Collapsible className="ml-1 mt-2 max-w-2xl overflow-hidden rounded-lg border border-border/60 bg-muted/20 text-xs">
      <CollapsibleTrigger
        render={
          <button
            type="button"
            aria-label={t('chat.thread.run.panelTitle')}
            className="group flex min-h-10 w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-muted-foreground outline-none transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
          />
        }
      >
          <Activity className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
          <span className="min-w-0 flex-1 font-medium text-foreground">
            {t('chat.thread.run.panelTitle')}
          </span>
          {hasTokens ? (
            <span className="hidden tabular-nums sm:inline">
              {t('chat.thread.run.totalTokens', { total: totalTokens })}
            </span>
          ) : null}
          <Badge variant={statusVariant} className="h-5 px-1.5 py-0">
            {t(`chat.thread.run.status.${statusKey}`)}
          </Badge>
          <ChevronDownIcon
            className="size-3.5 shrink-0 transition-transform group-data-panel-open:rotate-180"
            aria-hidden="true"
          />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden border-t border-border/50">
        <div className="grid grid-cols-[minmax(5.5rem,auto)_minmax(0,1fr)] gap-x-4 gap-y-2 px-3 py-3 text-muted-foreground">
          {runId ? (
            <>
              <span>{t('chat.thread.run.fields.runId')}</span>
              <code className="break-all font-mono text-foreground">{runId}</code>
            </>
          ) : null}
          {responseId ? (
            <>
              <span>{t('chat.thread.run.fields.responseId')}</span>
              <code className="break-all font-mono text-foreground">{responseId}</code>
            </>
          ) : null}
          {taskId ? (
            <>
              <span>{t('chat.thread.run.fields.taskId')}</span>
              <code className="break-all font-mono text-foreground">{taskId}</code>
            </>
          ) : null}
          {modelRef ? (
            <>
              <span>{t('chat.thread.run.fields.model')}</span>
              <span className="break-all text-foreground">{modelRef}</span>
            </>
          ) : null}
          {branchId ? (
            <>
              <span>{t('chat.thread.run.fields.branch')}</span>
              <code className="break-all font-mono text-foreground">{branchId}</code>
            </>
          ) : null}
          {hasTokens ? (
            <>
              <span>{t('chat.thread.run.fields.usage')}</span>
              <span className="text-foreground">
                {t('chat.thread.run.tokens', {
                  prompt: tokensPrompt ?? 0,
                  completion: tokensCompletion ?? 0,
                  total: totalTokens,
                })}
              </span>
            </>
          ) : null}
          {toolCallCount ? (
            <>
              <span>{t('chat.thread.run.fields.tools')}</span>
              <span className="text-foreground">
                {t('chat.thread.run.toolCalls', { count: toolCallCount })}
              </span>
            </>
          ) : null}
          {finishReason ? (
            <>
              <span>{t('chat.thread.run.finishReasonLabel')}</span>
              <span className="text-foreground">{finishReasonText}</span>
            </>
          ) : null}
          {hasBudget ? (
            <>
              <span>{t('chat.thread.run.fields.governance')}</span>
              <span className={budgetExceeded ? 'text-destructive' : 'text-foreground'}>
                {t('chat.thread.run.budget', {
                  status: budgetExceeded ? t('chat.thread.run.budgetExceeded') : t('chat.thread.run.budgetOk'),
                  reason: budgetReason || '-',
                })}
              </span>
            </>
          ) : null}
          {hasCost ? (
            <>
              <span>{t('chat.thread.run.fields.cost')}</span>
              <span className="text-foreground">
                {t('chat.thread.run.cost', { cost: Number(costTotal).toFixed(4) })}
              </span>
            </>
          ) : null}
        </div>
        {runId ? (
          <div className="border-t border-border/50 px-2 py-1.5">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => navigate(`/observe/runs/${runId}`)}
            >
              <Activity className="mr-1 h-3 w-3" />
              {t('chat.thread.run.viewRun')}
            </Button>
          </div>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  )
}

const AssistantCitations: FC = () => {
  const { t } = useTranslation()
  const selectedMetadata = useAuiState(({ message }) => message.metadata?.custom)
  const customMetadata = (selectedMetadata ?? EMPTY_MESSAGE_METADATA) as Record<string, any>
  const citations = Array.isArray(customMetadata.citations) ? customMetadata.citations : []

  if (!citations.length) {
    return null
  }

  return (
    <div className="mt-2 rounded-md border border-border/50 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
      <div className="mb-2 font-medium text-foreground">{t('chat.thread.citations.title')}</div>
      <div className="space-y-2">
        {citations.map((citation: any, index: number) => {
          const source =
            citation.title ||
            citation.doc_key ||
            citation.document_id ||
            citation.chunk_id ||
            '-'
          const candidateUrl = citation.url || citation.source_uri
          const sourceUrl =
            typeof candidateUrl === 'string' && /^https?:\/\//i.test(candidateUrl)
              ? candidateUrl
              : ''
          return (
            <div key={`${citation.chunk_id || citation.document_id || index}`} className="space-y-1">
              <div className="flex flex-wrap gap-2">
                <span className="text-muted-foreground">#{index + 1}</span>
                {sourceUrl ? (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    {`${t('chat.thread.citations.source')}: ${source}`}
                  </a>
                ) : (
                  <span>{`${t('chat.thread.citations.source')}: ${source}`}</span>
                )}
                {citation.knowledge_id ? (
                  <span>{`${t('chat.thread.citations.knowledge')}: ${citation.knowledge_id}`}</span>
                ) : null}
              </div>
              {citation.snippet ? (
                <div className="line-clamp-2 text-muted-foreground">{citation.snippet}</div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const AssistantArtifacts: FC = () => {
  const { t } = useTranslation()
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const selectedMetadata = useAuiState(({ message }) => message.metadata?.custom)
  const customMetadata = (selectedMetadata ?? EMPTY_MESSAGE_METADATA) as Record<string, any>
  const artifacts = Array.isArray(customMetadata.artifacts) ? customMetadata.artifacts : []

  if (!artifacts.length) return null

  const download = async (artifact: Record<string, any>) => {
    const url = artifact.download_url
    if (!url) return
    setDownloadingId(String(artifact.id))
    try {
      await downloadGovernedFile(String(url), String(artifact.name || artifact.id || 'artifact'))
    } catch (error) {
      console.error('Failed to download Run artifact:', error)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="mt-2 rounded-md border border-border/50 bg-muted/40 px-3 py-2 text-xs">
      <div className="mb-2 font-medium text-foreground">{t('chat.thread.artifacts.title')}</div>
      <div className="space-y-2">
        {artifacts.map((artifact: any) => (
          <div key={artifact.id} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate font-medium text-foreground">{artifact.name || artifact.id}</div>
              <div className="text-muted-foreground">
                {artifact.mime || artifact.type || t('chat.thread.artifacts.file')}
                {typeof artifact.size_bytes === 'number'
                  ? ` · ${t('chat.thread.artifacts.bytes', { size: artifact.size_bytes })}`
                  : ''}
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!artifact.download_url || downloadingId === String(artifact.id)}
              aria-label={t('chat.thread.artifacts.download', { name: artifact.name || artifact.id })}
              onClick={() => void download(artifact)}
            >
              {downloadingId === String(artifact.id) ? (
                <Loader2Icon className="size-3.5 animate-spin" />
              ) : (
                <DownloadIcon className="size-3.5" />
              )}
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({ className, ...rest }) => {
  return (
    <BranchPickerPrimitive.Root hideWhenSingleBranch className={cn('text-muted-foreground inline-flex items-center text-xs', className)} {...rest}>
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  )
}

const CircleStopIcon: FC<React.SVGProps<SVGSVGElement>> = (props) => {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="16" height="16" {...props}>
      <rect width="10" height="10" x="3" y="3" rx="2" />
    </svg>
  )
}
