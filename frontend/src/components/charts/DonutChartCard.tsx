"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface DonutChartCardProps {
  title: string;
  subtitle?: string;
  data: { name: string; value: number; color?: string }[];
  height?: number;
  colors?: string[];
}

const DEFAULT_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

export function DonutChartCard({
  title,
  subtitle,
  data,
  height = 240,
  colors = DEFAULT_COLORS,
}: DonutChartCardProps) {
  const total = data.reduce((acc, item) => acc + item.value, 0);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={3}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={entry.color || colors[index % colors.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "none",
              borderRadius: "8px",
              color: "#f8fafc",
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => [
              `${value} (${total > 0 ? Math.round((value / total) * 100) : 0}%)`,
              name,
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            iconType="circle"
            iconSize={8}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
