import React from 'react';
import { Button, Tooltip } from 'antd';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';
import { useClipboard } from 'use-clipboard-copy';
import { useTheme } from '@/components/theme-provider';
import { highlightCodeToHtml, plainCodeToHtml } from '@/lib/shiki';

// Add global styles
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
.shiki {
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
}
.shiki code {
  white-space: pre-wrap !important;
  word-break: break-all !important;
}
`

interface CodeBlockProps {
  language: string;
  value: string;
  className?: string;
  showLineNumbers?: boolean;
  showCopyButton?: boolean;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  language,
  value,
  className,
  showLineNumbers = true,
  showCopyButton = true,
}) => {
  const { theme } = useTheme();
  const clipboard = useClipboard();
  const [copied, setCopied] = React.useState(false);
  const [highlightedCode, setHighlightedCode] = React.useState<string>("");

  React.useEffect(() => {
    let active = true;
    const loadHighlightedCode = async () => {
      try {
        const html = await highlightCodeToHtml({
          code: value,
          language,
          showLineNumbers,
          theme: theme === "dark" ? "github-dark" : "github-light",
        });
        if (active) {
          setHighlightedCode(showLineNumbers ? `<style>${codeLineNumbersStyle}</style>${html}` : html);
        }
      } catch (error) {
        console.error("Failed to highlight code:", error);
        if (active) {
          setHighlightedCode(plainCodeToHtml(value));
        }
      }
    };

    void loadHighlightedCode();
    return () => {
      active = false;
    };
  }, [value, language, showLineNumbers, theme]);

  const handleCopy = () => {
    clipboard.copy(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`code-block-container relative ${className}`}>
      {showCopyButton && (
        <Tooltip title={copied ? 'Copied' : 'Copy code'}>
          <Button
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopy}
            type="text"
            size="small"
            className="absolute top-2 right-2 z-10 bg-black/20 hover:bg-black/40 text-white"
          />
        </Tooltip>
      )}
      <div className="p-4 relative">
        {highlightedCode ? (
          <div 
            className={`shiki-container w-full ${showLineNumbers ? 'shiki-with-line-numbers text-sm' : ''}`}
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
            <code className="text-sm">{value}</code>
          </pre>
        )}
      </div>
    </div>
  );
};

export default CodeBlock;
