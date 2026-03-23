"use client";

import { Category, CATEGORY_LABELS, CATEGORIES } from "@/lib/types";

interface CategoryTabsProps {
  selected: Category | "all";
  onChange: (cat: Category | "all") => void;
}

export default function CategoryTabs({
  selected,
  onChange,
}: CategoryTabsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      <TabButton
        label="전체"
        active={selected === "all"}
        onClick={() => onChange("all")}
      />
      {CATEGORIES.map((cat) => (
        <TabButton
          key={cat}
          label={CATEGORY_LABELS[cat]}
          active={selected === cat}
          onClick={() => onChange(cat)}
        />
      ))}
    </div>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-accent text-white"
          : "bg-card text-muted border border-card-border hover:bg-accent-light hover:text-accent"
      }`}
    >
      {label}
    </button>
  );
}
