import type { FallbackDiagnostic } from "../../types/sync";

type Props = {
  rows: FallbackDiagnostic[];
};

export function FallbackDiagnosticsTable({ rows }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Demand Fallback Diagnostics</h2>
        <span>{rows.length} tracked structures</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Structure</th>
            <th>Demand Source</th>
            <th>Confidence</th>
            <th>Coverage</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.structure_id}>
              <td>{row.structure_name}</td>
              <td>{row.demand_source}</td>
              <td>{(row.confidence_score * 100).toFixed(0)}%</td>
              <td>{(row.coverage_pct * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
