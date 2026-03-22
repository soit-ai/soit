import { useMemo } from 'react'
import {
  CompositeAttachmentAdapter,
  SimpleImageAttachmentAdapter,
  SimpleTextAttachmentAdapter,
  useLocalRuntime,
  WebSpeechSynthesisAdapter,
  type AssistantRuntime,
} from '@assistant-ui/react'
import { ChatAdapter } from './chat-adapter'

export type LocalRuntime = AssistantRuntime

export const localRuntime = ({ agentId = 'default' }: { agentId?: string }): LocalRuntime => {
  void agentId
  const adapters = useMemo(
    () => ({
      attachments: new CompositeAttachmentAdapter([
        new SimpleImageAttachmentAdapter(),
        new SimpleTextAttachmentAdapter(),
      ]),
      speech: new WebSpeechSynthesisAdapter(),
    }),
    []
  )

  const runtime = useLocalRuntime(ChatAdapter, { adapters }) as unknown as LocalRuntime

  return runtime
}
