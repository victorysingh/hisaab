"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { num, rupees, rupeesShort, shortDate, type Forecast } from "@/lib/api";

const TEAL = "#0f766e";
const RED = "#dc2626";
const AMBER = "#d97706";

type Point = {
  label: string;
  band: [number, number];
  likely: number;
  scenario?: number;
};

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-sm">
      <div className="font-medium">{p.label}</div>
      <div style={{ color: TEAL }}>Likely: {rupees(p.likely)}</div>
      {p.scenario !== undefined && <div style={{ color: AMBER }}>What-if: {rupees(p.scenario)}</div>}
      <div className="text-muted-foreground">
        Range: {rupees(p.band[0])} to {rupees(p.band[1])}
      </div>
    </div>
  );
}

/** Best-worst band, likely line, safety buffer, shortfall marker, optional what-if line. */
export function ForecastChart({ base, scenario }: { base: Forecast; scenario?: Forecast | null }) {
  const data: Point[] = base.days.map((d, i) => ({
    label: shortDate(d.date),
    band: [num(d.worst), num(d.best)],
    likely: num(d.likely),
    scenario: scenario?.days[i] ? num(scenario.days[i].likely) : undefined,
  }));
  const shown = scenario ?? base;
  const shortfall = shown.shortfall;
  const shortfallPoint = shortfall ? data.find((p) => p.label === shortDate(shortfall.date)) : undefined;
  const buffer = num(base.safety_buffer);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11 }}
            interval={Math.max(0, Math.ceil(data.length / 6) - 1)}
            tickLine={false}
          />
          <YAxis
            tickFormatter={rupeesShort}
            tick={{ fontSize: 11 }}
            width={52}
            tickLine={false}
            axisLine={false}
            domain={[(min: number) => Math.min(0, Math.floor((min * 1.25) / 5000) * 5000), "auto"]}
          />
          <Tooltip content={<ChartTooltip />} />
          <Area
            type="stepAfter"
            dataKey="band"
            stroke="none"
            fill={TEAL}
            fillOpacity={0.12}
            isAnimationActive={false}
          />
          <ReferenceLine y={buffer} stroke={RED} strokeDasharray="4 4" strokeWidth={1} />
          <Line type="stepAfter" dataKey="likely" stroke={TEAL} strokeWidth={2} dot={false} isAnimationActive={false} />
          {scenario && (
            <Line
              type="stepAfter"
              dataKey="scenario"
              stroke={AMBER}
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              isAnimationActive={false}
            />
          )}
          {shortfallPoint && (
            <ReferenceDot
              x={shortfallPoint.label}
              y={shortfallPoint.scenario ?? shortfallPoint.likely}
              r={5}
              fill={RED}
              stroke="white"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
