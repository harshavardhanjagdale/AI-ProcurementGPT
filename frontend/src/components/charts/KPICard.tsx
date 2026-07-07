"use client";

import { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: number;
  trendLabel?: string;
  color?: "blue" | "green" | "red" | "amber" | "purple" | "indigo";
}

const colorMap = {
  blue: "from-blue-500 to-blue-600",
  green: "from-emerald-500 to-emerald-600",
  red: "from-rose-500 to-rose-600",
  amber: "from-amber-500 to-amber-600",
  purple: "from-purple-500 to-purple-600",
  indigo: "from-indigo-500 to-indigo-600",
};

const iconBgMap = {
  blue: "bg-blue-400/30",
  green: "bg-emerald-400/30",
  red: "bg-rose-400/30",
  amber: "bg-amber-400/30",
  purple: "bg-purple-400/30",
  indigo: "bg-indigo-400/30",
};

export function KPICard({ title, value, subtitle, icon, trend, trendLabel, color = "blue" }: KPICardProps) {
  const renderTrend = () => {
    if (trend === undefined) return null;
    const isPositive = trend > 0;
    const isNeutral = trend === 0;
    const Icon = isPositive ? TrendingUp : isNeutral ? Minus : TrendingDown;
    const trendColor = isPositive ? "text-emerald-200" : isNeutral ? "text-white/60" : "text-rose-200";

    return (
      <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
        <Icon className="w-3 h-3" />
        <span>{Math.abs(trend)}%</span>
        {trendLabel && <span className="text-white/50">{trendLabel}</span>}
      </div>
    );
  };

  return (
    <div className={`relative overflow-hidden rounded-xl bg-gradient-to-br ${colorMap[color]} p-5 text-white shadow-lg`}>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-white/80">{title}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
          {subtitle && <p className="text-xs text-white/60">{subtitle}</p>}
          {renderTrend()}
        </div>
        {icon && (
          <div className={`rounded-lg p-2 ${iconBgMap[color]}`}>
            {icon}
          </div>
        )}
      </div>
      <div className="absolute -right-4 -bottom-4 h-24 w-24 rounded-full bg-white/5" />
    </div>
  );
}
