"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface BarChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, unknown>[];
  dataKey: string;
  xKey?: string;
  color?: string;
  height?: number;
  layout?: "horizontal" | "vertical";
  formatValue?: (value: number) => string;
}

export function BarChartCard({
  title,
  subtitle,
  data,
  dataKey,
  xKey = "name",
  color = "#6366f1",
  height = 240,
  layout = "vertical",
  formatValue,
}: BarChartCardProps) {
  const isHorizontal = layout === "horizontal";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          layout={isHorizontal ? "vertical" : "horizontal"}
          margin={{ top: 5, right: 10, left: isHorizontal ? 80 : 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          {isHorizontal ? (
            <>
              <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} tickFormatter={formatValue} />
              <YAxis dataKey={xKey} type="category" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} width={80} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} tickFormatter={formatValue} />
            </>
          )}
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "none",
              borderRadius: "8px",
              color: "#f8fafc",
              fontSize: 12,
            }}
            formatter={(value: number) => [formatValue ? formatValue(value) : value, dataKey]}
          />
          <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={40} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
