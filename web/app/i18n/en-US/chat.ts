const chat = {
  // Date grouping in chat list.
  dateGroups: {
    today: 'Today',
    yesterday: 'Yesterday',
    lastThreeDays: 'Last 3 Days',
    lastWeek: 'Last Week',
    loadMore: 'Load More',
    loading: 'Loading...',
    rename: 'Rename',
    delete: 'Delete',
    archive: 'Archive',
    unarchive: 'Unarchive',
  },
  custom: 'Customization',
  upgradeTip: {
    prefix: 'Upgrade your plan to',
    suffix: 'customize your brand.',
  },
  webapp: {
    title: 'Customize WebApp brand',
    removeBrand: 'Remove Powered by Soit',
    changeLogo: 'Change Powered by Brand Image',
    changeLogoTip: 'SVG or PNG format with a minimum size of 40x40px',
  },
  app: {
    title: 'Customize agent chat header brand',
    changeLogoTip: 'SVG or PNG format with a minimum size of 80x80px',
  },
  upload: 'Upload',
  uploading: 'Uploading',
  uploadedFail: 'Image upload failed, please re-upload.',
  change: 'Change',
  apply: 'Apply',
  restore: 'Restore Defaults',
  customize: {
    contactUs: ' contact us ',
    prefix: 'To customize the brand logo within the agent chat workspace, please',
    suffix: 'to upgrade to the Enterprise edition.',
  },
  sidebar: {
    newChat: 'New Chat',
    search: 'Type to search...',
    noConversations: 'No conversations yet',
    defaultTitle: 'New Chat',
    untitled: 'Untitled Chat',
    deleteConfirmTitle: 'Delete conversation?',
    deleteConfirmDescription: 'This will permanently delete "{{name}}".',
    toast: {
      renameError: 'Failed to rename conversation',
      deleteSuccess: 'Conversation deleted',
      deleteError: 'Failed to delete conversation',
    },
    filter: {
      label: 'Filter',
      all: 'All',
      active: 'Active',
      archived: 'Archived',
    },
  },
  header: {
    defaultTitle: 'New Chat',
    share: 'Share conversation',
    shareCopied: 'Share link copied',
    shareCopyFailed: 'Unable to copy share link',
    shareEmpty: 'Start a conversation to share',
    refresh: 'Refresh conversation',
    info: 'Conversation info',
  },
  thread: {
    scrollToBottom: 'Scroll to bottom',
    assistant: {
      title: 'SOIT AI Assistant',
      description: 'Your intelligent assistant, always ready to provide help and creativity',
      disclaimer: 'SOIT AI Assistant | Intelligently generated content · Please follow usage guidelines',
      capabilities: {
        multimodal: 'Multimodal capabilities',
        codeGeneration: 'Code generation',
        webSearch: 'Web search'
      },
      suggestions: {
        title: 'You can try the following conversations',
        items: {
          reactComponent: {
            title: 'Help me write a simple React component',
            prompt: 'Help me write a simple React component for displaying a user profile card, including avatar, username, bio, and follow button'
          },
          imageDescription: {
            title: 'Describe this image',
            prompt: 'Describe the content and theme of this image'
          },
          aiResearch: {
            title: 'Find the latest advances in artificial intelligence',
            prompt: 'Find the latest advances and applications in artificial intelligence'
          },
          creativeWriting: {
            title: 'Creative writing: Future technology',
            prompt: 'Please help me write a short article about how future technology will change human life'
          }
        }
      }
    },
    composer: {
      placeholder: 'Send a message to the current agent...',
      tabCompletion: 'Press',
      tab: 'Tab',
      complete: 'to complete',
      editPrevious: 'Edit previous message',
      deepThinking: 'Deep thinking',
      webSearch: 'Web search',
      codeMode: 'Code mode',
      multimodalHint: 'SOIT AI Assistant | Intelligently generated content · Please follow usage guidelines',
      send: 'Send message',
      cancel: 'Cancel generation',
      tooltips: {
        deepThinking: 'Enable deep thinking mode for more detailed answers',
        webSearch: 'Allow AI assistant to search the internet for the latest information',
        codeMode: 'Optimize code generation and explanation capabilities'
      }
    },
    userLabel: 'You',
    run: {
      viewRun: 'View run details',
      tokens: 'Tokens: prompt {{prompt}} · completion {{completion}} · total {{total}}',
      finishReasonLabel: 'Finish reason',
      finishReasons: {
        stop: 'Stop',
        length: 'Length',
        content_filter: 'Content filter',
        null: '—',
        _default: 'Other',
      },
    },
    citations: {
      title: 'Citations',
      empty: 'No citations',
      source: 'Source',
      knowledge: 'Knowledge',
    },
  },
}

export default chat
