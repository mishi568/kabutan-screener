# -*- coding: utf-8 -*-
"""
kabutan-screener のGUIダッシュボード。

使い方:
  pip install -r requirements.txt
  streamlit run app.py

ブラウザが自動で開き、http://localhost:8501 でダッシュボードが表示されます。
"""

import sys
import re
import subprocess
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import json

from db import get_conn, add_holding, remove_holding, get_active_holdings, get_all_holdings
from config import RANKINGS, MARKET_INDICES
from backtest import TARGET_PRESETS, signal_win_rates, combo_win_rate

st.set_page_config(page_title="Kabutan Screener", layout="wide")
st.title("📈 Kabutan Screener ダッシュボード")

# ============ メイン画面上部：実行状況 ============
st.subheader("▶ 実行状況")
status_msg = st.empty()
progress_holder = st.empty()
log_holder = st.empty()
status_msg.caption("サイドバーのボタンを押すと、ここに進捗とログがリアルタイムに表示されます。")
st.divider()

# ============ メイン画面：AIダイジェスト（コピーしてAIに貼り付け） ============
st.subheader("📋 AIダイジェスト（コピーしてAIチャットに貼り付け）")
brief_files = sorted(Path(".").glob("ai_brief_*.md"), reverse=True)
if brief_files:
    latest_brief = brief_files[0]
    st.caption(f"{latest_brief.name}　※コードブロック右上のアイコンでコピーできます")
    st.code(latest_brief.read_text(encoding="utf-8"), language="markdown")
else:
    st.info("まだダイジェストがありません。サイドバーの「🚀 全自動実行」または⑥を実行してください。")
st.divider()


# ============ サイドバー：操作 ============
st.sidebar.header("操作")

STEP_PATTERN = re.compile(r"\[(\d+)/(\d+)\]")


def run_script(args: list[str], label: str, total_steps: int | None = None) -> bool:
    """スクリプトをサブプロセスで実行し、メイン画面上部に進捗・出力をリアルタイム表示する。
    戻り値は成功したかどうか（exit code 0ならTrue）。"""
    status_msg.info(f"▶ {label} 実行中…")
    progress_bar = progress_holder.progress(0.0) if total_steps else None

    output_lines: list[str] = []
    done_steps = 0

    process = subprocess.Popen(
        [sys.executable, "-u"] + args,  # -u: 子プロセスのstdoutをアンバッファ化
                                          # （付けないとパイプ経由ではブロックバッファリングされ、
                                          #   プロセス終了までログが逐次表示されない）
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        output_lines.append(line)

        # "[3/30]" のような行があれば、そこから直接進捗を読み取る
        m = STEP_PATTERN.search(line)
        if m and progress_bar is not None:
            current, total = int(m.group(1)), int(m.group(2))
            progress_bar.progress(min(current / total, 1.0))
        # run_daily.pyのように [OK]/[NG] で1件ずつ完了を示すタイプはそれを数える
        elif total_steps and ("[OK]" in line or "[NG]" in line):
            done_steps += 1
            progress_bar.progress(min(done_steps / total_steps, 1.0))

        # 直近の意味のある行だけを「現在の状況」として太字表示
        stripped = line.strip()
        if stripped:
            status_msg.info(f"▶ {label} 実行中…\n\n**{stripped}**")

        log_holder.code("".join(output_lines[-30:]))

    process.wait()
    if progress_bar is not None:
        progress_bar.progress(1.0)

    if process.returncode == 0:
        status_msg.success(f"✅ {label} 完了")
    else:
        status_msg.error(f"❌ {label} 失敗 (exit={process.returncode})")

    return process.returncode == 0


st.sidebar.divider()
top_n = st.sidebar.number_input("個別詳細・ダイジェストの対象数", min_value=1, max_value=30, value=10)
pages_n = st.sidebar.number_input("株価ヒストリーの取得ページ数（1ページ≒1ヶ月弱）", min_value=1, max_value=9, value=3)
st.sidebar.divider()

if st.sidebar.button("🚀 全自動実行（地合い＋①〜⑥をまとめて実行）", use_container_width=True, type="primary"):
    steps = [
        (["fetch_market_index.py", "--pages", "2"], "🌐 地合い記録 (fetch_market_index.py)", len(MARKET_INDICES)),
        (["run_daily.py"], "① 日次収集 (run_daily.py)", len(RANKINGS)),
        (["flag_watch_list.py"], "② ウォッチリスト記録 (flag_watch_list.py)", None),
        (
            ["score_ranking.py", "--days", "1", "--top", str(top_n), "--min-score", "1"],
            "③ スコアリング (score_ranking.py)",
            None,
        ),
        (["fetch_stock_detail.py", "--top", str(top_n)], "④ 個別銘柄詳細取得 (fetch_stock_detail.py)", int(top_n)),
        (
            ["fetch_price_history.py", "--top", str(top_n), "--pages", str(pages_n)],
            "⑤ 株価ヒストリー取得 (fetch_price_history.py)",
            int(top_n),
        ),
        (["compile_ai_brief.py", "--top", str(top_n)], "⑥ AIダイジェスト生成 (compile_ai_brief.py)", None),
        (["fetch_holdings_price.py"], "💼 保有銘柄の株価更新 (fetch_holdings_price.py)", None),
        (["run_macro_sync.py"], "🌐 マクロ・需給データ取得 (run_macro_sync.py)", 14),
    ]

    overall = st.sidebar.empty()
    all_ok = True
    for i, (args, label, total_steps) in enumerate(steps):
        overall.caption(f"全体進捗: {i}/{len(steps)} ステップ完了 — 次: {label}")
        ok = run_script(args, label, total_steps=total_steps)
        if not ok:
            overall.error(f"全体進捗: {i}/{len(steps)} で停止（{label} が失敗）")
            all_ok = False
            break

    if all_ok:
        overall.caption(f"全体進捗: {len(steps)}/{len(steps)} 完了 ✅ 下の「AIダイジェスト」をコピーしてAIに貼り付けてください")

st.sidebar.divider()
st.sidebar.caption("個別ステップを手動で実行したい場合はこちら")

if st.sidebar.button("① 日次収集を実行", use_container_width=True):
    run_script(["run_daily.py"], "日次収集 (run_daily.py)", total_steps=len(RANKINGS))

if st.sidebar.button("② 時間差シグナルを記録", use_container_width=True):
    run_script(["flag_watch_list.py"], "ウォッチリスト記録 (flag_watch_list.py)")

if st.sidebar.button("③ スコアリング実行", use_container_width=True):
    run_script(
        ["score_ranking.py", "--days", "1", "--top", str(top_n), "--min-score", "1"],
        "スコアリング (score_ranking.py)",
    )

if st.sidebar.button("④ 個別銘柄詳細を取得", use_container_width=True):
    run_script(
        ["fetch_stock_detail.py", "--top", str(top_n)],
        "個別銘柄詳細取得 (fetch_stock_detail.py)",
        total_steps=int(top_n),
    )

if st.sidebar.button("⑤ 株価ヒストリーを取得", use_container_width=True):
    run_script(
        ["fetch_price_history.py", "--top", str(top_n), "--pages", str(pages_n)],
        "株価ヒストリー取得 (fetch_price_history.py)",
        total_steps=int(top_n),
    )

if st.sidebar.button("⑥ AIダイジェスト生成", use_container_width=True):
    run_script(["compile_ai_brief.py", "--top", str(top_n)], "AIダイジェスト生成 (compile_ai_brief.py)")

if st.sidebar.button("🌐 地合い（市場指数）を取得", use_container_width=True):
    run_script(
        ["fetch_market_index.py", "--pages", "2"],
        "地合い記録 (fetch_market_index.py)",
        total_steps=len(MARKET_INDICES),
    )

if st.sidebar.button("💼 保有銘柄の株価を更新", use_container_width=True):
    run_script(["fetch_holdings_price.py"], "保有銘柄の株価更新 (fetch_holdings_price.py)")

if st.sidebar.button("🌐 マクロ・需給データを取得（JPX/EDINET/nikkei225jp.com）", use_container_width=True):
    run_script(["run_macro_sync.py"], "マクロ・需給データ取得 (run_macro_sync.py)", total_steps=14)

st.sidebar.divider()
if st.sidebar.button("データ健全性チェック", use_container_width=True):
    run_script(["check_data_health.py"], "健全性チェック (check_data_health.py)")


# ============ メイン：タブ ============
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["📊 スコアリング結果", "📋 ランキング一覧", "📈 個別銘柄チャート", "🗂 データ概況", "🎯 シグナル勝率", "💼 保有銘柄", "🌐 マクロ・需給データ"]
)

conn = get_conn()

with tab1:
    st.subheader("直近のスコアリング結果（signal_score）")
    df_signal = pd.read_sql_query(
        """
        SELECT sp.pick_date, sp.code, s.name, s.market, sp.score
        FROM screening_picks sp
        JOIN stocks s ON s.code = sp.code
        WHERE sp.funnel_key = 'signal_score'
          AND sp.pick_date = (SELECT MAX(pick_date) FROM screening_picks WHERE funnel_key = 'signal_score')
        ORDER BY sp.score DESC
        """,
        conn,
    )
    if df_signal.empty:
        st.info("まだデータがありません。サイドバーの①③を実行してください。")
    else:
        st.dataframe(df_signal, use_container_width=True, hide_index=True)

    st.subheader("AI定性ランキング（ai_qualitative_rank）")
    df_ai = pd.read_sql_query(
        """
        SELECT sp.pick_date, sp.code, s.name, s.market, sp.score
        FROM screening_picks sp
        JOIN stocks s ON s.code = sp.code
        WHERE sp.funnel_key = 'ai_qualitative_rank'
          AND sp.pick_date = (SELECT MAX(pick_date) FROM screening_picks WHERE funnel_key = 'ai_qualitative_rank')
        ORDER BY sp.score DESC
        """,
        conn,
    )
    if df_ai.empty:
        st.info("まだAI判断の記録がありません（record_ai_ranking.py未実行）。")
    else:
        st.dataframe(df_ai, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("ランキング別一覧")
    rankings_df = pd.read_sql_query("SELECT ranking_key, title FROM rankings ORDER BY ranking_key", conn)
    dates_df = pd.read_sql_query(
        "SELECT DISTINCT snapshot_date FROM ranking_snapshots ORDER BY snapshot_date DESC", conn
    )

    if rankings_df.empty or dates_df.empty:
        st.info("まだデータがありません。サイドバーの①を実行してください。")
    else:
        title_map = dict(zip(rankings_df["ranking_key"], rankings_df["title"]))
        col1, col2 = st.columns(2)
        with col1:
            selected_ranking = st.selectbox(
                "ランキング選択", rankings_df["ranking_key"], format_func=lambda k: f"{title_map.get(k, k)} ({k})"
            )
        with col2:
            selected_date = st.selectbox("日付選択", dates_df["snapshot_date"])

        df_rank = pd.read_sql_query(
            "SELECT rank, code, name, market, extra FROM ranking_snapshots "
            "WHERE ranking_key = ? AND snapshot_date = ? ORDER BY rank",
            conn,
            params=(selected_ranking, selected_date),
        )
        st.dataframe(df_rank, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("個別銘柄の株価チャート")
    codes_df = pd.read_sql_query("SELECT DISTINCT code FROM price_history ORDER BY code", conn)

    if codes_df.empty:
        st.info("株価ヒストリーがまだありません。fetch_price_history.pyを実行してください。")
    else:
        selected_code = st.selectbox("銘柄コード", codes_df["code"])
        name_row = conn.execute("SELECT name FROM stocks WHERE code = ?", (selected_code,)).fetchone()
        if name_row:
            st.caption(f"銘柄名: {name_row[0]}")

        df_price = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM price_history WHERE code = ? ORDER BY date",
            conn,
            params=(selected_code,),
        )
        df_price["date"] = pd.to_datetime(df_price["date"])
        df_price = df_price.set_index("date")

        st.line_chart(df_price["close"])
        st.caption("出来高")
        st.bar_chart(df_price["volume"])
        st.dataframe(df_price.sort_index(ascending=False), use_container_width=True)

with tab4:
    st.subheader("データ概況")
    n_stocks = pd.read_sql_query("SELECT COUNT(*) AS n FROM stocks", conn).iloc[0]["n"]
    n_dates = pd.read_sql_query(
        "SELECT COUNT(DISTINCT snapshot_date) AS n FROM ranking_snapshots", conn
    ).iloc[0]["n"]
    latest_date_row = pd.read_sql_query("SELECT MAX(snapshot_date) AS d FROM ranking_snapshots", conn).iloc[0]
    latest_date = latest_date_row["d"] or "-"

    c1, c2, c3 = st.columns(3)
    c1.metric("登録銘柄数", n_stocks)
    c2.metric("収集済み日数", n_dates)
    c3.metric("最終収集日", latest_date)

    st.subheader("最近の実行ログ（run_log.txt）")
    log_path = Path("run_log.txt")
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        st.code("\n".join(lines[-100:]) or "(ログは空です)")
    else:
        st.info("run_log.txtがまだありません（run_daily.batなどログをファイルに残す実行方法を使うと表示されます）")

with tab5:
    st.subheader("🎯 シグナル別勝率（バックテスト）")
    st.caption(
        "各シグナルが出た銘柄について、その後の株価がprice_historyに十分溜まっているものだけを判定します。"
        "直近のシグナルは判定期間分の営業日がまだ経過していないため対象外になります。"
        "運用を続けてデータが溜まるほど判定件数が増えていきます。"
    )

    preset_name = st.selectbox("判定ルール", list(TARGET_PRESETS.keys()) + ["カスタム"])
    if preset_name == "カスタム":
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            horizon = st.number_input("判定期間（営業日）", min_value=1, max_value=60, value=20)
        with col_b:
            rule = st.selectbox(
                "判定方法", ["close", "max_high"],
                format_func=lambda r: "期間後の終値" if r == "close" else "期間内の最高値",
            )
        with col_c:
            threshold = st.number_input("勝ち判定の閾値（%）", value=0.0, step=0.5)
    else:
        preset = TARGET_PRESETS[preset_name]
        horizon, rule, threshold = preset["horizon_days"], preset["rule"], preset["threshold_pct"]
        rule_label = "期間後の終値" if rule == "close" else "期間内の最高値"
        st.caption(f"判定期間: {horizon}営業日 / 判定方法: {rule_label} / 閾値: {threshold}%")

    summary_df, merged_df = signal_win_rates(conn, horizon_days=int(horizon), rule=rule, threshold_pct=float(threshold))

    if summary_df.empty:
        st.info(
            "判定可能な実績がまだありません。シグナル発生日から判定期間分の株価データ"
            "（サイドバーの⑤やfetch_price_history.pyで取得）が必要です。"
            "運用を続けてデータが溜まってから確認してください。"
        )
    else:
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        st.bar_chart(summary_df.set_index("ranking_key")["勝率(%)"])

        st.divider()
        st.subheader("🔀 2シグナル重複時の勝率比較")
        st.caption("2つのシグナルが同じ日に重なって出た銘柄だけに絞ると、勝率はどう変わるか比較できます。")

        keys = summary_df["ranking_key"].tolist()
        col_a, col_b = st.columns(2)
        with col_a:
            key_a = st.selectbox("シグナルA", keys, key="combo_a")
        with col_b:
            key_b = st.selectbox("シグナルB", keys, index=min(1, len(keys) - 1), key="combo_b")

        solo_a = summary_df[summary_df["ranking_key"] == key_a].iloc[0]
        solo_b = summary_df[summary_df["ranking_key"] == key_b].iloc[0]
        combo = combo_win_rate(merged_df, key_a, key_b)

        c1, c2, c3 = st.columns(3)
        c1.metric(f"{key_a}（単体）", f"{solo_a['勝率(%)']}%", f"件数 {solo_a['件数']}")
        c2.metric(f"{key_b}（単体）", f"{solo_b['勝率(%)']}%", f"件数 {solo_b['件数']}")
        if combo["件数"] > 0:
            c3.metric("重複時", f"{combo['勝率(%)']}%", f"件数 {combo['件数']}")
        else:
            c3.metric("重複時", "データなし", "件数 0")

with tab6:
    st.subheader("💼 保有銘柄")
    st.caption(
        "実際に保有している銘柄を登録すると、株価と参考情報（PER/PBR/信用倍率/業績推移/信用残週次）を"
        "サイドバーの「💼 保有銘柄の株価を更新」または「🚀 全自動実行」でまとめて取得できます。"
        "price_historyとは別のholdings_price_historyに、常に最新の値動きを取り直す形で保存します。"
    )

    with st.form("add_holding_form", clear_on_submit=True):
        col_a, col_b = st.columns([1, 2])
        with col_a:
            new_code = st.text_input("銘柄コード")
        with col_b:
            new_memo = st.text_input("メモ（任意）")
        submitted = st.form_submit_button("追加")
        if submitted and new_code.strip():
            code_to_add = new_code.strip()
            existing_name_row = conn.execute("SELECT name FROM stocks WHERE code = ?", (code_to_add,)).fetchone()
            add_holding(
                conn, code_to_add,
                added_date=datetime.date.today().isoformat(),
                name=existing_name_row[0] if existing_name_row else None,
                memo=new_memo.strip() or None,
            )
            st.success(f"{code_to_add} を保有銘柄に追加しました。")
            st.rerun()

    st.divider()

    holdings_rows = get_all_holdings(conn)
    active_rows = [r for r in holdings_rows if r[4] is None]  # removed_date is None

    if not active_rows:
        st.info("保有銘柄が登録されていません。上のフォームから追加してください。")
    else:
        holdings_df = pd.DataFrame(active_rows, columns=["code", "name", "memo", "added_date", "removed_date"])
        holdings_df["name"] = holdings_df["name"].fillna("(名称未取得)")
        holdings_df["memo"] = holdings_df["memo"].fillna("")

        st.subheader("現在の保有銘柄")
        st.dataframe(holdings_df[["code", "name", "memo", "added_date"]], use_container_width=True, hide_index=True)

        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            remove_code = st.selectbox("解除する銘柄（売却済みにする）", holdings_df["code"])
        with col_r2:
            st.write("")
            if st.button("解除する"):
                remove_holding(conn, remove_code, removed_date=datetime.date.today().isoformat())
                st.success(f"{remove_code} を解除しました。")
                st.rerun()

        st.divider()
        st.subheader("保有銘柄の値動き・参考情報")
        selected_hcode = st.selectbox("表示する銘柄", holdings_df["code"], key="holdings_chart_code")

        df_hprice = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM holdings_price_history WHERE code = ? ORDER BY date",
            conn, params=(selected_hcode,),
        )
        if df_hprice.empty:
            st.info("この銘柄の株価データがまだありません。「💼 保有銘柄の株価を更新」を実行してください。")
        else:
            df_hprice["date"] = pd.to_datetime(df_hprice["date"])
            df_hprice = df_hprice.set_index("date")
            st.line_chart(df_hprice["close"])
            st.caption("出来高")
            st.bar_chart(df_hprice["volume"])
            st.dataframe(df_hprice.sort_index(ascending=False), use_container_width=True)

        detail_row = conn.execute(
            "SELECT snapshot_date, data_json FROM stock_details WHERE code = ? ORDER BY snapshot_date DESC LIMIT 1",
            (selected_hcode,),
        ).fetchone()
        if detail_row:
            snapshot_date, data_json = detail_row
            detail = json.loads(data_json)
            st.caption(f"参考情報（{snapshot_date}時点）")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("PER", detail.get("per") or "-")
            c2.metric("PBR", detail.get("pbr") or "-")
            c3.metric("利回り", detail.get("yield") or "-")
            c4.metric("信用倍率", detail.get("margin_ratio") or "-")
            c5.metric("時価総額", detail.get("market_cap") or "-")

            fin = detail.get("financials") or []
            if fin:
                st.caption("業績推移（決算期 / 売上高 / 経常益 / 最終益 / 1株益 / 1株配）")
                st.dataframe(pd.DataFrame(fin), use_container_width=True, hide_index=True)

            mh = detail.get("margin_history") or []
            if mh:
                st.caption("信用残 週次推移（日付 / 売り残 / 買い残 / 倍率）")
                st.dataframe(pd.DataFrame(mh), use_container_width=True, hide_index=True)
        else:
            st.info("この銘柄の参考情報（PER/PBR等）がまだありません。「💼 保有銘柄の株価を更新」を実行してください。")

with tab7:
    st.subheader("🌐 マクロ・需給データ")
    st.caption(
        "株探以外のデータ源（JPX公式・EDINET・nikkei225jp.com）。"
        "サイドバーの「🌐 マクロ・需給データを取得」または「🚀 全自動実行」で更新できます。"
    )

    def _latest_row(table: str):
        row = conn.execute(f"SELECT * FROM {table} ORDER BY date DESC LIMIT 1").fetchone()
        if row is None:
            return None
        cols = [d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
        return dict(zip(cols, row))

    nt = _latest_row("nikkei225jp_nt_ratio")
    fear = _latest_row("nikkei225jp_fear_index")
    arb = _latest_row("nikkei225jp_arbitrage")
    karauri = _latest_row("nikkei225jp_short_selling")
    sinyou = _latest_row("nikkei_margin_records")

    if not any([nt, fear, arb, karauri, sinyou]):
        st.info("まだデータがありません。サイドバーの「🌐 マクロ・需給データを取得」を実行してください。")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("NT倍率（日経平均/TOPIX）", f"{nt['nt_ratio']:.2f}" if nt and nt["nt_ratio"] is not None else "-",
                   help=f"基準日: {nt['date']}" if nt else None)
        c2.metric("日本VI（恐怖指数）", f"{fear['japan_vi']:.2f}" if fear and fear["japan_vi"] is not None else "-",
                   help=f"基準日: {fear['date']}" if fear else None)
        c3.metric("裁定買い残-売り残差引（千株）",
                   f"{arb['net_shares']:,.0f}" if arb and arb["net_shares"] is not None else "-",
                   help=f"基準日: {arb['date']}" if arb else None)
        c4.metric("空売り比率（nikkei225jp.com）",
                   f"{karauri['short_ratio_total']:.1f}%" if karauri and karauri["short_ratio_total"] is not None else "-",
                   help=f"基準日: {karauri['date']}" if karauri else None)
        c5.metric("信用倍率（東証全体）",
                   f"{sinyou['margin_ratio']:.2f}倍" if sinyou and sinyou["margin_ratio"] is not None else "-",
                   help=f"基準日: {sinyou['date']}" if sinyou else None)

    st.divider()

    st.subheader("📉 JPX信用倍率が低い個別銘柄（売り長＝踏み上げ期待）")
    df_low_margin = pd.read_sql_query(
        """
        SELECT code, name, margin_buy, margin_sell, margin_ratio, date
        FROM jpx_margin_positions
        WHERE date = (SELECT MAX(date) FROM jpx_margin_positions)
          AND margin_ratio IS NOT NULL
        ORDER BY margin_ratio ASC
        LIMIT 30
        """,
        conn,
    )
    if df_low_margin.empty:
        st.info("データがありません。")
    else:
        st.dataframe(df_low_margin, use_container_width=True, hide_index=True)

    st.subheader("🏦 機関投資家の空売りポジション集中銘柄（0.5%ルール開示分）")
    df_short_conc = pd.read_sql_query(
        """
        SELECT code, SUM(short_position_ratio) AS total_ratio, COUNT(*) AS holder_count, MAX(date) AS date
        FROM jpx_short_positions
        WHERE date = (SELECT MAX(date) FROM jpx_short_positions)
        GROUP BY code
        ORDER BY total_ratio DESC
        LIMIT 30
        """,
        conn,
    )
    if df_short_conc.empty:
        st.info("データがありません。")
    else:
        st.dataframe(df_short_conc, use_container_width=True, hide_index=True)

    st.subheader("📄 EDINET大量保有報告書（直近30日）")
    df_edinet = pd.read_sql_query(
        """
        SELECT date, code, issuer_name, holder_name, holding_ratio, report_type
        FROM edinet_large_holdings
        WHERE date >= date('now', '-30 days')
        ORDER BY date DESC
        LIMIT 50
        """,
        conn,
    )
    if df_edinet.empty:
        st.info("データがありません（EDINET_API_KEY未設定の場合は取得されません）。")
    else:
        st.dataframe(df_edinet, use_container_width=True, hide_index=True)

conn.close()
