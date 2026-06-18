"""Pandas 深度分析引擎 — 基于规则的确定性分析

不依赖 LLM 写 Python 代码，而是按意图类型预定义分析策略，
直接用 pandas/numpy/scipy 执行确定性分析，保证稳定输出。

支持的分析策略:
- trend: 时间趋势（环比/同比/移动平均）
- comparison: 分组对比（差异显著性）
- ranking: 排行分析（Top N / 占比）
- distribution: 分布分析（频次/直方图/百分位）
- anomaly: 异常检测（IQR/标准差）
- root_cause: 根因分析（贡献度拆解）
- forecast: 预测（线性回归/移动平均）
- summary: 全量数据摘要
"""

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def analyze_dataframe(
    df: pd.DataFrame,
    intent_type: str = "summary",
    question: str = "",
    top_n: int = 10,
) -> dict:
    """对 DataFrame 执行意图感知的深度分析

    Args:
        df: 要分析的数据
        intent_type: 意图类型（trend/comparison/ranking/distribution/anomaly/root_cause/forecast/summary）
        question: 原始用户问题（用于提取分析参数）
        top_n: 排行/分布的前 N 项

    Returns:
        {
            "insight": str,          # 核心洞察文本
            "charts": list[dict],    # ECharts 兼容图表配置
            "table": list[dict],     # 分析结果表格
            "stats": dict,           # 关键统计指标
            "summary": str,          # 数据概览
        }
    """
    if df.empty:
        return _empty_result()

    # 自动检测列类型
    num_cols = _get_numeric_cols(df)
    cat_cols = _get_categorical_cols(df)
    time_cols = _get_time_cols(df)
    date_cols = _get_date_like_cols(df)

    # 自动选择最佳分析策略
    strategy = intent_type

    # 如果指定了 summary 或无明确意图，自动检测
    if strategy == "summary" or strategy == "unknown":
        strategy = _detect_best_strategy(df, num_cols, cat_cols, time_cols, date_cols)

    # 按策略执行分析
    analyzers = {
        "trend": _analyze_trend,
        "comparison": _analyze_comparison,
        "ranking": _analyze_ranking,
        "distribution": _analyze_distribution,
        "anomaly": _analyze_anomaly,
        "root_cause": _analyze_root_cause,
        "forecast": _analyze_forecast,
        "summary": _analyze_summary,
    }

    analyzer = analyzers.get(strategy, _analyze_summary)
    try:
        result = analyzer(df, num_cols, cat_cols, time_cols, date_cols, top_n)
    except Exception as e:
        logger.warning(f"分析策略 {strategy} 失败: {e}")
        result = _analyze_summary(df, num_cols, cat_cols, time_cols, date_cols, top_n)

    result["strategy"] = strategy
    return result


def _get_numeric_cols(df: pd.DataFrame) -> list[str]:
    """获取数值列"""
    return list(df.select_dtypes(include=[np.number]).columns)


def _get_categorical_cols(df: pd.DataFrame) -> list[str]:
    """获取分类列"""
    cat_types = ["object", "category", "bool"]
    # 排除日期类
    cols = []
    for c in df.select_dtypes(include=cat_types).columns:
        if not _is_date_string(df[c]):
            cols.append(c)
    return cols


def _get_time_cols(df: pd.DataFrame) -> list[str]:
    """获取时间列（datetime 类型）"""
    return list(df.select_dtypes(include=["datetime64", "datetimetz"]).columns)


def _get_date_like_cols(df: pd.DataFrame) -> list[str]:
    """获取类日期列（字符串类型的日期）"""
    date_cols = []
    for c in df.select_dtypes(include=["object"]).columns:
        if _is_date_string(df[c]):
            date_cols.append(c)
    return date_cols


def _is_date_string(series: pd.Series) -> bool:
    """判断字符串列是否包含日期格式。
    两步策略：
    1. 关键词快速匹配列名（零成本）
    2. 仅当列名无关键词时，抽样5行做快速日期解析（无 infer_datetime_format，兼容 pandas 3.0）
    """
    date_keywords = ["date", "time", "日期", "时间",
                     "month", "year", "day", "dt", "timestamp",
                     "create", "update", "modified"]
    col_name = str(series.name) if series.name else ""
    if any(kw in col_name.lower() for kw in date_keywords):
        return True

    sample = series.dropna().head(5)
    if sample.empty:
        return False
    first_val = str(sample.iloc[0])
    if any(sep in first_val for sep in ["-", "/", ":"]) and any(c.isdigit() for c in first_val):
        try:
            _pd_check = pd if "pd" in dir() else __import__("pandas", fromlist=["DataFrame"])
            parsed = _pd_check.to_datetime(sample, errors="coerce")
            return parsed.notna().sum() >= len(sample) // 2
        except Exception:
            pass
    return False


def _detect_best_strategy(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str],
) -> str:
    """自动检测最佳分析策略"""
    time_like = time_cols + date_cols

    # 有时间列 → trend
    if time_like and num_cols:
        return "trend"

    # 有分类列 + 数值列 → comparison
    if len(cat_cols) >= 1 and len(num_cols) >= 1:
        if len(cat_cols) >= 2 or len(num_cols) >= 2:
            return "comparison"
        # 单分类 + 单数值 → ranking
        if df[cat_cols[0]].nunique() > 3:
            return "ranking"
        return "distribution"

    # 只有分类列 → distribution
    if cat_cols:
        return "distribution"

    # 只有数值列 → anomaly 检测
    if num_cols:
        return "anomaly"

    return "summary"


# ─── 各分析策略实现 ───

def _analyze_trend(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """时间趋势分析"""
    time_like = time_cols + date_cols
    if not time_like:
        # 无时间列时降级为 summary
        from app.core.pandas_analyzer import _analyze_summary
        return _analyze_summary(df, num_cols, cat_cols, time_cols, date_cols, top_n)
    time_col = time_like[0]

    # 解析时间列
    if time_col in date_cols:
        df = df.copy()
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df_sorted = df.sort_values(time_col)

    # 对每个数值列做趋势分析
    charts = []
    insight_parts = []
    table_data = None

    for col in num_cols[:3]:
        series = df_sorted.set_index(time_col)[col]
        # 聚合到月
        monthly = series.resample("ME").sum().dropna()
        if len(monthly) < 2:
            monthly = series.resample("W").sum().dropna()
        if len(monthly) < 2:
            continue

        values = monthly.values
        labels = [str(d.date()) for d in monthly.index]

        # 环比计算
        pct_changes = pd.Series(values).pct_change() * 100
        avg_change = pct_changes.dropna().mean()

        # 趋势方向
        trend_dir = "上升" if values[-1] > values[0] else "下降"
        change_pct = abs((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0

        insight_parts.append(
            f"{col}整体呈{trend_dir}趋势，从{values[0]:.1f}到{values[-1]:.1f}"
            f"（变化{change_pct:.1f}%），平均环比{avg_change:+.1f}%"
        )

        charts.append({
            "type": "line",
            "title": f"{col}时间趋势",
            "data": {
                "xAxis": labels,
                "series": [{"name": col, "data": [round(float(v), 2) for v in values]}],
            },
        })

        # 构建结果表
        result_df = pd.DataFrame({"period": labels, col: [round(float(v), 2) for v in values]})
        # 添加环比
        pct_charts = [round(float(v), 1) if not math.isnan(float(v)) else None for v in pct_changes.values]
        if len(pct_charts) == len(result_df):
            pct_charts[0] = None
        else:
            pct_charts = [None] + pct_charts[:len(result_df)-1]
        result_df["环比(%)"] = pct_charts
        table_data = result_df.to_dict(orient="records")

    if not insight_parts:
        insight_parts.append(f"已分析{len(df)}条记录的时间趋势")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"rows": len(df), "trend_periods": len(charts)},
        "summary": f"趋势分析: {len(num_cols)}个数值列 × {len(time_like)}个时间维度",
    }


def _analyze_comparison(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """对比分析"""
    charts = []
    insight_parts = []
    table_data = None

    # 取前几个分类列和数值列做交叉分析
    for cat in cat_cols[:2]:
        for num in num_cols[:2]:
            grouped = df.groupby(cat)[num].agg(["mean", "sum", "count", "std"]).reset_index()
            grouped = grouped.sort_values("sum", ascending=False).head(top_n)

            labels = [str(x) for x in grouped[cat].values]
            means = [round(float(v), 2) for v in grouped["mean"].values]
            sums = [round(float(v), 2) for v in grouped["sum"].values]

            # 对比洞察
            if len(grouped) >= 2:
                top_item = grouped.iloc[0]
                bottom_item = grouped.iloc[-1]
                ratio = (top_item["mean"] / bottom_item["mean"]) if bottom_item["mean"] != 0 else 0
                insight_parts.append(
                    f"按{cat}对比{num}：最高为'{top_item[cat]}'（均值{top_item['mean']:.1f}），"
                    f"最低为'{bottom_item[cat]}'（均值{bottom_item['mean']:.1f}），相差{ratio:.1f}倍"
                )

            charts.append({
                "type": "bar",
                "title": f"各{cat}的{num}对比",
                "data": {
                    "xAxis": labels[:top_n],
                    "series": [
                        {"name": "均值", "data": means[:top_n]},
                        {"name": "总和", "data": sums[:top_n]},
                    ],
                },
            })

            if table_data is None:
                table_data = grouped.head(top_n).to_dict(orient="records")

    if not insight_parts:
        insight_parts.append(f"已完成{len(cat_cols)}个维度×{len(num_cols)}个指标的对比分析")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"groups": len(cat_cols), "metrics": len(num_cols)},
        "summary": f"对比分析: {len(cat_cols)}个分组维度",
    }


def _analyze_ranking(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """排行分析"""
    charts = []
    insight_parts = []
    table_data = None

    for num in num_cols[:2]:
        if cat_cols:
            cat = cat_cols[0]
            ranked = df.groupby(cat)[num].sum().sort_values(ascending=False).head(top_n).reset_index()
            total = df[num].sum()
            ranked["占比(%)"] = [round(float(v) / total * 100, 1) if total != 0 else 0 for v in ranked[num].values]

            labels = [str(x) for x in ranked[cat].values]
            values = [round(float(v), 2) for v in ranked[num].values]
            pcts = ranked["占比(%)"].tolist()

            # 排行洞察
            top_name = ranked.iloc[0][cat]
            top_val = ranked.iloc[0][num]
            top_pct = ranked.iloc[0]["占比(%)"]
            insight_parts.append(
                f"{num}Top 1: '{top_name}'（{top_val:.1f}，占比{top_pct:.1f}%）"
            )
            if len(ranked) >= 3:
                sum_top3 = ranked.head(3)[num].sum()
                pct_top3 = sum_top3 / total * 100 if total != 0 else 0
                insight_parts.append(f"Top 3 合计占比{pct_top3:.1f}%")

            charts.append({
                "type": "bar",
                "title": f"{num}排行(Top {min(top_n, len(ranked))})",
                "data": {
                    "xAxis": labels,
                    "series": [
                        {"name": num, "data": values},
                        {"name": "占比(%)", "data": pcts},
                    ],
                },
            })

            if table_data is None:
                table_data = ranked.to_dict(orient="records")
        else:
            # 直接对数值列排序
            ranked = df.sort_values(num, ascending=False).head(top_n)
            labels = [str(i + 1) for i in range(len(ranked))]
            values = [round(float(v), 2) for v in ranked[num].values]
            insight_parts.append(f"{num}最高值: {values[0]:.1f}，最低值: {values[-1]:.1f}")
            charts.append({
                "type": "bar",
                "title": f"{num}排行(Top {len(ranked)})",
                "data": {"xAxis": labels, "series": [{"name": num, "data": values}]},
            })
            if table_data is None:
                table_data = ranked.head(top_n).to_dict(orient="records")

    if not insight_parts:
        insight_parts.append("已完成排行分析")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"top_n": top_n},
        "summary": f"排行分析: {len(num_cols)}个指标",
    }


def _analyze_distribution(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """分布分析"""
    charts = []
    insight_parts = []
    table_data = None

    for cat in cat_cols[:3]:
        vc = df[cat].value_counts().head(top_n)
        labels = [str(x) for x in vc.index]
        values = [int(v) for v in vc.values]
        total = vc.sum()
        pcts = [round(v / total * 100, 1) for v in vc.values]

        # 分布洞察
        top_name = vc.index[0]
        top_pct = pcts[0]
        insight_parts.append(f"{cat}分布：'{top_name}'最多（{top_pct}%）")

        charts.append({
            "type": "pie",
            "title": f"{cat}分布",
            "data": [{"name": labels[i], "value": values[i]} for i in range(len(labels))],
        })

        result_df = pd.DataFrame({
            cat: labels, "数量": values, "占比(%)": pcts,
        })
        if table_data is None:
            table_data = result_df.to_dict(orient="records")

    # 数值列分布
    for num in num_cols[:2]:
        stats = df[num].describe()
        insight_parts.append(
            f"{num}: 均值={stats['mean']:.1f}, 中位数={stats['50%']:.1f}, "
            f"最大={stats['max']:.1f}, 最小={stats['min']:.1f}"
        )
        # 直方图
        hist, edges = np.histogram(df[num].dropna(), bins=min(10, len(df[num].dropna())))
        bin_labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(len(hist))]
        charts.append({
            "type": "bar",
            "title": f"{num}分布直方图",
            "data": {
                "xAxis": bin_labels,
                "series": [{"name": "频次", "data": [int(v) for v in hist]}],
            },
        })

    if not insight_parts:
        insight_parts.append("已完成分布分析")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"categories": len(cat_cols), "numerics": len(num_cols)},
        "summary": f"分布分析: {len(cat_cols)}个分类维度, {len(num_cols)}个数值维度",
    }


def _analyze_anomaly(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """异常检测（IQR 方法）"""
    charts = []
    insight_parts = []
    all_anomalies = []

    for col in num_cols[:5]:
        series = df[col].dropna()
        if len(series) < 4:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        anomalies = df[(df[col] < lower) | (df[col] > upper)]
        normal_count = len(df) - len(anomalies)

        if len(anomalies) > 0:
            pct = len(anomalies) / len(df) * 100
            insight_parts.append(
                f"{col}检测到{len(anomalies)}个异常值（占{pct:.1f}%），"
                f"正常范围[{lower:.1f}, {upper:.1f}]"
            )
            all_anomalies.append({
                "column": col,
                "count": len(anomalies),
                "pct": round(pct, 1),
                "lower": round(lower, 2),
                "upper": round(upper, 2),
            })

            # 箱线图数据
            charts.append({
                "type": "scatter",
                "title": f"{col}异常值分布",
                "data": {
                    "xAxis": [str(i) for i in range(len(series))],
                    "series": [
                        {
                            "name": "正常值",
                            "data": [
                                float(v) if lower <= float(v) <= upper else None
                                for v in series.values
                            ],
                        },
                        {
                            "name": "异常值",
                            "data": [
                                float(v) if float(v) < lower or float(v) > upper else None
                                for v in series.values
                            ],
                        },
                    ],
                },
            })

        # 统计摘要
        stats = series.describe()
        insight_parts.append(
            f"{col}: 均值={stats['mean']:.1f}, 标准差={stats['std']:.1f}"
        )

    if not insight_parts:
        insight_parts.append("未检测到明显异常值")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": df.head(top_n).to_dict(orient="records"),
        "stats": {"anomaly_columns": len(all_anomalies), "anomalies": all_anomalies},
        "summary": f"异常检测: 检查了{len(num_cols)}个数值列",
    }


def _analyze_root_cause(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """根因分析（贡献度拆解）"""
    if not num_cols or not cat_cols:
        return _analyze_summary(df, num_cols, cat_cols, time_cols, date_cols, top_n)

    charts = []
    insight_parts = []
    table_data = None

    total = df[num_cols[0]].sum()

    for cat in cat_cols[:2]:
        contributions = df.groupby(cat)[num_cols[0]].sum().sort_values(ascending=False)
        total_contrib = contributions.sum()
        pcts = contributions / total_contrib * 100

        labels = [str(x) for x in contributions.index[:top_n]]
        values = [round(float(v), 2) for v in contributions.values[:top_n]]
        pct_vals = [round(float(pcts.iloc[i]), 1) for i in range(min(top_n, len(pcts)))]

        # 帕累托：累计占比
        cumsum = np.cumsum(pct_vals)
        top80_idx = np.where(cumsum >= 80)[0]
        top80_count = top80_idx[0] + 1 if len(top80_idx) > 0 else len(pct_vals)

        top_item = contributions.index[0]
        top_pct = pcts.iloc[0]
        insight_parts.append(
            f"按{cat}拆解{num_cols[0]}：'{top_item}'贡献最大（{top_pct:.1f}%），"
            f"前{top80_count}项累计占比超过80%"
        )

        charts.append({
            "type": "bar",
            "title": f"{num_cols[0]}按{cat}的贡献度拆解",
            "data": {
                "xAxis": labels,
                "series": [
                    {"name": num_cols[0], "data": values},
                    {"name": "累计占比(%)", "data": pct_vals},
                ],
            },
        })

        result_df = pd.DataFrame({
            cat: labels,
            num_cols[0]: values,
            "占比(%)": pct_vals,
            "累计占比(%)": [round(float(c), 1) for c in cumsum[:top_n]],
        })
        if table_data is None:
            table_data = result_df.to_dict(orient="records")

    if not insight_parts:
        insight_parts.append(f"已完成贡献度分析，{num_cols[0]}总计为{total:.1f}")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"total": round(float(total), 2), "dimensions": len(cat_cols)},
        "summary": f"根因分析: {num_cols[0]}按{len(cat_cols)}个维度拆解",
    }


def _analyze_forecast(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """预测分析（移动平均 + 线性回归）"""
    time_like = time_cols + date_cols
    if not time_like or not num_cols:
        # 无时间列或无数值列时降级为 summary
        from app.core.pandas_analyzer import _analyze_summary
        return _analyze_summary(df, num_cols, cat_cols, time_cols, date_cols, top_n)

    charts = []
    insight_parts = []
    table_data = None

    time_col = time_like[0]
    df_sorted = df.sort_values(time_col)
    if time_col in date_cols:
        df_sorted = df_sorted.copy()
        df_sorted[time_col] = pd.to_datetime(df_sorted[time_col], errors="coerce")

    for col in num_cols[:2]:
        series = df_sorted.set_index(time_col)[col]
        monthly = series.resample("ME").sum().dropna()
        if len(monthly) < 3:
            weekly = series.resample("W").sum().dropna()
            if len(weekly) >= 3:
                monthly = weekly
            else:
                continue

        values = monthly.values.astype(float)
        labels = [str(d.date()) for d in monthly.index]

        # 移动平均
        window = min(3, len(values))
        ma = pd.Series(values).rolling(window=window, min_periods=1).mean().values

        # 简单线性回归预测（往后预测3期）
        n_forecast = min(3, max(1, len(values) // 3))
        x = np.arange(len(values))
        mask = ~np.isnan(values)
        if mask.sum() >= 2:
            coeffs = np.polyfit(x[mask], values[mask], 1)
            trend_line = np.polyval(coeffs, x)
            forecast_x = np.arange(len(values), len(values) + n_forecast)
            forecast_y = np.polyval(coeffs, forecast_x)
            forecast_labels = [f"预测{i+1}" for i in range(n_forecast)]
        else:
            trend_line = values
            forecast_y = np.array([])
            forecast_labels = []

        # 趋势方向
        if len(values) >= 2:
            direction = "上升" if values[-1] > values[0] else "下降"
            change = abs((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
            insight_parts.append(
                f"{col}呈{direction}趋势（变化{change:.1f}%），"
                f"最近3期移动平均={ma[-1]:.1f}"
            )

        # 预测洞察
        if len(forecast_y) > 0:
            insight_parts.append(
                f"预测下期{col}约为{forecast_y[0]:.1f}"
            )

        # 图表：历史 + 趋势线 + 预测
        chart_data = {
            "xAxis": labels + forecast_labels,
            "series": [
                {"name": "实际值", "data": [round(float(v), 2) for v in values] + [None] * n_forecast},
                {"name": "趋势线", "data": [round(float(v), 2) for v in trend_line] + [None] * n_forecast},
                {"name": "预测值", "data": [None] * len(values) + [round(float(v), 2) for v in forecast_y]},
            ],
        }
        charts.append({
            "type": "line",
            "title": f"{col}趋势与预测",
            "data": chart_data,
        })

        # 结果表
        result_rows = []
        for i in range(len(labels)):
            result_rows.append({
                "period": labels[i],
                f"{col}(实际)": round(float(values[i]), 2),
                f"{col}(趋势)": round(float(trend_line[i]), 2),
                f"{col}(MA{window})": round(float(ma[i]), 2),
            })
        for i in range(len(forecast_y)):
            result_rows.append({
                "period": forecast_labels[i],
                f"{col}(预测)": round(float(forecast_y[i]), 2),
            })
        if table_data is None:
            table_data = result_rows

    if not insight_parts:
        insight_parts.append("数据不足以进行预测分析，已降级为趋势分析")

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": table_data or df.head(top_n).to_dict(orient="records"),
        "stats": {"forecast_periods": n_forecast if "n_forecast" in dir() else 0},
        "summary": f"预测分析: {len(num_cols)}个指标",
    }


def _analyze_summary(
    df: pd.DataFrame, num_cols: list[str], cat_cols: list[str],
    time_cols: list[str], date_cols: list[str], top_n: int,
) -> dict:
    """全量数据摘要"""
    insight_parts = []
    charts = []

    # 数据概览
    insight_parts.append(f"共{len(df)}条记录，{len(df.columns)}个字段")

    # 数值列统计
    if num_cols:
        desc = df[num_cols].describe()
        for col in num_cols[:3]:
            insight_parts.append(
                f"{col}: 均值={desc[col]['mean']:.1f}, "
                f"总和={df[col].sum():.1f}"
            )

        # 相关性矩阵（如果有多个数值列）
        if len(num_cols) >= 2:
            corr = df[num_cols].corr()
            # 找最强相关对
            corr_values = []
            for i in range(len(num_cols)):
                for j in range(i + 1, len(num_cols)):
                    corr_values.append((num_cols[i], num_cols[j], corr.iloc[i, j]))
            if corr_values:
                corr_values.sort(key=lambda x: abs(x[2]), reverse=True)
                top_corr = corr_values[0]
                if abs(top_corr[2]) > 0.3:
                    direction = "正相关" if top_corr[2] > 0 else "负相关"
                    insight_parts.append(
                        f"'{top_corr[0]}'与'{top_corr[1]}'{direction}（r={top_corr[2]:.2f}）"
                    )

    # 分类列统计
    for cat in cat_cols[:3]:
        nunique = df[cat].nunique()
        top_val = df[cat].value_counts().index[0]
        insight_parts.append(f"{cat}: {nunique}个唯一值，最多'{top_val}'")

    # 缺失值
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if len(null_cols) > 0:
        for col in null_cols.index[:3]:
            pct = null_counts[col] / len(df) * 100
            insight_parts.append(f"{col}有{null_counts[col]}个缺失值（{pct:.1f}%）")

    # 默认图表
    if num_cols and cat_cols:
        grouped = df.groupby(cat_cols[0])[num_cols[0]].sum().sort_values(ascending=False).head(top_n)
        charts.append({
            "type": "bar",
            "title": f"各{cat_cols[0]}{num_cols[0]}分布(Top {min(top_n, len(grouped))})",
            "data": {
                "xAxis": [str(x) for x in grouped.index],
                "series": [{"name": num_cols[0], "data": [round(float(v), 2) for v in grouped.values]}],
            },
        })

    return {
        "insight": "；".join(insight_parts),
        "charts": charts,
        "table": df.head(top_n).to_dict(orient="records"),
        "stats": {
            "rows": len(df),
            "columns": len(df.columns),
            "numeric_cols": len(num_cols),
            "categorical_cols": len(cat_cols),
            "null_ratio": round(float(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100), 1) if len(df) > 0 else 0,
        },
        "summary": f"数据摘要: {len(df)}行 × {len(df.columns)}列",
    }


def _empty_result() -> dict:
    return {
        "insight": "数据为空，无法分析",
        "charts": [],
        "table": [],
        "stats": {},
        "summary": "无数据",
        "strategy": "empty",
    }