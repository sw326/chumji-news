/** Simple markdown-to-HTML renderer (no external dependency) */
export default function MarkdownRenderer({ content }: { content: string }) {
  const html = markdownToHtml(content);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

function markdownToHtml(md: string): string {
  return md
    .split("\n\n")
    .map((block) => {
      block = block.trim();
      if (!block) return "";

      // Headings
      if (block.startsWith("### "))
        return `<h3>${inline(block.slice(4))}</h3>`;
      if (block.startsWith("## ")) return `<h2>${inline(block.slice(3))}</h2>`;
      if (block.startsWith("# ")) return `<h1>${inline(block.slice(2))}</h1>`;

      // HR
      if (/^-{3,}$/.test(block)) return "<hr />";

      // Unordered list
      if (block.match(/^[-*] /m)) {
        const items = block
          .split("\n")
          .filter((l) => l.match(/^[-*] /))
          .map((l) => `<li>${inline(l.replace(/^[-*] /, ""))}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }

      // Ordered list
      if (block.match(/^\d+\. /m)) {
        const items = block
          .split("\n")
          .filter((l) => l.match(/^\d+\. /))
          .map((l) => `<li>${inline(l.replace(/^\d+\. /, ""))}</li>`)
          .join("");
        return `<ol>${items}</ol>`;
      }

      // Paragraph
      return `<p>${inline(block.replace(/\n/g, "<br />"))}</p>`;
    })
    .join("\n");
}

function inline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}
