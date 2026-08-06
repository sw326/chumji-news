"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { createArticleKey } from "@/lib/article-key";
import { useScraps } from "./ScrapProvider";
import type { Category, NewsScrapDraft } from "@/lib/types";

interface ParsedArticle {
  type: "article";
  emoji: string;
  title: string;
  description: string;
  sourceText: string;
  sourceUrl: string;
}

interface ParsedSection {
  type: "section";
  heading: string;
  items: ParsedBlock[];
}

interface ParsedParagraph {
  type: "paragraph";
  text: string;
}

interface ParsedHr {
  type: "hr";
}

interface ParsedList {
  type: "list";
  items: string[];
}

type ParsedBlock = ParsedArticle | ParsedParagraph | ParsedHr | ParsedList;
type ParsedNode = ParsedSection | ParsedArticle | ParsedParagraph | ParsedHr | ParsedList;

// Parse inline markdown — links, bold, #issue 링크
function parseInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  // Pattern: links [text](url) and **bold**
  const regex = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|(?<![\w/])#(\d+)(?!\w)/g;
  let last = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[1] !== undefined) {
      // Link
      parts.push(
        <a
          key={key++}
          href={match[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline underline-offset-2 hover:text-accent/80 break-all"
        >
          {match[1]}
        </a>
      );
    } else if (match[3] !== undefined) {
      // Bold
      parts.push(<strong key={key++} className="font-semibold">{match[3]}</strong>);
    } else if (match[4] !== undefined) {
      // #123 → GitHub issue link
      const issueNum = match[4];
      parts.push(
        <a
          key={key++}
          href={`https://github.com/sw326/openclaw-workspace/issues/${issueNum}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent font-medium hover:underline"
        >
          #{issueNum}
        </a>
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 ? parts[0] : parts;
}

// Parse a block of lines into article or paragraph
function parseBlock(lines: string[]): ParsedBlock {
  const text = lines.join("\n").trim();
  if (!text || text === "---") return { type: "hr" };

  // Try to parse as article block:
  // Line 1: [emoji? ] **Title** or emoji **Title**
  // Line 2: description text
  // Line 3+: [Source](url) or *source*
  const firstLine = lines[0]?.trim() ?? "";

  // Bold title: 🚀 **Title** (기존 방식)
  const boldMatch = firstLine.match(/^([\p{Emoji}\u{1F1E0}-\u{1F1FF}🇺-🇿]*\s*)\*\*([^*]+)\*\*/u);
  // Emoji-only title: 🚀 Title without bold (Haiku가 볼드 생략 시)
  const emojiOnlyMatch = firstLine.match(/^([\p{Emoji}]\s+)(.+)/u);
  // Block 내 링크 존재 여부 (article 식별 보조 신호)
  const hasLink = lines.some((l) => /^\[([^\]]+)\]\(([^)]+)\)/.test(l.trim()));

  const isArticle = boldMatch || (hasLink && emojiOnlyMatch);

  if (isArticle) {
    const emoji = boldMatch
      ? boldMatch[1].trim()
      : emojiOnlyMatch![1].trim();
    const title = boldMatch
      ? boldMatch[2].trim()
      : emojiOnlyMatch![2].replace(/\*\*/g, "").trim();
    const remaining = lines.slice(1);

    let description = "";
    let sourceText = "";
    let sourceUrl = "";

    for (const line of remaining) {
      const linkMatch = line.trim().match(/^\[([^\]]+)\]\(([^)]+)\)/);
      const italicSourceMatch = line.trim().match(/^\*([^*]+)\*/);
      if (linkMatch) {
        sourceText = linkMatch[1];
        sourceUrl = linkMatch[2];
      } else if (italicSourceMatch) {
        sourceText = italicSourceMatch[1];
      } else if (line.trim() && !line.startsWith("---")) {
        description += (description ? " " : "") + line.trim().replace(/\*\*/g, "");
      }
    }

    return { type: "article", emoji, title, description, sourceText, sourceUrl };
  }

  return { type: "paragraph", text };
}

function parseContent(content: string): ParsedNode[] {
  const lines = content.split("\n");
  const nodes: ParsedNode[] = [];
  let currentSection: ParsedSection | null = null;
  let currentList: ParsedList | null = null;
  let blockLines: string[] = [];

  function pushNode(node: ParsedNode) {
    if (currentSection) currentSection.items.push(node as ParsedBlock);
    else nodes.push(node);
  }

  function flushList() {
    if (!currentList) return;
    pushNode(currentList);
    currentList = null;
  }

  function flushBlock() {
    if (blockLines.length === 0) return;
    const nonEmpty = blockLines.filter((l) => l.trim());
    if (nonEmpty.length === 0) {
      blockLines = [];
      return;
    }
    const block = parseBlock(blockLines);
    pushNode(block);
    blockLines = [];
  }

  for (const line of lines) {
    // H1
    if (/^#\s/.test(line)) {
      flushBlock(); flushList();
      const text = line.replace(/^#+\s*/, "");
      if (currentSection) {
        nodes.push(currentSection);
        currentSection = null;
      }
      nodes.push({ type: "paragraph", text: `__H1__${text}` });
      continue;
    }
    // H2 — section header
    if (/^##\s/.test(line)) {
      flushBlock(); flushList();
      if (currentSection) nodes.push(currentSection);
      currentSection = { type: "section", heading: line.replace(/^#+\s*/, ""), items: [] };
      continue;
    }
    // H3
    if (/^###\s/.test(line)) {
      flushBlock(); flushList();
      const text = line.replace(/^#+\s*/, "");
      pushNode({ type: "paragraph", text: `__H3__${text}` });
      continue;
    }
    // List item (− or *)
    if (/^[-*]\s/.test(line)) {
      flushBlock();
      const item = line.replace(/^[-*]\s/, "");
      if (currentList) {
        currentList.items.push(item);
      } else {
        currentList = { type: "list", items: [item] };
      }
      continue;
    }
    // Non-list line — flush list if active
    if (currentList && line.trim()) {
      flushList();
    }
    // HR separator → flush block
    if (/^---+$/.test(line.trim())) {
      flushBlock();
      const hr: ParsedHr = { type: "hr" };
      if (currentSection) currentSection.items.push(hr);
      else nodes.push(hr);
      continue;
    }
    // Empty line → flush block
    if (!line.trim()) {
      flushBlock();
      continue;
    }
    blockLines.push(line);
  }

  flushBlock();
  flushList();
  if (currentSection) nodes.push(currentSection);

  return nodes;
}

// Render an article card
function ArticleCard({ article, postId, postDate, category }: {
  article: ParsedArticle;
  postId: string;
  postDate: string;
  category: Category;
}) {
  const router = useRouter();
  const { isScrapped, toggleScrap } = useScraps();
  const articleKey = createArticleKey(postId, article.sourceUrl, article.title);
  const saved = isScrapped(articleKey);

  async function handleScrap() {
    const draft: NewsScrapDraft = {
      article_key: articleKey,
      post_id: postId,
      post_date: postDate,
      category,
      emoji: article.emoji,
      title: article.title,
      description: article.description,
      source_text: article.sourceText,
      source_url: article.sourceUrl,
    };
    const result = await toggleScrap(draft);
    if (result === "login") router.push("/scraps");
  }

  return (
    <div className="relative rounded-xl border border-card-border bg-card/60 p-4 pr-12 hover:border-accent/30 hover:bg-card transition-all">
      <button
        type="button"
        onClick={() => void handleScrap()}
        aria-label={saved ? "스크랩 해제" : "기사 스크랩"}
        aria-pressed={saved}
        className={`absolute right-3 top-3 rounded-md p-2 transition-colors ${saved ? "bg-accent/10 text-accent" : "text-muted hover:bg-accent/10 hover:text-accent"}`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill={saved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" />
        </svg>
      </button>
      <div className="flex items-start gap-2">
        {article.emoji && (
          <span className="text-lg leading-none mt-0.5 shrink-0">{article.emoji}</span>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm leading-snug mb-1 break-words">
            {article.title}
          </h3>
          {article.description && (
            <p className="text-xs text-muted leading-relaxed mb-2 break-words">
              {article.description}
            </p>
          )}
          {article.sourceUrl && (
            <a
              href={article.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors font-medium"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              {article.sourceText || "출처 보기"}
            </a>
          )}
          {article.sourceText && !article.sourceUrl && (
            <span className="text-xs text-muted italic">{article.sourceText}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function renderBlock(block: ParsedBlock, index: number, postId: string, postDate: string, category: Category): React.ReactNode {
  if (block.type === "list") {
    return (
      <ul key={index} className="space-y-1 my-1">
        {block.items.map((item, j) => (
          <li key={j} className="flex gap-2 text-sm text-foreground leading-relaxed">
            <span className="text-muted mt-0.5 shrink-0">–</span>
            <span className="break-words min-w-0">{parseInline(item)}</span>
          </li>
        ))}
      </ul>
    );
  }
  if (block.type === "hr") {
    return <hr key={index} className="my-4 border-card-border" />;
  }
  if (block.type === "article") {
    return <ArticleCard key={index} article={block} postId={postId} postDate={postDate} category={category} />;
  }
  // paragraph
  const text = block.text;
  if (text.startsWith("__H1__")) {
    return (
      <h1 key={index} className="text-2xl font-bold mb-4 leading-tight break-words">
        {parseInline(text.slice(6))}
      </h1>
    );
  }
  if (text.startsWith("__H3__")) {
    return (
      <h3 key={index} className="text-base font-semibold mt-4 mb-2 break-words">
        {parseInline(text.slice(6))}
      </h3>
    );
  }
  return (
    <p key={index} className="text-sm text-muted leading-relaxed mb-2 break-words">
      {parseInline(text)}
    </p>
  );
}

export default function MarkdownRenderer({ content, postId, postDate, category }: {
  content: string;
  postId: string;
  postDate: string;
  category: Category;
}) {
  const nodes = parseContent(content);

  return (
    <div className="overflow-x-hidden break-words max-w-full space-y-3">
      {nodes.map((node, i) => {
        if (node.type === "section") {
          return (
            <section key={i} className="space-y-2.5">
              <h2 className="text-base font-semibold mt-2 mb-3 flex items-center gap-2">
                <span>{node.heading}</span>
                <span className="h-px flex-1 bg-card-border" />
              </h2>
              <div className="space-y-2.5">
                {node.items.map((block, j) => renderBlock(block, j, postId, postDate, category))}
              </div>
            </section>
          );
        }
        return renderBlock(node as ParsedBlock, i, postId, postDate, category);
      })}
    </div>
  );
}
