# -*- coding: utf-8 -*-
"""
実行ログを logs/ 以下のテキストファイルに保存するための共通ユーティリティ。

run.bat / run.sh のウィンドウが何らかの理由で一瞬で閉じてしまったり、
エラーが流れて見えなくなってしまっても、「何が起きたか」をあとから
確認できるように、コンソールに表示される内容をそのままログファイルにも
書き出す（screener.py と volume_watch.py の両方で共通して使う）。
"""

import os
import sys
from datetime import datetime

MAX_LOG_BYTES = 2 * 1024 * 1024  # これを超えたら古い部分を切り詰めて肥大化を防ぐ


class _Tee:
    """複数の出力先（コンソール＋ログファイルなど）に同時に書き込む。"""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
            except Exception:
                pass

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass


def _trim_if_too_large(path):
    try:
        if not os.path.exists(path):
            return
        if os.path.getsize(path) <= MAX_LOG_BYTES:
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        trimmed = content[-MAX_LOG_BYTES:]
        with open(path, "w", encoding="utf-8") as f:
            f.write("...(ログが大きくなったため、古い部分は省略しました)\n")
            f.write(trimmed)
    except OSError:
        pass


def start_logging(log_path):
    """
    以後の標準出力・標準エラー出力を、コンソール表示に加えて log_path にも
    追記するようにする。戻り値の3つ組を stop_logging() にそのまま渡すと
    元の状態に戻せる。
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    _trim_if_too_large(log_path)

    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    log_file.write("\n" + "=" * 60 + "\n")
    log_file.write("{}\n".format(datetime.now().astimezone().isoformat(timespec="seconds")))

    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(orig_stdout, log_file)
    sys.stderr = _Tee(orig_stderr, log_file)
    return orig_stdout, orig_stderr, log_file


def stop_logging(orig_stdout, orig_stderr, log_file):
    sys.stdout, sys.stderr = orig_stdout, orig_stderr
    try:
        log_file.close()
    except Exception:
        pass
