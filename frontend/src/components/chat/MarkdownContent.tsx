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
 * expand inline bullet items into discrete list rows, format key-value pairs,
 * and convert domain mentions into clickable markdown links.
 */
export function normalizeMarkdownContent(raw: string): string {
  if (!raw) return "";

  let text = raw;

  // 1. If text has inline bullets (e.g., "• item 1 • item 2 • item 3"), split them into discrete list items
  text = text.replace(/([^\n])\s*[•·]\s+/g, "$1\n- ");

  // 2. Turn leading unicode bullets on any line into standard markdown '- '
  text = text.replace(/^[\t ]*[•·]\s*/gm, "- ");

  // 3. If multiple bold key-values are grouped together on a line or without bullet points:
  // e.g., "**Destination & Region:** ... **Duration:** ... **Official Price:** ..."
  text = text.replace(/([^\n])\s+(\*\*[A-Z][a-zA-Z\s&/]+:\*\*)/g, "$1\n- $2");
  text = text.replace(/^(\*\*[A-Z][a-zA-Z\s&/]+:\*\*)/gm, "- $1");

  // 4. Convert parenthesized or backticked domain references to markdown links
  // e.g., (`itp.7scribes.com`) or ( itp.7scribes.com ) or (itp.7scribes.com)
  text = text.replace(/\(?`?(?:https?:\/\/)?(itp\.7scribes\.com(?:\/[^\s`\)]*)?)`?\)?/g, (match, urlPath) => {
    if (match.startsWith("[") || match.includes("](")) return match;
    const cleanUrl = urlPath.trim();
    const fullHref = cleanUrl.startsWith("http") ? cleanUrl : `https://${cleanUrl}`;
    return `[${cleanUrl}](${fullHref})`;
  });

  // 5. Ensure headings have a blank line before them
  text = text.replace(/([^\n])\n(#{1,4}\s+)/g, "$1\n\n$2");

  // 6. Ensure bullet lists have a blank line before them if preceded by a non-list line
  text = text.replace(/([^\n\-])\n(- )/g, "$1\n\n$2");

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
              className="text-lg font-bold text-humsafar-navy mt-4 mb-2 pb-1 border-b border-slate-200/80 tracking-tight"
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
          ul: ({ node, ...props }) => (
            <ul className="my-3 space-y-2 pl-1" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="my-3 space-y-2 pl-5 list-decimal text-slate-800 marker:font-semibold marker:text-humsafar-teal" {...props} />
          ),
          li: ({ node, children, ...props }) => (
            <li className="flex items-start gap-2.5 text-[14.5px] sm:text-[15px] leading-relaxed text-slate-700 my-1">
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
            <hr className="my-4 border-slate-200" {...props} />
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
