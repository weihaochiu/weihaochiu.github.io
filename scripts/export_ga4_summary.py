from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, OrderBy, RunReportRequest

OUTPUT = Path(os.getenv("GA4_OUTPUT_PATH", "assets/data/ga-summary.json"))
PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "").strip()

def val(row, i, kind=float):
    try: return kind(float(row.metric_values[i].value)) if kind is int else float(row.metric_values[i].value)
    except (ValueError, TypeError, IndexError): return kind()

def report(client, dimensions, metrics, start, end="yesterday", limit=100, order_metric=None, filter_expr=None):
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name=x) for x in dimensions],
        metrics=[Metric(name=x) for x in metrics],
        limit=limit,
        dimension_filter=filter_expr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_metric), desc=True)] if order_metric else []
    )
    return client.run_report(req)

def main():
    if not PROPERTY_ID.isdigit():
        raise SystemExit("GA4_PROPERTY_ID must be the numeric GA4 Property ID.")
    client = BetaAnalyticsDataClient()

    o = report(client, [], ["screenPageViews","activeUsers","sessions","engagementRate"], "28daysAgo")
    row = o.rows[0] if o.rows else None
    overview = {"pageViews":val(row,0,int),"activeUsers":val(row,1,int),"sessions":val(row,2,int),"engagementRate":val(row,3)} if row else {}

    monthly = report(client, ["yearMonth"], ["screenPageViews","activeUsers"], "365daysAgo", order_metric=None)
    monthly_trend = []
    for r in monthly.rows:
        ym=r.dimension_values[0].value
        monthly_trend.append({"month":f"{ym[:4]}-{ym[4:]}", "pageViews":val(r,0,int),"activeUsers":val(r,1,int)})
    monthly_trend.sort(key=lambda x:x["month"])

    pages = report(client, ["pageTitle","pagePath"], ["screenPageViews","activeUsers"], "28daysAgo", limit=15, order_metric="screenPageViews")
    top_pages=[{"title":r.dimension_values[0].value,"path":r.dimension_values[1].value,"pageViews":val(r,0,int),"activeUsers":val(r,1,int)} for r in pages.rows]

    channels = report(client, ["sessionDefaultChannelGroup"], ["sessions","activeUsers"], "28daysAgo", limit=10, order_metric="sessions")
    traffic=[{"channel":r.dimension_values[0].value,"sessions":val(r,0,int),"activeUsers":val(r,1,int)} for r in channels.rows]

    countries_r = report(client, ["country"], ["activeUsers","screenPageViews"], "28daysAgo", limit=15, order_metric="activeUsers")
    countries=[{"country":r.dimension_values[0].value,"activeUsers":val(r,0,int),"pageViews":val(r,1,int)} for r in countries_r.rows]

    devices_r = report(client, ["deviceCategory"], ["activeUsers"], "28daysAgo", limit=10, order_metric="activeUsers")
    devices=[{"device":r.dimension_values[0].value,"activeUsers":val(r,0,int)} for r in devices_r.rows]

    event_filter = FilterExpression(filter=Filter(
        field_name="eventName",
        in_list_filter=Filter.InListFilter(values=[
            "doi_click","oa_pdf_click","scholar_click","cited_by_click",
            "patent_click","cv_download","orcid_click","openalex_click"
        ])
    ))
    events_r = report(client, ["eventName"], ["eventCount"], "28daysAgo", limit=30, order_metric="eventCount", filter_expr=event_filter)
    events=[{"eventName":r.dimension_values[0].value,"eventCount":val(r,0,int)} for r in events_r.rows]

    payload={
        "schemaVersion":1,
        "generatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
        "period":{"overview":"28daysAgo to yesterday","trend":"365daysAgo to yesterday"},
        "overview":overview,"monthlyTrend":monthly_trend,"topPages":top_pages,
        "trafficChannels":traffic,"topCountries":countries,"devices":devices,
        "academicEvents":events
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Wrote {OUTPUT}")

if __name__=="__main__": main()
