"use client";

import { ACTIVE_CATEGORIES, Category, CATEGORY_LABELS } from "@/lib/types";

interface CategoryTabsProps {
  selected: Category | "all";
  onChange: (cat: Category | "all") => void;
}

export default function CategoryTabs({
  selected,
  onChange,
}: CategoryTabsProps) {
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
      <TabButton
        label="전체"
        active={selected === "all"}
        onClick={() => onChange("all")}
      />
      {ACTIVE_CATEGORIES.map((cat) => (
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
      className={`whitespace-nowrap rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors ${
        active
          ? "bg-accent text-white"
          : "bg-card text-muted border border-card-border hover:border-accent/40 hover:text-accent"
      }`}
    >
      {label}
    </button>
  );
}
