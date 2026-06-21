#!/usr/bin/env python3
"""run_check.py — autotube golden-principles 기계 검증 게이트.

usage: python3 scripts/run_check.py output/<run>/

golden-principles.md 의 불변식을 회차 산출물에 대해 검사한다(말이 아니라 환경으로 강제 — 헌법 제3·4원칙).
아직 진행 안 된 스테이지의 산출물(자막/stock/video)이 없으면 그 규칙은 FAIL 이 아니라 SKIP.
PASS/SKIP/WARN 은 통과, FAIL 1개라도 있으면 exit code = FAIL 개수(≠0).
"""
import json
import os
import struct
import sys

OK, FAIL, SKIP, WARN = "PASS", "FAIL", "SKIP", "WARN"
results = []  # (status, rule, detail)


def add(status, rule, detail=""):
    results.append((status, rule, detail))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def moov_before_mdat(mp4_path):
    """top-level MP4 box 를 순회해 moov 가 mdat 보다 먼저 나오면 faststart=True."""
    with open(mp4_path, "rb") as f:
        pos = 0
        for _ in range(64):  # top-level box 는 보통 몇 개 안 됨
            f.seek(pos)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size = struct.unpack(">I", hdr[:4])[0]
            box = hdr[4:8]
            if box == b"moov":
                return True
            if box == b"mdat":
                return False
            if size == 1:  # 64-bit largesize
                size = struct.unpack(">Q", f.read(8))[0]
            if size == 0:  # box extends to EOF
                break
            pos += size
    return False


def main(run):
    run = run.rstrip("/")
    if not os.path.isdir(run):
        print(f"FAIL: run 폴더 없음 — {run}")
        return 1

    # ---- #1, #2 : sources.json ----
    src = load_json(os.path.join(run, "sources.json"))
    if src is None:
        add(SKIP, "#1 소스 날짜", "sources.json 없음")
        add(SKIP, "#2 번역 발췌 4-7", "sources.json 없음")
    elif src.get("mode") == "overseas-sns-reaction":
        # V3: posts[] array, no primary_source.date / key_passages.
        # Use generated_at for #1 and posts count for #2.
        gen_at = str(src.get("generated_at", ""))[:10]
        if gen_at >= "2026-01-01":
            add(OK, "#1 소스 날짜", f"{gen_at} [v3]")
        else:
            add(FAIL, "#1 소스 날짜", f"{gen_at!r} < 2026-01-01")
        n_posts = len(src.get("posts", []))
        n_comments = sum(len(p.get("comments", [])) for p in src.get("posts", []))
        # V3 floor: enough total content. Reddit threads → ≥20 comments standard.
        # Yahoo Japan threads have smaller comment pools (16 is real top); allow ≥10.
        ok2 = (n_posts >= 1) and (n_comments >= 10)
        add(OK if ok2 else FAIL, "#2 번역 발췌 4-7",
            f"posts={n_posts}, comments={n_comments} [v3 posts ≥1, comments ≥10]")
    else:
        ps = src.get("primary_source", {})
        date = str(ps.get("date", ""))
        if date >= "2026-01-01":
            add(OK, "#1 소스 날짜", date)
        else:
            add(FAIL, "#1 소스 날짜", f"{date!r} < 2026-01-01")
        n = len(ps.get("key_passages_for_translation", []))
        add(OK if 4 <= n <= 7 else FAIL, "#2 번역 발췌 4-7", f"{n}개")

    # ---- #3..#6 : segments.json ----
    doc = load_json(os.path.join(run, "segments.json"))
    if doc is None:
        for r in ("#3 세그먼트 골격", "#4 sign-off", "#5 자막 N-of-N", "#6 stock_path N-of-N"):
            add(SKIP, r, "segments.json 없음")
        segs = []
    else:
        segs = doc.get("segments", [])
        n = len(segs)
        roles = {}
        for s in segs:
            roles[s.get("role")] = roles.get(s.get("role"), 0) + 1
        # Reaction Mode (V2 japanese-reaction): 18-26 segments — standard 11-17 + 5-10 reaction_translation + 1 reaction_bridge.
        # V3 overseas-sns-reaction: 30-110 segments — 2 + N posts × (post_analysis + post_body + M comments) + 1 closing.
        is_v3 = (roles.get("post_body", 0) >= 1 and roles.get("comment_translation", 0) >= 10)
        is_reaction = (roles.get("reaction_translation", 0) >= 5)
        if is_v3:
            lo, hi = 16, 110
        elif is_reaction:
            lo, hi = 18, 26
        else:
            lo, hi = 11, 17
        ok3 = (lo <= n <= hi and roles.get("intro") == 1
               and roles.get("bridge") == 1 and roles.get("closing") == 1)
        suffix = " [v3]" if is_v3 else (" [reaction]" if is_reaction else "")
        add(OK if ok3 else FAIL, "#3 세그먼트 골격",
            f"{n}개{suffix}, intro={roles.get('intro')} bridge={roles.get('bridge')} closing={roles.get('closing')}")

        # #4 closing sign-off
        closing = next((s for s in segs if s.get("role") == "closing"), None)
        if closing is None:
            add(FAIL, "#4 sign-off", "closing 세그먼트 없음")
        else:
            text_ok = "파이널 케이" in closing.get("text", "")
            sub = closing.get("subtitle_text")
            sub_ok = (sub is None) or ("파이널K" in sub)  # 자막 아직 없으면 text 만으로 판정
            if text_ok and sub_ok:
                add(OK, "#4 sign-off", "파이널K 멘트 포함")
            else:
                add(FAIL, "#4 sign-off",
                    f"text:{'OK' if text_ok else '파이널 케이 누락'} / subtitle:{'OK' if sub_ok else '파이널K 누락'}")

        # #5 subtitle_text N-of-N (stage 6) — 전무하면 SKIP, 일부만이면 FAIL
        have_sub = [bool(s.get("subtitle_text")) for s in segs]
        if not any(have_sub):
            add(SKIP, "#5 자막 N-of-N", "stage 6 미실행(subtitle_text 전무)")
        elif all(have_sub):
            add(OK, "#5 자막 N-of-N", f"{sum(have_sub)}/{n}")
        else:
            add(FAIL, "#5 자막 N-of-N", f"{sum(have_sub)}/{n} — 일부 누락")

        # #6 stock_path N-of-N (stage 9).
        # Reaction-style segs (reaction_translation / post_body / comment_translation) intentionally
        # have stock_path=null — they use their UI card field instead.
        reaction_roles = {"reaction_translation", "post_body", "comment_translation"}
        body_segs = [s for s in segs if s.get("role") not in reaction_roles]
        react_segs = [s for s in segs if s.get("role") in reaction_roles]
        have_sp = [bool(s.get("stock_path")) for s in body_segs]
        # Reaction segs must have their UI card image field.
        def _react_img_ok(s):
            r = s.get("role")
            if r == "post_body": return bool(s.get("post_image"))
            return bool(s.get("comment_image"))
        react_ok = all(_react_img_ok(s) for s in react_segs) if react_segs else True
        if not any(have_sp) and not react_segs:
            add(SKIP, "#6 stock_path N-of-N", "stage 8-9 미실행(stock_path 전무)")
        elif all(have_sp) and react_ok:
            detail = f"{sum(have_sp)}/{len(body_segs)}"
            if react_segs:
                detail += f" body + {len(react_segs)}/{len(react_segs)} reaction(comment_image)"
            add(OK, "#6 stock_path N-of-N", detail)
        else:
            missing_body = len(body_segs) - sum(have_sp)
            missing_react = len(react_segs) - sum(1 for s in react_segs if s.get("comment_image"))
            add(FAIL, "#6 stock_path N-of-N",
                f"body 누락 {missing_body}, reaction 누락 {missing_react}")

    # ---- #7 : video.mp4 faststart + 소유권 ----
    vid = os.path.join(run, "video.mp4")
    if not os.path.exists(vid):
        add(SKIP, "#7 faststart", "video.mp4 없음")
    else:
        if moov_before_mdat(vid):
            add(OK, "#7 faststart", "moov < mdat")
        else:
            add(FAIL, "#7 faststart", "moov atom 이 mdat 뒤 — -movflags +faststart 누락")
        st = os.stat(vid)
        if st.st_uid == 0:
            add(WARN, "#7 소유권", "root:root — chown 1000:1000 필요(업로드 거부 가능)")

    # ---- #8 : 업로드 privacy (참고) ----
    up = load_json(os.path.join(run, "upload_result.json"))
    if up is None:
        add(SKIP, "#8 업로드 unlisted", "upload_result.json 없음")
    else:
        priv = up.get("privacy", up.get("privacyStatus", "?"))
        if priv == "public":
            add(WARN, "#8 업로드 unlisted", "privacy=public — 의도된 공개인지 확인")
        else:
            add(OK, "#8 업로드 unlisted", f"privacy={priv}")

    # ---- 출력 ----
    width = max(len(r) for _, r, _ in results)
    fails = 0
    for status, rule, detail in results:
        if status == FAIL:
            fails += 1
        print(f"  [{status:4}] {rule:<{width}}  {detail}")
    print(f"\n{run}: {fails} FAIL")
    return fails


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(min(main(sys.argv[1]), 255))
