import { Copy, Megaphone, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";

import { CitationChip } from "@/components/CitationChip";
import { StatusTag } from "@/components/StatusTag";
import { Button } from "@/components/ui/button";
import type { CampaignResult } from "@/lib/api";
import { generateCampaign } from "@/lib/api";

type CampaignsPanelProps = {
  restaurantId: string;
  isMultipleSelected?: boolean;
};

/** Campaigns panel — the right panel in the split view per
 * design-guidelines.md §5/§11: a brief input, a Generate action, and a
 * stacked campaign-draft card with Regenerate + Copy actions. Unlike
 * ChatPage, /campaigns is a plain single response, not streamed — see
 * docs/decisions/011 for why that's a deliberate non-goal for this
 * endpoint. Generation is agentic though (docs/decisions/016): the model
 * may call the same tools chat uses (e.g. get_weekday_performance) before
 * writing copy that references real data, and any tools it called render
 * as citation chips under the draft, same as chat's grounding evidence.
 * Campaign generation stays single-location by design (Phase 8): brand
 * voice and copy are generated per-restaurant, so when the sidebar has
 * more than one location selected, this panel disables Generate and
 * prompts the owner to narrow the selection rather than guessing which
 * location to generate for. */
export default function CampaignsPanel({
  restaurantId,
  isMultipleSelected = false,
}: CampaignsPanelProps) {
  const [brief, setBrief] = useState("");
  const [submittedBrief, setSubmittedBrief] = useState<string | null>(null);
  const [draft, setDraft] = useState<CampaignResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function runGenerate(effectiveBrief: string) {
    setIsLoading(true);
    setError(null);
    setCopied(false);
    try {
      const result = await generateCampaign(restaurantId, effectiveBrief);
      setDraft(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate a campaign.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleGenerate() {
    if (isMultipleSelected) return;
    const trimmed = brief.trim();
    if (!trimmed) return;
    setSubmittedBrief(trimmed);
    await runGenerate(trimmed);
  }

  async function handleRegenerate() {
    if (!submittedBrief) return;
    await runGenerate(submittedBrief);
  }

  async function handleCopy() {
    if (!draft) return;
    await navigator.clipboard.writeText(draft.copy_text);
    setCopied(true);
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <Megaphone size={18} className="text-brand" />
        <h2 className="font-display text-[23px] font-semibold leading-[30px]">
          Campaigns
        </h2>
      </div>

      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void handleGenerate();
        }}
      >
        <input
          className="flex-1 rounded-md border border-border-strong bg-elevated px-3 py-2 text-sm text-text outline-none focus:border-brand"
          placeholder="What's the campaign about?"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
        />
        <Button type="submit" disabled={isLoading || isMultipleSelected}>
          Generate
        </Button>
      </form>

      {isMultipleSelected && (
        <StatusTag variant="warning">
          Select exactly one location to generate a campaign.
        </StatusTag>
      )}

      {error && <StatusTag variant="error">{error}</StatusTag>}

      {!draft && !isLoading && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-strong p-8 text-center">
          <Sparkles size={24} className="text-brand" />
          <p className="text-sm text-text-muted">
            No campaign draft yet — describe what you want below.
          </p>
        </div>
      )}

      {isLoading && <p className="text-sm text-text-muted">Generating…</p>}

      {draft && !isLoading && (
        <div className="rounded-lg border border-border bg-elevated p-4 shadow-e1">
          <p className="text-sm leading-[22px] text-text">{draft.copy_text}</p>
          {draft.tool_calls.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {draft.tool_calls.map((tc, i) => (
                <CitationChip
                  // biome-ignore lint/suspicious/noArrayIndexKey: tool calls carry no id from the API and this list is fixed once a draft finishes generating
                  key={`${tc.tool_name}-${i}`}
                  toolName={tc.tool_name}
                  hasError={!!tc.error}
                />
              ))}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => void handleRegenerate()}
            >
              <RefreshCw size={14} />
              Regenerate
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleCopy()}
            >
              <Copy size={14} />
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
