"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

interface MarkdownContentProps {
  content: string;
  isStreaming?: boolean;
}

function extractText(node: any): string {
  if (node === null || node === undefined) return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node.props && node.props.children) return extractText(node.props.children);
  return "";
}

/**
 * Responsive Comparison Table (Rule 4):
 * On desktop/tablet (sm: and above), renders as a clean comparison table.
 * On mobile (< 640px), collapses into neat stacked cards with attribute-value rows
 * to eliminate cramped horizontal scrolling on small screens.
 */
const ResponsiveComparisonTable: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  try {
    const childrenArray = React.Children.toArray(children);
    let theadEl: any = null;
    let tbodyEl: any = null;

    for (const child of childrenArray) {
      if (React.isValidElement(child)) {
        if (child.type === "thead") theadEl = child;
        else if (child.type === "tbody") tbodyEl = child;
      }
    }

    // Extract headers
    const headers: string[] = [];
    if (theadEl && theadEl.props && theadEl.props.children) {
      const trs = React.Children.toArray(theadEl.props.children);
      for (const tr of trs) {
        if (React.isValidElement(tr) && (tr as any).props && (tr as any).props.children) {
          const ths = React.Children.toArray((tr as any).props.children);
          for (const th of ths) {
            headers.push(extractText(th).trim());
          }
        }
      }
    }

    // Extract rows
    const rows: string[][] = [];
    if (tbodyEl && tbodyEl.props && tbodyEl.props.children) {
      const trs = React.Children.toArray(tbodyEl.props.children);
      for (const tr of trs) {
        if (React.isValidElement(tr) && (tr as any).props && (tr as any).props.children) {
          const tds = React.Children.toArray((tr as any).props.children);
          const rowCells: string[] = [];
          for (const td of tds) {
            rowCells.push(extractText(td).trim());
          }
          if (rowCells.length > 0) {
            rows.push(rowCells);
          }
        }
      }
    }

    if (headers.length > 0 && rows.length > 0) {
      return (
        <div className="my-4 w-full">
          {/* Desktop & Tablet: Classic Comparison Table */}
          <div className="hidden sm:block overflow-hidden rounded-xl border border-slate-200/90 shadow-2xs bg-white">
            <table className="w-full text-left text-xs sm:text-[13px] border-collapse">
              <thead className="bg-humsafar-navy text-white text-xs font-semibold uppercase tracking-wider">
                <tr>
                  {headers.map((h, i) => (
                    <th key={i} className="px-3.5 py-2.5 font-semibold text-white tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-50/70 transition-colors">
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className={clsx(
                          "px-3.5 py-2.5 text-slate-700",
                          cIdx === 0 && "font-semibold text-humsafar-navy"
                        )}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile: Responsive Stacked Cards (no horizontal scroll) */}
          <div className="block sm:hidden space-y-2.5">
            {rows.map((row, rIdx) => (
              <div
                key={rIdx}
                className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-2"
              >
                <div className="font-bold text-sm text-humsafar-navy pb-1.5 border-b border-slate-100 flex items-center justify-between">
                  <span>{row[0] || `Option ${rIdx + 1}`}</span>
                  <span className="text-[10px] font-semibold text-humsafar-teal bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200/60">
                    Option {rIdx + 1}
                  </span>
                </div>
                <div className="space-y-1.5 pt-0.5">
                  {headers.slice(1).map((header, hIdx) => {
                    const cellVal = row[hIdx + 1];
                    if (!cellVal) return null;
                    return (
                      <div key={hIdx} className="flex items-start justify-between gap-2 text-xs">
                        <span className="text-slate-500 font-medium shrink-0">{header}:</span>
                        <span className="text-slate-800 font-semibold text-right">{cellVal}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }
  } catch (err) {
    console.warn("Table parsing fallback:", err);
  }

  // Graceful fallback if custom AST extraction fails
  return (
    <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-xs sm:text-sm border-collapse">{children}</table>
    </div>
  );
};

export const MarkdownContent: React.FC<MarkdownContentProps> = ({
  content,
  isStreaming,
}) => {
  if (!content) return null;

  return (
    <div className="markdown-content text-[15px] sm:text-[15.5px] leading-[1.75] text-slate-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ node, ...props }) => <ResponsiveComparisonTable {...props} />,
          thead: ({ node, ...props }) => (
            <thead className="bg-humsafar-navy text-white text-xs font-semibold" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody className="divide-y divide-slate-100 bg-white" {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="hover:bg-slate-50/70 transition-colors" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="px-3 py-2 font-semibold text-white tracking-wide" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="px-3 py-2 text-slate-700" {...props} />
          ),
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

