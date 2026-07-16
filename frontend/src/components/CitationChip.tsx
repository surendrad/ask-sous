import { Wrench } from "lucide-react";

import { StatusTag } from "@/components/StatusTag";

type CitationChipProps = {
  toolName: string;
  hasError?: boolean;
};

/** Citation chip per design-guidelines.md §8 — the "info" tag variant is
 * reserved specifically for tool-call/grounding evidence, kept visually
 * distinct from any "AI generated" styling, per the same "no naked
 * numbers" discipline the backend enforces. */
export function CitationChip({
  toolName,
  hasError = false,
}: CitationChipProps) {
  return (
    <StatusTag variant={hasError ? "error" : "info"}>
      <Wrench size={12} />
      {toolName}
      {hasError ? " (error)" : ""}
    </StatusTag>
  );
}
