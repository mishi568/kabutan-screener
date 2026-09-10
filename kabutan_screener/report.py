# -*- coding: utf-8 -*-
"""ローカルHTMLレポートと、Claudeに貼り付けて確認してもらうための
要約JSONを生成する。"""

import json
import os

from . import config

STATUS_LABEL = {
    "success": "更新成功",
    "skipped_holiday": "祝日スキップ",
    "skipped_no_data": "取得スキップ",
    "error": "エラー",
}

MARKET_LABEL_SHORT = {
    "プライム": "東Ｐ",
    "スタンダード": "東Ｓ",
    "グロース": "東Ｇ",
}


def build_comparison(current_stocks, previous_stocks):
    """前回成功回との比較。新規トップ20入り・大きく順位を落とした銘柄を拾う。"""
    prev_rank = {s["code"]: s["rank"] for s in previous_stocks}
    prev_top20_codes = {s["code"] for s in previous_stocks if s["rank"] <= 20}
    cur_codes = {s["code"] for s in current_stocks}

    new_top20 = []
    big_drops = []
    dropped_out = []

    for s in current_stocks:
        if s["rank"] <= 20:
            pr = prev_rank.get(s["code"])
            if pr is None or pr > 20:
                new_top20.append({"code": s["code"], "name": s["name"], "rank": s["rank"], "prev_rank": pr})

    for s in current_stocks:
        pr = prev_rank.get(s["code"])
        if pr is not None and pr <= 20 and s["rank"] - pr >= 15:
            big_drops.append({"code": s["code"], "name": s["name"], "rank": s["rank"], "prev_rank": pr})

    for code in prev_top20_codes:
        if code not in cur_codes:
            # 前回トップ20だった銘柄が今回の候補から完全に外れた
            prev_name = next((s["name"] for s in previous_stocks if s["code"] == code), code)
            dropped_out.append({"code": code, "name": prev_name, "prev_rank": prev_rank[code]})

    return {"new_top20": new_top20, "big_drops": big_drops, "dropped_out": dropped_out}


def build_summary_json(as_of, current_stocks, previous_stocks, run_status, top_n=20):
    comparison = build_comparison(current_stocks, previous_stocks) if previous_stocks else {
        "new_top20": [], "big_drops": [], "dropped_out": []
    }
    top = []
    for s in current_stocks[:top_n]:
        top.append({
            "rank": s["rank"],
            "code": s["code"],
            "name": s["name"],
            "market": s["market"],
            "score": s["score"],
            "price": s["price"],
            "this_growth_pct": s["this_growth"],
            "supply_score": s["supply_score"],
            "supply_category": s["supply_category"],
            "cred_ratio": s["cred_ratio"],
        })
    return {
        "generated_at": as_of,
        "run_status": run_status,
        "candidate_count": len(current_stocks),
        "top": top,
        "comparison_vs_previous_run": comparison,
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
<title>長期上昇候補スクリーナー（ローカル実行結果）</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;800&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap">
<style>
:root{{
  --paper:#f6f2e8; --panel:#fffdf8; --panel-2:#f0ead9; --ink:#211d17; --muted:#7a7062;
  --line:#e0d6bf; --line-strong:#c9bc9c; --accent:#26314f; --accent-soft:#e7e9f2;
  --up:#b8382a; --up-soft:#f7e5e1; --down:#3d5f8f; --down-soft:#e4eaf3;
  --ok:#3f7a52; --ok-soft:#e2ede3; --err:#a23c2e; --err-soft:#f5e1de;
  --shadow:0 1px 2px rgba(40,32,16,.06), 0 8px 24px -12px rgba(40,32,16,.18); --radius:10px;
}}
@media (prefers-color-scheme: dark){{
  :root{{
    --paper:#15130f; --panel:#1d1a14; --panel-2:#26221a; --ink:#ece4d3; --muted:#a89a80;
    --line:#39331f; --line-strong:#4c4526; --accent:#93a4d8; --accent-soft:#252a3e;
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
.lede{{color:var(--muted);font-size:14px;margin:0 0 18px;max-width:70ch;}}
.stat-row{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;min-width:110px;}}
.stat b{{display:block;font-size:19px;font-weight:800;font-family:"Shippori Mincho",serif;}}
.stat span{{font-size:11px;color:var(--muted);}}
details{{margin-bottom:18px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);}}
summary{{cursor:pointer;padding:12px 16px;font-weight:700;font-size:14px;color:var(--accent);}}
.log-body{{padding:0 16px 16px;border-top:1px solid var(--line);font-size:13px;}}
.log-item{{display:flex;gap:10px;align-items:baseline;padding:7px 0;border-top:1px solid var(--line);flex-wrap:wrap;}}
.log-item:first-child{{border-top:none;}}
.log-date{{width:64px;color:var(--muted);font-size:12px;flex:none;}}
.log-badge{{display:inline-flex;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:100px;flex:none;}}
.log-badge.success{{background:var(--ok-soft);color:var(--ok);}}
.log-badge.error{{background:var(--err-soft);color:var(--err);}}
.log-badge.skipped_holiday, .log-badge.skipped_no_data{{background:var(--panel-2);color:var(--muted);}}
input#q{{width:100%;max-width:280px;padding:8px 10px;border-radius:8px;border:1px solid var(--line-strong);background:var(--panel);color:var(--ink);font-size:13.5px;margin-bottom:12px;}}
.table-shell{{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--panel);box-shadow:var(--shadow);}}
.table-scroll{{overflow-x:auto;}}
table{{border-collapse:collapse;width:100%;min-width:820px;}}
thead th{{position:sticky;top:0;background:var(--panel-2);text-align:left;font-size:11px;color:var(--muted);padding:9px 11px;border-bottom:1px solid var(--line-strong);white-space:nowrap;}}
th.num, td.num{{text-align:right;}}
td{{padding:8px 11px;font-size:13px;white-space:nowrap;border-bottom:1px solid var(--line);}}
td.name-cell{{white-space:normal;min-width:150px;}}
.code{{color:var(--muted);font-size:11px;display:block;}}
.name{{font-weight:700;}}
.score-badge{{display:inline-flex;min-width:38px;padding:3px 7px;border-radius:6px;font-weight:800;font-size:13px;font-family:"Shippori Mincho",serif;justify-content:center;}}
.score-s{{background:var(--up-soft);color:var(--up);}}
.score-a{{background:var(--accent-soft);color:var(--accent);}}
.score-b{{background:var(--panel-2);color:var(--muted);}}
.score-warn{{background:var(--down-soft);color:var(--down);}}
footer{{margin-top:22px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px;}}
</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">日本株スクリーニング・ツール（ローカル実行）</p>
  <h1>長期上昇候補スクリーナー</h1>
  <p class="lede">お手元のPCで株探(kabutan.jp)から取得・算出した最新の候補一覧です。データ基準: {as_of}</p>
  <div class="stat-row">
    <div class="stat"><b>{stock_count}</b><span>候補銘柄数</span></div>
    <div class="stat"><b>{avg_score}</b><span>平均スコア</span></div>
    <div class="stat"><b>{top_name}</b><span>首位（{top_score}点）</span></div>
  </div>

  <details open>
    <summary>実行ログ（直近 {run_count} 件）</summary>
    <div class="log-body" id="logBody">{log_html}</div>
  </details>

  <input id="q" type="text" placeholder="銘柄名・コードで検索">
  <div class="table-shell">
    <div class="table-scroll">
      <table id="tbl">
        <thead>
          <tr>
            <th class="num">#</th><th>銘柄</th><th class="num">総合スコア</th>
            <th class="num">株価</th><th class="num">連続増益期</th><th class="num">今期予想増益率</th>
            <th class="num">200日線カイリ率</th><th>需給</th><th class="num">PER</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <footer>
    <p>本ツールは投資助言を目的としたものではありません。総合スコアは過去の業績データと株価トレンドに基づく機械的な絞り込みの目安であり、将来の株価上昇を示唆・保証するものではありません。投資判断はご自身の責任で行ってください。</p>
    <p>結果は data/screener.db（SQLite）に蓄積されています。output/summary_latest.json をClaudeとの会話に貼ると、上位銘柄や前回からの変化についてコメントをもらえます。</p>
  </footer>
</div>
<script>
var STOCKS = {stocks_json};
function fmtPct(v){{ if(v===null||v===undefined) return "－"; var s=v>0?"+":""; return s+v.toFixed(1)+"%"; }}
function scoreClass(s){{ if(s>=70) return "score-s"; if(s>=50) return "score-a"; return "score-b"; }}
function supplyClass(s){{ if(s>=65) return "score-s"; if(s>=35) return "score-a"; return "score-warn"; }}
function creditLabel(d){{
  if(d.supply_category==="r" && d.cred_ratio!=null) return d.cred_ratio.toFixed(2)+"倍";
  if(d.supply_category==="b") return "買い長";
  return "－";
}}
function render(list){{
  var body = document.getElementById("tbody");
  body.innerHTML = list.map(function(d){{
    return "<tr>"+
      "<td class='num'>"+d.rank+"</td>"+
      "<td class='name-cell'><span class='name'>"+d.name+"</span><span class='code'>"+d.code+" ・ "+d.market+"</span></td>"+
      "<td class='num'><span class='score-badge "+scoreClass(d.score)+"'>"+d.score.toFixed(1)+"</span></td>"+
      "<td class='num'>"+(d.price==null?"－":d.price.toLocaleString("ja-JP"))+"</td>"+
      "<td class='num'>"+(d.streak==null?"－":d.streak+"期")+"</td>"+
      "<td class='num'>"+fmtPct(d.this_growth)+"</td>"+
      "<td class='num'>"+fmtPct(d.dev200)+"</td>"+
      "<td><span class='score-badge "+supplyClass(d.supply_score)+"' title='需給スコア "+d.supply_score.toFixed(1)+"点'>"+creditLabel(d)+"</span></td>"+
      "<td class='num'>"+(d.per==null?"－":d.per.toFixed(1)+"倍")+"</td>"+
    "</tr>";
  }}).join("");
}}
document.getElementById("q").addEventListener("input", function(e){{
  var q = e.target.value.trim().toLowerCase();
  if(!q){{ render(STOCKS); return; }}
  render(STOCKS.filter(function(d){{
    return d.name.toLowerCase().indexOf(q)>=0 || d.code.toLowerCase().indexOf(q)>=0;
  }}));
}});
render(STOCKS);
</script>
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


def write_html_report(path, as_of, stocks, recent_runs):
    if stocks:
        avg_score = round(sum(s["score"] for s in stocks) / len(stocks), 1)
        top = stocks[0]
        top_name, top_score = top["name"], top["score"]
    else:
        avg_score, top_name, top_score = "－", "－", "－"

    log_html = "".join(_log_item_html(r) for r in recent_runs) or '<p style="color:var(--muted);margin:0;">まだ実行記録がありません。</p>'

    html = HTML_TEMPLATE.format(
        as_of=as_of,
        stock_count=len(stocks),
        avg_score=avg_score,
        top_name=top_name,
        top_score=top_score,
        run_count=len(recent_runs),
        log_html=log_html,
        stocks_json=json.dumps(stocks, ensure_ascii=False),
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
