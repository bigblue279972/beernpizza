"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export interface BankrollSeriesPoint {
  date: Date | string;
  balance: number;
  label: string;
}

interface BankrollChartProps {
  series: BankrollSeriesPoint[];
  peak: number;
  hardStopLossPct: number;
  startingBalance: number;
}

interface TooltipPayloadEntry {
  dataKey: string;
  value: number;
  payload: { dateStr: string; balance: number; label: string };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs shadow-lg max-w-[240px]">
      <p className="font-medium text-[var(--text)] mb-0.5">{d.dateStr}</p>
      <p className="text-[var(--text-muted)] mb-1 truncate">{d.label}</p>
      <p className="text-[var(--text)] font-semibold tabular-nums">
        £{d.balance.toFixed(2)}
      </p>
    </div>
  );
}

export function BankrollChart({
  series,
  peak,
  hardStopLossPct,
  startingBalance,
}: BankrollChartProps) {
  if (series.length < 2) {
    return (
      <div className="flex flex-col items-center justify-center h-[400px] text-center">
        <p className="text-[var(--text-muted)] text-sm">No transaction history yet</p>
        <p className="text-[var(--text-muted)] text-xs mt-1">
          Deposit funds or settle bets to see your balance over time.
        </p>
      </div>
    );
  }

  const currentBalance = series[series.length - 1]?.balance ?? startingBalance;
  const isAboveStart = currentBalance >= startingBalance;
  const areaColor = isAboveStart ? "var(--green)" : "var(--red)";
  const stopLossFloor = peak * (1 - hardStopLossPct / 100);

  const chartData = series.map((pt) => {
    const d = new Date(pt.date);
    const isEpoch = d.getFullYear() === 1970 && d.getMonth() === 0 && d.getDate() === 1;
    const dateStr = isEpoch
      ? "Start"
      : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit" });
    return {
      dateStr,
      balance: pt.balance,
      label: pt.label,
    };
  });

  // Ticks: show at most ~8 evenly-spaced labels
  const maxTicks = 8;
  const step = Math.max(1, Math.floor(chartData.length / maxTicks));
  const tickIndices = new Set<number>();
  for (let i = 0; i < chartData.length; i += step) tickIndices.add(i);
  tickIndices.add(chartData.length - 1);

  const allBalances = chartData.map((d) => d.balance);
  const minBalance = Math.min(...allBalances, stopLossFloor, startingBalance);
  const maxBalance = Math.max(...allBalances, peak);
  const padding = (maxBalance - minBalance) * 0.08 || 50;

  return (
    <ResponsiveContainer width="100%" height={400}>
      <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <defs>
          <linearGradient id="bankrollAreaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={areaColor} stopOpacity={0.25} />
            <stop offset="95%" stopColor={areaColor} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} />
        <XAxis
          dataKey="dateStr"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
          interval={step - 1}
          angle={-25}
          textAnchor="end"
          height={40}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `£${v.toFixed(0)}`}
          width={70}
          domain={[minBalance - padding, maxBalance + padding]}
        />
        <Tooltip content={<CustomTooltip />} />
        {/* Starting balance reference line */}
        <ReferenceLine
          y={startingBalance}
          stroke="var(--text-muted)"
          strokeDasharray="5 5"
          opacity={0.6}
          label={{
            value: `Start £${startingBalance.toFixed(0)}`,
            position: "insideTopRight",
            fill: "var(--text-muted)",
            fontSize: 10,
          }}
        />
        {/* Hard stop-loss floor reference line */}
        <ReferenceLine
          y={stopLossFloor}
          stroke="var(--red)"
          strokeDasharray="4 4"
          opacity={0.8}
          label={{
            value: `Stop £${stopLossFloor.toFixed(0)} (-${hardStopLossPct}%)`,
            position: "insideBottomRight",
            fill: "var(--red)",
            fontSize: 10,
          }}
        />
        <Area
          type="monotone"
          dataKey="balance"
          stroke={areaColor}
          strokeWidth={2}
          fill="url(#bankrollAreaGradient)"
          dot={false}
          activeDot={{ r: 4, fill: areaColor, stroke: "var(--surface-2)", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
