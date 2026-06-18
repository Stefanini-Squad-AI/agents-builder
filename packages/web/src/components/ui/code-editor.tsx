'use client';

import { useCallback } from 'react';
import Editor from 'react-simple-code-editor';
import Prism from 'prismjs';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-sql';
import { cn } from '@/lib/utils';

// Map SkillResourceLanguage values to Prism language keys
const LANGUAGE_MAP: Record<string, string> = {
  markdown: 'markdown',
  yaml: 'yaml',
  python: 'python',
  sql: 'sql',
  plain: 'plain',
};

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  placeholder?: string;
  disabled?: boolean;
  minHeight?: string;
  maxHeight?: string;
  className?: string;
}

/**
 * Code editor component using react-simple-code-editor with Prism highlighting.
 */
export function CodeEditor({
  value,
  onChange,
  language = 'markdown',
  placeholder = '',
  disabled = false,
  minHeight = '200px',
  maxHeight = '500px',
  className,
}: CodeEditorProps) {
  const highlight = useCallback(
    (code: string) => {
      const prismLang = LANGUAGE_MAP[language] || 'plain';
      const grammar = Prism.languages[prismLang];
      
      if (grammar) {
        return Prism.highlight(code, grammar, prismLang);
      }
      // Fallback to plain text
      return code;
    },
    [language]
  );

  return (
    <div
      className={cn(
        'relative rounded-md border border-input bg-transparent',
        'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      <Editor
        value={value}
        onValueChange={onChange}
        highlight={highlight}
        placeholder={placeholder}
        disabled={disabled}
        padding={12}
        textareaClassName="focus:outline-none"
        style={{
          fontFamily: '"Fira Code", "Fira Mono", monospace',
          fontSize: 14,
          lineHeight: 1.5,
          minHeight,
          maxHeight,
          overflow: 'auto',
        }}
        className="code-editor-inner"
      />
      <style jsx global>{`
        .code-editor-inner {
          background: transparent !important;
        }
        .code-editor-inner textarea {
          background: transparent !important;
          caret-color: hsl(var(--foreground)) !important;
        }
        .code-editor-inner pre {
          background: transparent !important;
        }
        /* Prism theme overrides for our design */
        .code-editor-inner .token.comment { color: hsl(var(--muted-foreground)); }
        .code-editor-inner .token.string { color: hsl(142 76% 36%); }
        .code-editor-inner .token.number { color: hsl(200 98% 39%); }
        .code-editor-inner .token.keyword { color: hsl(271 81% 56%); }
        .code-editor-inner .token.function { color: hsl(200 98% 39%); }
        .code-editor-inner .token.operator { color: hsl(var(--foreground)); }
        .code-editor-inner .token.punctuation { color: hsl(var(--muted-foreground)); }
        .code-editor-inner .token.title { color: hsl(200 98% 39%); font-weight: bold; }
        .code-editor-inner .token.url { color: hsl(200 98% 39%); text-decoration: underline; }
        .code-editor-inner .token.code { color: hsl(142 76% 36%); font-family: monospace; }
        .code-editor-inner .token.bold { font-weight: bold; }
        .code-editor-inner .token.italic { font-style: italic; }
      `}</style>
    </div>
  );
}

export default CodeEditor;
