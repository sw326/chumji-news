"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold mb-4 leading-tight">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-xl font-semibold mt-6 mb-3">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="text-muted text-sm">{children}</em>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline underline-offset-2 hover:text-accent/80 transition-colors"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-6 mb-3 space-y-1">{children}</ul>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  p: ({ children }) => (
    <p className="mb-3 leading-7">{children}</p>
  ),
  hr: () => (
    <hr className="my-6 border-card-border" />
  ),
};

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="prose overflow-x-hidden break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
