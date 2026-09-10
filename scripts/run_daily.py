#!/usr/bin/env python3
"""KPOP DAILY 的统一入口：抓取、个性化、榜单刷新、HTML 构建。"""
import argparse
import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
KST = datetime.timezone(datetime.timedelta(hours=9))


def run(label, args, timeout, required=True):
    print("\n=== %s ===" % label, flush=True)
    try:
        result = subprocess.run([sys.executable, "-u", *args], cwd=REPO_ROOT, timeout=timeout)
    except subprocess.TimeoutExpired:
        if required:
            raise SystemExit("%s 超过 %d 秒，流水线停止" % (label, timeout))
        print("WARN: %s 超时，保留已有数据继续" % label)
        return False
    if result.returncode != 0:
        if required:
            raise SystemExit("%s 失败，退出码 %d" % (label, result.returncode))
        print("WARN: %s 失败，保留已有数据继续" % label)
        return False
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="一条命令生成 KPOP 个性化日报")
    p.add_argument("--date", help="YYYY-MM-DD，默认当前 KST 日期")
    p.add_argument("--profile", default=os.path.join(HERE, "profile.example.json"),
                   help="偏好配置 JSON")
    p.add_argument("--top", type=int, default=30, help="新闻入选上限")
    p.add_argument("--no-translate", action="store_true", help="跳过在线翻译")
    p.add_argument("--skip-melon", action="store_true", help="不单独刷新 Melon 榜")
    p.add_argument("--step-timeout", type=int, default=300,
                   help="每个流水线阶段最长等待秒数，默认 300")
    args = p.parse_args(argv)

    date = args.date or datetime.datetime.now(KST).date().isoformat()
    datetime.date.fromisoformat(date)
    daily_dir = os.path.join(REPO_ROOT, "dailies")
    os.makedirs(daily_dir, exist_ok=True)
    raw = os.path.join(daily_dir, date + ".json")
    personalized = os.path.join(daily_dir, date + ".personalized.json")
    html = os.path.join(daily_dir, date + ".personalized.html")

    fetch_args = [os.path.join(HERE, "kpop_daily_proto.py"), "--date", date,
                  "--output-dir", daily_dir]
    if args.no_translate:
        fetch_args.append("--no-translate")
    run("1/4 抓取、归一、去重", fetch_args, args.step_timeout)

    personalize_args = [os.path.join(HERE, "personalize_report.py"),
                        "--date", date, "--input", raw, "--output", personalized,
                        "--top", str(args.top)]
    if args.profile:
        personalize_args += ["--profile", os.path.abspath(args.profile)]
    run("2/4 个性化筛选", personalize_args, args.step_timeout)

    melon_ok = True
    if not args.skip_melon:
        melon_ok = run("3/4 刷新 Melon 榜",
                       [os.path.join(HERE, "patch_melon.py"), "--date", date,
                        "--input", personalized], args.step_timeout, required=False)
    else:
        print("\n=== 3/4 跳过 Melon 单源刷新 ===")

    run("4/4 构建 HTML", [os.path.join(HERE, "build_html.py"),
                           "--input", personalized, "--output", html], args.step_timeout)
    print("\nDONE: %s" % html)
    if not melon_ok:
        print("NOTE: Melon 刷新失败，HTML 保留原抓取阶段可用的榜单数据。")


if __name__ == "__main__":
    main()
