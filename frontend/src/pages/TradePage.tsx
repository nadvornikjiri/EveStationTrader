import { useEffect, useState } from "react";

import { useOpportunityItems, useSourceSummaries, useTargets } from "../hooks/useTradeData";
import { ItemDetailPanel } from "../components/trade/ItemDetailPanel";
import { ItemOpportunityTable } from "../components/trade/ItemOpportunityTable";
import { SourceSummaryTable } from "../components/trade/SourceSummaryTable";
import { TradeControls } from "../components/trade/TradeControls";

export function TradePage() {
  const { data: targets } = useTargets();
  const [targetId, setTargetId] = useState<number | null>(null);
  const [sourceId, setSourceId] = useState<number | null>(null);

  useEffect(() => {
    if (!targetId && targets?.length) {
      setTargetId(targets[0].location_id);
    }
  }, [targetId, targets]);

  const summaries = useSourceSummaries(targetId);

  useEffect(() => {
    if (!sourceId && summaries.data?.length) {
      setSourceId(summaries.data[0].source_location_id);
    }
  }, [sourceId, summaries.data]);

  const items = useOpportunityItems(targetId, sourceId);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <span className="eyebrow">Trading Analysis</span>
          <h1>Regional Day Trader</h1>
        </div>
        <button className="refresh-button" onClick={() => summaries.refetch()}>
          Refresh
        </button>
      </header>
      <TradeControls />
      <SourceSummaryTable
        rows={summaries.data ?? []}
        selectedSourceId={sourceId}
        onSelectSource={setSourceId}
      />
      <div className="trade-lower-grid">
        <ItemOpportunityTable rows={items.data ?? []} />
        <ItemDetailPanel />
      </div>
    </div>
  );
}
