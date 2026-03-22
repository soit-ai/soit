"use client"

import * as React from "react"
import { Copy, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { createHighlighter, type Highlighter } from "shiki"
import { useTheme } from '@/components/theme-provider'

// Global styles for line numbers.
const codeLineNumbersStyle = `
.shiki-with-line-numbers .line {
  position: relative;
  padding-left: 1rem;
  counter-increment: line;
}

.shiki-with-line-numbers .line::before {
  content: counter(line);
  position: absolute;
  left: -2rem;
  width: 1.5rem;
  text-align: right;
  color: var(--tw-prose-captions);
  opacity: 0.5;
  font-size: 0.75rem;
  user-select: none;
}
.shiki.github-dark {
  background-color: hsl(var(--muted-foreground) / 0.7) !important;
}
.shiki.github-light {
  background-color: hsl(var(--muted-foreground) / 0.7) !important;
}
/* Enable code wrapping */
.shiki {
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
}
.shiki code {
  white-space: pre-wrap !important;
  word-break: break-all !important;
}
`

interface CodeboxProps {
  language?: string
  code: string
  className?: string
  showLineNumbers?: boolean
}

export function Codebox({
  language = "text",
  code,
  className,
  showLineNumbers = false,
}: CodeboxProps) {
  const { theme } = useTheme()
  const [copied, setCopied] = React.useState(false)
  const [highlighter, setHighlighter] = React.useState<Highlighter | null>(null)
  const [highlightedCode, setHighlightedCode] = React.useState<string>("") 

  React.useEffect(() => {
    const loadHighlighter = async () => {
      try {
        const highlighter = await createHighlighter({
          themes: ["github-dark", "github-light"],
          langs: [language],
        })
        setHighlighter(highlighter)
      } catch (error) {
        console.error("Failed to load highlighter:", error)
      }
    }
    
    loadHighlighter()
  }, [language])

  React.useEffect(() => {
    if (highlighter) {
      try {
        const _theme = theme === "dark" ? "github-dark" : "github-light"
        const html = highlighter.codeToHtml(code, { 
          lang: language, 
          theme: _theme,
          transformers: showLineNumbers ? [
            {
              line(element, index) {
                element.properties["class"] = "line"
                // Use index + 1 to keep line numbers 1-based.
                element.properties["line-number"] = String(index + 1)
                return element
              }
            }
          ] : undefined
        })
        // Add line number styles when enabled.
        const htmlWithStyle = showLineNumbers 
          ? `<style>${codeLineNumbersStyle}</style>${html}` 
          : html
        setHighlightedCode(htmlWithStyle)
      } catch (error) {
        console.error("Failed to highlight code:", error)
        // Fall back to plain text rendering.
        setHighlightedCode(`<pre><code>${code}</code></pre>`)
      }
    }
  }, [highlighter, code, language, showLineNumbers, theme])

  const copyToClipboard = React.useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [code])

  return (
    <div className={cn("rounded-lg border overflow-hidden relative", className)}>
      <div className="flex items-center justify-between px-4 py-2 bg-muted/50 border-b">
        <div className="text-sm font-medium text-muted-foreground">
          {language.toUpperCase()}
        </div>
        <button
          type="button"
          onClick={copyToClipboard}
          className="p-1 rounded-md hover:bg-muted transition-colors"
          aria-label={"Copy Code"}
        >
          {copied ? (
            <Check className="h-4 w-4 text-green-500" />
          ) : (
            <Copy className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      </div>
      <div className="p-4 relative">
        {highlighter ? (
          <div 
            className={cn(
              "shiki-container w-full", 
              showLineNumbers && "shiki-with-line-numbers text-sm"
            )}
            dangerouslySetInnerHTML={{ __html: highlightedCode }} 
            style={{
              position: 'relative',
              ...(showLineNumbers && {
                paddingLeft: '3rem',
              }),
            }}
          />
        ) : (
          <pre>
            <code className="text-sm">{code}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
