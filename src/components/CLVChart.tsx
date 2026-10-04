"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export interface ChartData {
  betIndex: number;
  cumulativeAvgClvPct: number;
  clvPct: number;
  event: string;
}

interface CLVChartProps {
  data: ChartData[];
}

interface TooltipPayloadEntry {
  dataKey: string;
  value: number;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: number;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const eventName = (payload[0] as unknown as { payload: ChartData })?.payload?.event ?? "";
  const clvEntry = payload.find((p) => p.dataKey === "clvPct");
  const cumEntry = payload.find((p) => p.dataKey === "cumulativeAvgClvPct");

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-[var(--text)] mb-1">Bet #{label}</p>
      {eventName && (
        <p className="text-[var(--text-muted)] mb-1 max-w-[200px] truncate">{eventName}</p>
      )}
      {clvEntry && (
        <p style={{ color: clvEntry.color }}>
          CLV: {clvEntry.value > 0 ? "+" : ""}
          {clvEntry.value.toFixed(2)}%
        </p>
      )}
      {cumEntry && (
        <p style={{ color: cumEntry.color }}>
          Avg CLV: {cumEntry.value > 0 ? "+" : ""}
          {cumEntry.value.toFixed(2)}%
        </p>
      )}
    </div>
  );
}

export function CLVChart({ data }: CLVChartProps) {
  if (data.length < 5) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <p className="text-[var(--text-muted)] text-sm">Not enough data</p>
        <p className="text-[var(--text-muted)] text-xs mt-1">
          Log at least 5 settled bets with closing prices to see your CLV chart.
        </p>
      </div>
    );
  }

  const finalCumAvg = data[data.length - 1]?.cumulativeAvgClvPct ?? 0;
  const lineColor = finalCumAvg >= 0 ? "var(--green)" : "var(--red)";

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
        <XAxis
          dataKey="betIndex"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
          label={{ value: "Bet #", position: "insideBottomRight", offset: -4, fill: "var(--text-muted)", fontSize: 11 }}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
          width={56}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="var(--text-muted)" strokeDasharray="4 4" opacity={0.6} />
        <Line
          type="monotone"
          dataKey="clvPct"
          stroke="var(--text-muted)"
          strokeWidth={1}
          dot={false}
          opacity={0.4}
          name="clvPct"
        />
        <Line
          type="monotone"
          dataKey="cumulativeAvgClvPct"
          stroke={lineColor}
          strokeWidth={2.5}
          dot={false}
          name="cumulativeAvgClvPct"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
