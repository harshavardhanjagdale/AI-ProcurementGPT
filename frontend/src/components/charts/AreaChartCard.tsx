"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface AreaChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, unknown>[];
  dataKey: string;
  xKey?: string;
  color?: string;
  gradientId?: string;
  height?: number;
  formatValue?: (value: number) => string;
}

export function AreaChartCard({
  title,
  subtitle,
  data,
  dataKey,
  xKey = "month",
  color = "#6366f1",
  gradientId = "areaGradient",
  height = 240,
  formatValue,
}: AreaChartCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={formatValue}
          />
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
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
