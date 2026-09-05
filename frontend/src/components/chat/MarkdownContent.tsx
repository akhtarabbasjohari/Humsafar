"use client";

import React from "react";
import ReactMarkdown from "react-markdown";

interface MarkdownContentProps {
  content: string;
  isStreaming?: boolean;
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  isStreaming,
}) => {
  if (!content) return null;

  return (
    <div className="markdown-content text-[15px] sm:text-[15.5px] leading-[1.75] text-slate-800">
      <ReactMarkdown
        components={{
          h1: ({ node, ...props }) => (
            <h1
              className="text-lg font-bold text-humsafar-navy mt-4 mb-2 pb-1 border-b border-slate-200/80 tracking-tight"
              {...props}
            />
          ),
          h2: ({ node, ...props }) => (
            <h2
              className="text-base font-bold text-humsafar-navy mt-3.5 mb-1.5 flex items-center gap-1.5 tracking-tight"
              {...props}
            />
          ),
          h3: ({ node, ...props }) => (
            <h3
              className="text-sm sm:text-[14.5px] font-bold text-humsafar-navy mt-3 mb-1 tracking-tight"
              {...props}
            />
          ),
          p: ({ node, ...props }) => (
            <p className="my-2 leading-[1.75] text-slate-800" {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul className="my-2 space-y-1.5 pl-2" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="my-2 space-y-1.5 pl-5 list-decimal text-slate-800" {...props} />
          ),
          li: ({ node, children, ...props }) => (
            <li className="flex items-start gap-2 text-[14.5px] leading-relaxed text-slate-700">
              <span className="w-1.5 h-1.5 rounded-full bg-humsafar-teal mt-2 shrink-0" />
              <div className="flex-1 min-w-0">{children}</div>
            </li>
          ),
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-humsafar-navy" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic text-slate-700" {...props} />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="my-3 pl-3.5 py-2 border-l-2 border-humsafar-teal bg-humsafar-tealTint/50 rounded-r-lg text-sm text-slate-700 italic"
              {...props}
            />
          ),
          hr: ({ node, ...props }) => (
            <hr className="my-3 border-slate-200" {...props} />
          ),
          a: ({ node, ...props }) => (
            <a
              className="text-humsafar-teal hover:underline font-medium transition-colors"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          code: ({ node, ...props }) => (
            <code
              className="px-1.5 py-0.5 rounded bg-slate-100 text-xs font-mono text-humsafar-navy border border-slate-200"
              {...props}
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="streaming-cursor" />}
    </div>
  );
};
