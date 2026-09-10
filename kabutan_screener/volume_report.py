# -*- coding: utf-8 -*-
"""出来高急増ウォッチ専用のローカルHTMLレポートと要約JSONを生成する。

長期上昇候補スクリーナーのreport.pyとは別ファイル・別出力
（output/volume_report.html, output/volume_summary_latest.json）。
"""

import json
import os

STATUS_LABEL = {
    "success": "更新成功",
    "skipped_holiday": "祝日スキップ",
    "skipped_no_data": "取得スキップ",
    "error": "エラー",
}


def build_summary_json(as_of, analysis, run_status):
    return {
        "generated_at": as_of,
        "run_status": run_status,
        "window_dates": analysis["window_dates"],
        "oldest_date": analysis["oldest_date"],
        "latest_date": analysis["latest_date"],
        "insufficient_data": analysis["insufficient_data"],
        "surge_ratio_threshold": analysis.get("surge_ratio_threshold"),
        "price_flat_pct_threshold": analysis.get("price_flat_pct_threshold"),
        "surge_count": len(analysis["surges"]),
        "surges": analysis["surges"],
        "new_entrant_count": len(analysis["new_entrants"]),
        "new_entrants": analysis["new_entrants"][:30],
    }


def write_summary_json(path, summary):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


HTML_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>出来高急増ウォッチ（ローカル実行結果）</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;800&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap">
<style>
:root{{
  --paper:#f6f2e8; --panel:#fffdf8; --panel-2:#f0ead9; --ink:#211d17; --muted:#7a7062;
  --line:#e0d6bf; --line-strong:#c9bc9c; --accent:#3f5a3d; --accent-soft:#e5ecdf;
  --up:#b8382a; --up-soft:#f7e5e1; --down:#3d5f8f; --down-soft:#e4eaf3;
  --ok:#3f7a52; --ok-soft:#e2ede3; --err:#a23c2e; --err-soft:#f5e1de;
  --shadow:0 1px 2px rgba(40,32,16,.06), 0 8px 24px -12px rgba(40,32,16,.18); --radius:10px;
}}
@media (prefers-color-scheme: dark){{
  :root{{
    --paper:#15130f; --panel:#1d1a14; --panel-2:#26221a; --ink:#ece4d3; --muted:#a89a80;
    --line:#39331f; --line-strong:#4c4526; --accent:#8fc28d; --accent-soft:#212a1f;
    --up:#e2685a; --up-soft:#3a2420; --down:#84a6dc; --down-soft:#212a3d;
    --ok:#7cc296; --ok-soft:#1d2a20; --err:#e2685a; --err-soft:#3a2420;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 28px -14px rgba(0,0,0,.6);
  }}
}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Zen Kaku Gothic New","Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.55;}}
h1,h2{{font-family:"Shippori Mincho",serif;letter-spacing:.02em;}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 60px;}}
.eyebrow{{font-size:12px;letter-spacing:.14em;color:var(--muted);text-transform:uppercase;margin:0 0 8px;}}
h1{{font-size:28px;margin:0 0 6px;}}
h2{{font-size:18px;margin:28px 0 10px;}}
.lede{{color:var(--muted);font-size:14px;margin:0 0 18px;max-width:70ch;}}
.stat-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;min-width:110px;}}
.stat b{{display:block;font-size:19px;font-weight:800;font-family:"Shippori Mincho",serif;}}
.stat span{{font-size:11px;color:var(--muted);}}
.notice{{background:var(--panel);border:1px solid var(--line-strong);border-left:4px solid var(--down);border-radius:var(--radius);padding:12px 16px;font-size:13px;margin-bottom:20px;}}
details{{margin-bottom:18px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);}}
summary{{cursor:pointer;padding:12px 16px;font-weight:700;font-size:14px;color:var(--accent);}}
.log-body, .method-body{{padding:0 16px 16px;border-top:1px solid var(--line);font-size:13px;}}
.log-item{{display:flex;gap:10px;align-items:baseline;padding:7px 0;border-top:1px solid var(--line);flex-wrap:wrap;}}
.log-item:first-child{{border-top:none;}}
.log-date{{width:64px;color:var(--muted);font-size:12px;flex:none;}}
.log-badge{{display:inline-flex;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:100px;flex:none;}}
.log-badge.success{{background:var(--ok-soft);color:var(--ok);}}
.log-badge.error{{background:var(--err-soft);color:var(--err);}}
.log-badge.skipped_holiday, .log-badge.skipped_no_data{{background:var(--panel-2);color:var(--muted);}}
.table-shell{{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--panel);box-shadow:var(--shadow);margin-bottom:22px;}}
.table-scroll{{overflow-x:auto;}}
table{{border-collapse:collapse;width:100%;min-width:640px;}}
thead th{{position:sticky;top:0;background:var(--panel-2);text-align:left;font-size:11px;color:var(--muted);padding:9px 11px;border-bottom:1px solid var(--line-strong);white-space:nowrap;}}
th.num, td.num{{text-align:right;}}
td{{padding:8px 11px;font-size:13px;white-space:nowrap;border-bottom:1px solid var(--line);}}
td.name-cell{{white-space:normal;min-width:150px;}}
.code{{color:var(--muted);font-size:11px;display:block;}}
.name{{font-weight:700;}}
.ratio-badge{{display:inline-flex;min-width:44px;padding:3px 7px;border-radius:6px;font-weight:800;font-size:13px;font-family:"Shippori Mincho",serif;justify-content:center;background:var(--up-soft);color:var(--up);}}
.flat-badge{{display:inline-flex;padding:3px 7px;border-radius:6px;font-weight:700;font-size:12px;background:var(--accent-soft);color:var(--accent);}}
.empty{{color:var(--muted);font-size:13px;padding:16px;}}
footer{{margin-top:22px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px;}}
</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">日本株ウォッチ・ツール（ローカル実行）</p>
  <h1>出来高急増ウォッチ</h1>
  <p class="lede">出来高が急に増えたのに株価がまだ動いていない銘柄（＝物言わぬ買い集めの可能性）を、
  日々蓄積した出来高ランキングの比較から探します。長期上昇候補スクリーナーとは別の、独立したデータベース・レポートです。
  データ基準: {as_of}</p>

  {insufficient_notice}

  <div class="stat-row">
    <div class="stat"><b>{surge_count}</b><span>急増・横ばい候補</span></div>
    <div class="stat"><b>{new_entrant_count}</b><span>ランキング新規浮上</span></div>
    <div class="stat"><b>{window_label}</b><span>比較ウィンドウ</span></div>
  </div>

  <details>
    <summary>検出条件・実行ログを見る</summary>
    <div class="method-body">
      <p>比較ウィンドウ内で最も古い実行日と最新の実行日を比べ、出来高が
      <b>{surge_ratio_threshold}倍以上</b>に増えているのに、株価の変化が
      <b>±{price_flat_pct_threshold}%以内</b>に収まっている銘柄を「急増・横ばい候補」として検出しています。
      ウィンドウ内の他の日には出来高ランキングに登場していなかった銘柄は、比較対象がなく倍率を計算できないため
      「ランキング新規浮上」として別枠に表示しています。</p>
    </div>
    <div class="log-body" id="logBody">{log_html}</div>
  </details>

  <h2>出来高急増・株価横ばい候補</h2>
  <div class="table-shell">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th class="num">#</th><th>銘柄</th><th class="num">出来高倍率</th>
            <th class="num">株価変化</th><th class="num">出来高（比較元→最新）</th><th class="num">株価（比較元→最新）</th>
          </tr>
        </thead>
        <tbody>{surge_rows_html}</tbody>
      </table>
    </div>
  </div>

  <h2>ランキング新規浮上銘柄（参考）</h2>
  <div class="table-shell">
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th class="num">#</th><th>銘柄</th><th class="num">出来高ランキング順位</th><th class="num">株価</th><th class="num">出来高</th></tr>
        </thead>
        <tbody>{new_entrant_rows_html}</tbody>
      </table>
    </div>
  </div>

  <footer>
    <p>本ツールは投資助言を目的としたものではありません。表示される候補は過去の出来高・株価データに基づく
    機械的な絞り込みの目安であり、将来の株価上昇を示唆・保証するものではありません。投資判断はご自身の責任で行ってください。</p>
    <p>結果は data/volume_watch.db（SQLite、長期候補スクリーナーのDBとは別ファイル）に蓄積されています。
    output/volume_summary_latest.json をClaudeとの会話に貼ると、コメントをもらえます。</p>
  </footer>
</div>
</body>
</html>
"""


def _log_item_html(run):
    status = run["status"]
    label = STATUS_LABEL.get(status, status)
    summary = run.get("summary") or ""
    return (
        '<div class="log-item">'
        '<span class="log-date">{date}</span>'
        '<span class="log-badge {status}">{label}</span>'
        '<span>{summary}</span>'
        '</div>'
    ).format(date=run["date"], status=status, label=label, summary=summary)


def _fmt_num(v, unit=""):
    if v is None:
        return "－"
    return "{:,.0f}{}".format(v, unit)


def _fmt_price(v):
    if v is None:
        return "－"
    return "{:,.0f}円".format(v)


def _surge_row_html(i, s):
    price_sign = "+" if (s["price_pct_change"] is not None and s["price_pct_change"] >= 0) else ""
    price_text = "－" if s["price_pct_change"] is None else "{}{:.1f}%".format(price_sign, s["price_pct_change"])
    return (
        "<tr>"
        "<td class='num'>{i}</td>"
        "<td class='name-cell'><span class='name'>{name}</span><span class='code'>{code} ・ {market}</span></td>"
        "<td class='num'><span class='ratio-badge'>×{ratio:.1f}</span></td>"
        "<td class='num'><span class='flat-badge'>{price_text}</span></td>"
        "<td class='num'>{base_vol} → {latest_vol}</td>"
        "<td class='num'>{base_price} → {latest_price}</td>"
        "</tr>"
    ).format(
        i=i,
        name=s.get("name") or "－",
        code=s["code"],
        market=s.get("market") or "－",
        ratio=s["volume_ratio"],
        price_text=price_text,
        base_vol=_fmt_num(s.get("base_volume")),
        latest_vol=_fmt_num(s.get("latest_volume")),
        base_price=_fmt_price(s.get("base_price")),
        latest_price=_fmt_price(s.get("latest_price")),
    )


def _new_entrant_row_html(i, e):
    return (
        "<tr>"
        "<td class='num'>{i}</td>"
        "<td class='name-cell'><span class='name'>{name}</span><span class='code'>{code} ・ {market}</span></td>"
        "<td class='num'>{rank}</td>"
        "<td class='num'>{price}</td>"
        "<td class='num'>{volume}</td>"
        "</tr>"
    ).format(
        i=i,
        name=e.get("name") or "－",
        code=e["code"],
        market=e.get("market") or "－",
        rank=e.get("rank") if e.get("rank") is not None else "－",
        price=_fmt_price(e.get("price")),
        volume=_fmt_num(e.get("volume")),
    )


def write_html_report(path, as_of, analysis, recent_runs):
    surges = analysis["surges"]
    new_entrants = analysis["new_entrants"]

    surge_rows_html = "".join(_surge_row_html(i, s) for i, s in enumerate(surges, start=1)) or (
        "<tr><td colspan='6' class='empty'>該当銘柄はありませんでした。</td></tr>"
    )
    new_entrant_rows_html = "".join(_new_entrant_row_html(i, e) for i, e in enumerate(new_entrants[:50], start=1)) or (
        "<tr><td colspan='5' class='empty'>該当銘柄はありませんでした。</td></tr>"
    )

    log_html = "".join(_log_item_html(r) for r in recent_runs) or '<p style="color:var(--muted);margin:0;">まだ実行記録がありません。</p>'

    if analysis["insufficient_data"]:
        insufficient_notice = (
            '<div class="notice">まだ比較に十分な実行回数（2回以上）が蓄積されていません。'
            'このツールを毎営業日実行して、data/volume_watch.db にランキングを蓄積してください。'
            '直近{}営業日ぶんが蓄積されると、出来高急増・株価横ばい候補の検出が始まります。</div>'
        ).format(0 if not analysis["window_dates"] else "N")
        window_label = "データ蓄積中"
    else:
        insufficient_notice = ""
        window_label = "{}〜{}".format(analysis["oldest_date"], analysis["latest_date"])

    html = HTML_TEMPLATE.format(
        as_of=as_of,
        insufficient_notice=insufficient_notice,
        surge_count=len(surges),
        new_entrant_count=len(new_entrants),
        window_label=window_label,
        surge_ratio_threshold=analysis.get("surge_ratio_threshold", "－"),
        price_flat_pct_threshold=analysis.get("price_flat_pct_threshold", "－"),
        log_html=log_html,
        surge_rows_html=surge_rows_html,
        new_entrant_rows_html=new_entrant_rows_html,
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
