"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { ExternalLink } from "lucide-react";

interface MarkdownContentProps {
  content: string;
  isStreaming?: boolean;
}

/**
 * Preprocesses raw AI or template markdown text to normalize unicode bullets,
 * strip erroneous bullets from headings, unpack inline bullet lists,
 * and convert domain mentions into clickable markdown links.
 */
export function normalizeMarkdownContent(raw: string): string {
  if (!raw) return "";

  let text = raw;

  // 1. Strip any leading bullet or dash before Markdown headings (e.g. "- ## Heading" or "- 🌄 ## Heading")
  text = text.replace(/^[\t ]*[-*•·]\s*(#{1,6}\s+)/gm, "$1");
  text = text.replace(/^[\t ]*[-*•·]\s*([^\n#]*#{1,6}\s+)/gm, "$1");
  text = text.replace(/^[\t ]*[-*•·]\s*(#{1,6}[^\n]+)/gm, "$1");

  // 2. Remove standalone empty bullet lines (e.g. lines with just "•" or "-")
  text = text.replace(/^[\t ]*[-*•·]\s*$/gm, "");

  // 3. If text has inline bullets (e.g., "• item 1 • item 2 • item 3"), split them into discrete list items
  text = text.replace(/([^\n])\s*[•·]\s+/g, "$1\n- ");

  // 4. Turn leading unicode bullets on non-heading lines into standard markdown '- '
  text = text.replace(/^[\t ]*[•·]\s+/gm, "- ");

  // 5. If multiple bold key-values are packed onto a single line without newlines, split them
  text = text.replace(/([^\n])\s+(\*\*[A-Z][a-zA-Z\s&/]+:\*\*)/g, "$1\n\n$2");

  // 6. Convert parenthesized or backticked domain references to markdown links
  // e.g., (`itp.7scribes.com`) or ( itp.7scribes.com ) or (itp.7scribes.com)
  text = text.replace(/\(?`?(?:https?:\/\/)?(itp\.7scribes\.com(?:\/[^\s`\)]*)?)`?\)?/g, (match, urlPath) => {
    if (match.startsWith("[") || match.includes("](")) return match;
    const cleanUrl = urlPath.trim();
    const fullHref = cleanUrl.startsWith("http") ? cleanUrl : `https://${cleanUrl}`;
    return `[${cleanUrl}](${fullHref})`;
  });

  // 7. Ensure headings have a blank line before them
  text = text.replace(/([^\n])\n(#{1,4}\s+)/g, "$1\n\n$2");

  // 8. Ensure tables have a blank line before and after them
  text = text.replace(/([^\n])\n(\|.+?\|)/g, "$1\n\n$2");

  return text.trim();
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  isStreaming,
}) => {
  const normalized = useMemo(() => normalizeMarkdownContent(content), [content]);

  if (!normalized) return null;

  return (
    <div className="markdown-content text-[15px] sm:text-[15.5px] leading-[1.75] text-slate-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          h1: ({ node, ...props }) => (
            <h1
              className="text-lg font-bold text-humsafar-navy mt-5 mb-2 pb-1 border-b border-slate-200/80 tracking-tight"
              {...props}
            />
          ),
          h2: ({ node, ...props }) => (
            <h2
              className="text-base font-bold text-humsafar-navy mt-4 mb-2 flex items-center gap-1.5 tracking-tight"
              {...props}
            />
          ),
          h3: ({ node, ...props }) => (
            <h3
              className="text-sm sm:text-[14.5px] font-bold text-humsafar-navy mt-3.5 mb-1.5 tracking-tight"
              {...props}
            />
          ),
          p: ({ node, ...props }) => (
            <p className="my-2.5 leading-[1.75] text-slate-800" {...props} />
          ),
          // Word / docx format hanging-indent bullet lists
          ul: ({ node, ...props }) => (
            <ul className="my-3 ml-6 space-y-1.5 list-disc marker:text-humsafar-teal text-slate-700 leading-relaxed" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="my-3 ml-6 space-y-1.5 list-decimal marker:text-humsafar-teal marker:font-semibold text-slate-700 leading-relaxed" {...props} />
          ),
          li: ({ node, children, ...props }) => {
            if (!children || (typeof children === "string" && !children.trim())) return null;
            return (
              <li className="pl-1 text-[14.5px] sm:text-[15px] leading-relaxed text-slate-700" {...props}>
                {children}
              </li>
            );
          },
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-humsafar-navy" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic text-slate-700" {...props} />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="my-3.5 pl-4 py-2.5 border-l-2 border-humsafar-teal bg-humsafar-tealTint/50 rounded-r-lg text-sm text-slate-700 italic"
              {...props}
            />
          ),
          hr: ({ node, ...props }) => (
            <hr className="my-4 border-slate-200" {...props} />
          ),
          // Beautiful responsive table components
          table: ({ node, ...props }) => (
            <div className="w-full my-4 overflow-x-auto rounded-xl border border-slate-200/90 shadow-subtle bg-white">
              <table className="w-full border-collapse text-left text-[13px] sm:text-[13.5px]" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-slate-50/90 border-b border-slate-200 text-humsafar-navy font-bold text-xs uppercase tracking-wider" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody className="divide-y divide-slate-100 bg-white" {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="hover:bg-slate-50/60 transition-colors" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="px-4 py-3 font-semibold text-humsafar-navy whitespace-nowrap" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="px-4 py-3 text-slate-700 leading-relaxed align-top" {...props} />
          ),
          a: ({ node, href, children, ...props }) => {
            const isExternal = typeof href === "string" && (href.startsWith("http") || href.startsWith("//"));
            return (
              <a
                href={href}
                className="inline-flex items-center gap-1 font-semibold text-humsafar-teal hover:text-teal-700 underline underline-offset-2 transition-colors cursor-pointer"
                target={isExternal ? "_blank" : undefined}
                rel={isExternal ? "noopener noreferrer" : undefined}
                {...props}
              >
                <span>{children}</span>
                {isExternal && <ExternalLink className="w-3 h-3 shrink-0 opacity-80 inline" />}
              </a>
            );
          },
          code: ({ node, ...props }) => (
            <code
              className="px-1.5 py-0.5 rounded bg-slate-100 text-xs font-mono text-humsafar-navy border border-slate-200"
              {...props}
            />
          ),
        }}
      >
        {normalized}
      </ReactMarkdown>
      {isStreaming && <span className="streaming-cursor" />}
    </div>
  );
};
