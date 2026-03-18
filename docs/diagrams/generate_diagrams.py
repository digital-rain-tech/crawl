#!/usr/bin/env python3
"""Generate Excalidraw diagrams for Crawl demo."""
import json
import uuid

def gid():
    return uuid.uuid4().hex[:12]

def make_rect(id, x, y, w, h, bg="#ffffff", stroke="#1e1e1e", stroke_w=2, roundness=None, opacity=100):
    r = {
        "id": id, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": stroke, "backgroundColor": bg,
        "fillStyle": "solid", "strokeWidth": stroke_w, "strokeStyle": "solid",
        "roughness": 1, "opacity": opacity, "groupIds": [], "frameId": None,
        "roundness": roundness or {"type": 3},
        "seed": hash(id) % 2**31, "version": 1, "versionNonce": hash(id+"v") % 2**31,
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False,
    }
    return r

def make_text(id, x, y, w, h, text, font_size=16, color="#1e1e1e", container_id=None, align="center"):
    t = {
        "id": id, "type": "text",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": None,
        "seed": hash(id) % 2**31, "version": 1, "versionNonce": hash(id+"v") % 2**31,
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False,
        "text": text, "fontSize": font_size, "fontFamily": 5, "textAlign": align,
        "verticalAlign": "middle" if container_id else "top",
        "containerId": container_id, "originalText": text, "autoResize": True,
        "lineHeight": 1.25,
    }
    return t

def make_arrow(id, x, y, points, start_id=None, end_id=None, color="#1e1e1e", stroke_w=2, style="solid", label=None):
    a = {
        "id": id, "type": "arrow",
        "x": x, "y": y, "width": abs(points[-1][0]), "height": abs(points[-1][1]),
        "angle": 0, "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": stroke_w, "strokeStyle": style,
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": {"type": 2},
        "seed": hash(id) % 2**31, "version": 1, "versionNonce": hash(id+"v") % 2**31,
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False,
        "points": points,
        "startBinding": {"elementId": start_id, "focus": 0, "gap": 5, "fixedPoint": None} if start_id else None,
        "endBinding": {"elementId": end_id, "focus": 0, "gap": 5, "fixedPoint": None} if end_id else None,
        "lastCommittedPoint": None, "startArrowhead": None, "endArrowhead": "arrow",
        "elbowed": False,
    }
    return a

def labeled_rect(x, y, w, h, text, bg="#ffffff", stroke="#1e1e1e", stroke_w=2, font_size=14, roundness=None, text_color="#1e1e1e"):
    rid = gid()
    tid = gid()
    r = make_rect(rid, x, y, w, h, bg=bg, stroke=stroke, stroke_w=stroke_w, roundness=roundness)
    t = make_text(tid, x+5, y+5, w-10, h-10, text, font_size=font_size, container_id=rid, color=text_color)
    r["boundElements"].append({"id": tid, "type": "text"})
    return rid, r, t

def arrow_between(sx, sy, sw, sh, tx, ty, tw, th, src_id, tgt_id, color="#495057", stroke_w=2, style="solid"):
    """Create arrow from right edge of source to left edge of target."""
    aid = gid()
    start_x = sx + sw + 5
    start_y = sy + sh / 2
    end_x = tx - 5
    end_y = ty + th / 2
    dx = end_x - start_x
    dy = end_y - start_y
    a = make_arrow(aid, start_x, start_y, [[0, 0], [dx, dy]], start_id=src_id, end_id=tgt_id, color=color, stroke_w=stroke_w, style=style)
    return aid, a

def arrow_down(sx, sy, sw, sh, tx, ty, tw, th, src_id, tgt_id, color="#495057", stroke_w=2, style="solid"):
    """Create arrow from bottom of source to top of target."""
    aid = gid()
    start_x = sx + sw / 2
    start_y = sy + sh + 5
    end_x = tx + tw / 2
    end_y = ty - 5
    dx = end_x - start_x
    dy = end_y - start_y
    a = make_arrow(aid, start_x, start_y, [[0, 0], [dx, dy]], start_id=src_id, end_id=tgt_id, color=color, stroke_w=stroke_w, style=style)
    return aid, a


# ============================================================
# DIAGRAM 1: ETL Pipeline Lineage
# ============================================================
def generate_etl_lineage():
    elements = []

    # Colors
    ORACLE_BG = "#fff3bf"  # amber
    ORACLE_STROKE = "#e67700"
    HIVE_BG = "#d0ebff"  # blue
    HIVE_STROKE = "#1971c2"
    HDFS_BG = "#d3f9d8"  # green
    HDFS_STROKE = "#2f9e44"
    MAP_BG = "#f1f3f5"  # light gray
    MAP_STROKE = "#495057"
    TARGET_STROKE_W = 3
    RISK_BG = "#ffc9c9"
    RISK_STROKE = "#e03131"
    ARROW_COLOR = "#495057"

    W_SRC = 180  # source table width
    W_MAP = 200  # mapping width
    W_STG = 195  # staging table width
    W_TGT = 210  # target width
    H = 50  # standard height

    # Title
    title_id = gid()
    elements.append(make_text(title_id, 300, 30, 800, 40, "ODI Movie Pipeline — Data Lineage & Migration Risks", font_size=28, color="#1e1e1e"))

    # Subtitle
    sub_id = gid()
    elements.append(make_text(sub_id, 370, 72, 650, 25, "Oracle Big Data Lite demo repository  •  8 mappings  •  5 cross-platform hops", font_size=14, color="#868e96"))

    # ── Row 1: Movie Ingest (y=140) ──
    r1_y = 140
    src1_x, src1_y = 60, r1_y
    id_oracle_movie, *el = labeled_rect(src1_x, src1_y, W_SRC, H, "Oracle.MOVIE", bg=ORACLE_BG, stroke=ORACLE_STROKE, font_size=14)
    elements.extend(el)

    map1_x, map1_y = 310, r1_y
    id_a_sqoop, *el = labeled_rect(map1_x, map1_y, W_MAP, H, "A: Load Movies\n(Sqoop)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3})
    elements.extend(el)

    stg1_x, stg1_y = 580, r1_y
    id_movie_updates, *el = labeled_rect(stg1_x, stg1_y, W_STG, H, "Hive.movie_updates", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    # Arrow: Oracle.MOVIE → A: Sqoop
    aid, a = arrow_between(src1_x, src1_y, W_SRC, H, map1_x, map1_y, W_MAP, H, id_oracle_movie, id_a_sqoop, color=ARROW_COLOR)
    el[0]["boundElements"] = el[0].get("boundElements", [])  # the rect
    elements.append(a)

    # Arrow: A: Sqoop → movie_updates
    aid, a = arrow_between(map1_x, map1_y, W_MAP, H, stg1_x, stg1_y, W_STG, H, id_a_sqoop, id_movie_updates, color=ARROW_COLOR)
    elements.append(a)

    # Risk callout on Sqoop mapping
    risk1_id, *el = labeled_rect(310, 90, 200, 36, "⚠ SYSDATE → needs translation", bg=RISK_BG, stroke=RISK_STROKE, stroke_w=1, font_size=11, text_color="#c92a2a")
    elements.extend(el)

    # ── Row 2: Merge (y=250) ──
    r2_y = 250
    map2_x, map2_y = 580, r2_y
    id_b_merge, *el = labeled_rect(map2_x, map2_y, W_MAP, H, "B: Merge Movies\n(Hive)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3})
    elements.extend(el)

    stg2_x, stg2_y = 850, r2_y
    id_movie, *el = labeled_rect(stg2_x, stg2_y, 160, H, "Hive.movie", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    # Arrow: movie_updates → B: Merge (down)
    aid, a = arrow_down(stg1_x, stg1_y, W_STG, H, map2_x, map2_y, W_MAP, H, id_movie_updates, id_b_merge, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: B: Merge → movie
    aid, a = arrow_between(map2_x, map2_y, W_MAP, H, stg2_x, stg2_y, 160, H, id_b_merge, id_movie, color=ARROW_COLOR)
    elements.append(a)

    # ── Row 3: Log Staging (y=370) ──
    r3_y = 370
    src3_x, src3_y = 60, r3_y
    id_log_avro, *el = labeled_rect(src3_x, src3_y, W_SRC, H, "Hive.log_avro", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    map3_x, map3_y = 310, r3_y
    id_populate, *el = labeled_rect(map3_x, map3_y, 180, H, "Populate\n(Staging)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3})
    elements.extend(el)

    stg3_x, stg3_y = 560, r3_y
    id_log_staging, *el = labeled_rect(stg3_x, stg3_y, 215, H, "Hive.log_odistage", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    # Arrow: log_avro → Populate
    aid, a = arrow_between(src3_x, src3_y, W_SRC, H, map3_x, map3_y, 180, H, id_log_avro, id_populate, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: Populate → log_staging
    aid, a = arrow_between(map3_x, map3_y, 180, H, stg3_x, stg3_y, 215, H, id_populate, id_log_staging, color=ARROW_COLOR)
    elements.append(a)

    # ── Row 4: Ratings Calculation (y=500) ──
    r4_y = 500
    map4_x, map4_y = 560, r4_y
    id_c_pigspark, *el = labeled_rect(map4_x, map4_y, 210, H, "C: Calc Ratings\n(Hive → Pig → Spark)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3}, font_size=12)
    elements.extend(el)

    stg4_x, stg4_y = 840, r4_y
    id_movie_rating, *el = labeled_rect(stg4_x, stg4_y, W_STG, H, "Hive.movie_rating", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    # Arrow: C → movie_rating
    aid, a = arrow_between(map4_x, map4_y, 210, H, stg4_x, stg4_y, W_STG, H, id_c_pigspark, id_movie_rating, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: movie → C (diagonal down from row 2)
    aid, a = arrow_down(stg2_x, stg2_y, 160, H, map4_x, map4_y, 210, H, id_movie, id_c_pigspark, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: log_staging → C (diagonal down from row 3)
    aid, a = arrow_down(stg3_x, stg3_y, 215, H, map4_x, map4_y, 210, H, id_log_staging, id_c_pigspark, color=ARROW_COLOR)
    elements.append(a)

    # ── Row 4b: JSON Flatten (y=610) ──
    r4b_y = 610
    src4_x, src4_y = 60, r4b_y
    id_hdfs, *el = labeled_rect(src4_x, src4_y, W_SRC, H, "HDFS.movie_ratings", bg=HDFS_BG, stroke=HDFS_STROKE)
    elements.extend(el)

    map4b_x, map4b_y = 310, r4b_y
    id_d_json, *el = labeled_rect(map4b_x, map4b_y, W_MAP, H, "D: Calc Ratings\n(JSON Flatten)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3}, font_size=12)
    elements.extend(el)

    # Arrow: HDFS → D
    aid, a = arrow_between(src4_x, src4_y, W_SRC, H, map4b_x, map4b_y, W_MAP, H, id_hdfs, id_d_json, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: D → movie_rating (diagonal up)
    aid = gid()
    sx = map4b_x + W_MAP + 5
    sy = map4b_y + H / 2
    ex = stg4_x - 5
    ey = stg4_y + H / 2
    a = make_arrow(aid, sx, sy, [[0, 0], [ex-sx, ey-sy]], start_id=id_d_json, end_id=id_movie_rating, color=ARROW_COLOR)
    elements.append(a)

    # Risk callout on JSON mapping
    risk2_id, *el = labeled_rect(310, r4b_y + 56, 200, 30, "⚠ Cross-platform: HDFS → Hive", bg=RISK_BG, stroke=RISK_STROKE, stroke_w=1, font_size=11, text_color="#c92a2a")
    elements.extend(el)

    # ── Row 4c: Ratings → Oracle (y=500 continued right) ──
    map5_x, map5_y = 1100, r4_y
    id_e_olh, *el = labeled_rect(map5_x, map5_y, 170, H, "E: Load Oracle\n(OLH)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3}, font_size=12)
    elements.extend(el)

    tgt1_x, tgt1_y = 1340, r4_y
    id_tgt_rating, *el = labeled_rect(tgt1_x, tgt1_y, 220, H, "Oracle.MOVIE_RATING", bg=ORACLE_BG, stroke=ORACLE_STROKE, stroke_w=TARGET_STROKE_W, font_size=13)
    elements.extend(el)

    # Arrow: movie_rating → E
    aid, a = arrow_between(stg4_x, stg4_y, W_STG, H, map5_x, map5_y, 170, H, id_movie_rating, id_e_olh, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: E → ODI_MOVIE_RATING
    aid, a = arrow_between(map5_x, map5_y, 170, H, tgt1_x, tgt1_y, 220, H, id_e_olh, id_tgt_rating, color=ARROW_COLOR)
    elements.append(a)

    # Terminal marker
    star1_id = gid()
    elements.append(make_text(star1_id, tgt1_x + 225, tgt1_y + 10, 30, 30, "★", font_size=20, color="#e67700"))

    # ── Row 5: Sales (y=740) ──
    r5_y = 740
    src5_x, src5_y = 60, r5_y
    id_customer, *el = labeled_rect(src5_x, src5_y, W_SRC, H, "Oracle.CUSTOMER", bg=ORACLE_BG, stroke=ORACLE_STROKE)
    elements.extend(el)

    map5b_x, map5b_y = 310, r5_y
    id_f_bdsql, *el = labeled_rect(map5b_x, map5b_y, 210, H, "F: Calc Sales\n(Big Data SQL)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3}, font_size=12)
    elements.extend(el)

    tgt2_x, tgt2_y = 590, r5_y
    id_tgt_sales, *el = labeled_rect(tgt2_x, tgt2_y, 240, H, "Oracle.COUNTRY_SALES", bg=ORACLE_BG, stroke=ORACLE_STROKE, stroke_w=TARGET_STROKE_W, font_size=13)
    elements.extend(el)

    # Arrow: CUSTOMER → F
    aid, a = arrow_between(src5_x, src5_y, W_SRC, H, map5b_x, map5b_y, 210, H, id_customer, id_f_bdsql, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: F → ODI_COUNTRY_SALES
    aid, a = arrow_between(map5b_x, map5b_y, 210, H, tgt2_x, tgt2_y, 240, H, id_f_bdsql, id_tgt_sales, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: log_staging → F (long diagonal down)
    aid, a = arrow_down(stg3_x, stg3_y, 215, H, map5b_x, map5b_y, 210, H, id_log_staging, id_f_bdsql, color=ARROW_COLOR, style="dashed")
    elements.append(a)

    # Risk callout
    risk3_id, *el = labeled_rect(590, r5_y + 56, 240, 30, "⚠ Mixed: Hive + Oracle sources", bg=RISK_BG, stroke=RISK_STROKE, stroke_w=1, font_size=11, text_color="#c92a2a")
    elements.extend(el)

    star2_id = gid()
    elements.append(make_text(star2_id, tgt2_x + 245, tgt2_y + 10, 30, 30, "★", font_size=20, color="#e67700"))

    # ── Row 6: Sessions (y=870) ──
    r6_y = 870
    src6_x, src6_y = 60, r6_y
    id_cust, *el = labeled_rect(src6_x, src6_y, 150, H, "Hive.cust", bg=HIVE_BG, stroke=HIVE_STROKE)
    elements.extend(el)

    map6_x, map6_y = 310, r6_y
    id_g_pig, *el = labeled_rect(map6_x, map6_y, W_MAP, H, "G: Sessionize\n(Pig)", bg=MAP_BG, stroke=MAP_STROKE, roundness={"type": 3}, font_size=12)
    elements.extend(el)

    tgt3_x, tgt3_y = 590, r6_y
    id_tgt_sessions, *el = labeled_rect(tgt3_x, tgt3_y, 200, H, "Hive.session_stats", bg=HIVE_BG, stroke=HIVE_STROKE, stroke_w=TARGET_STROKE_W, font_size=13)
    elements.extend(el)

    # Arrow: cust → G
    aid, a = arrow_between(src6_x, src6_y, 150, H, map6_x, map6_y, W_MAP, H, id_cust, id_g_pig, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: G → session_stats
    aid, a = arrow_between(map6_x, map6_y, W_MAP, H, tgt3_x, tgt3_y, 200, H, id_g_pig, id_tgt_sessions, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: log_staging → G (long diagonal down)
    aid, a = arrow_down(stg3_x, stg3_y, 215, H, map6_x, map6_y, W_MAP, H, id_log_staging, id_g_pig, color=ARROW_COLOR, style="dashed")
    elements.append(a)

    star3_id = gid()
    elements.append(make_text(star3_id, tgt3_x + 205, tgt3_y + 10, 30, 30, "★", font_size=20, color="#1971c2"))

    # ── Legend (bottom right) ──
    legend_y = 970
    legend_x = 900

    # Legend box
    leg_id, *el = labeled_rect(legend_x, legend_y, 280, 130, "", bg="#ffffff", stroke="#dee2e6", stroke_w=1)
    elements.extend(el)

    elements.append(make_text(gid(), legend_x + 10, legend_y + 8, 260, 20, "Legend", font_size=16, color="#1e1e1e"))

    # Oracle swatch
    _, *el = labeled_rect(legend_x + 15, legend_y + 35, 18, 14, "", bg=ORACLE_BG, stroke=ORACLE_STROKE, stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), legend_x + 40, legend_y + 33, 100, 18, "Oracle", font_size=13, color="#495057", align="left"))

    # Hive swatch
    _, *el = labeled_rect(legend_x + 15, legend_y + 57, 18, 14, "", bg=HIVE_BG, stroke=HIVE_STROKE, stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), legend_x + 40, legend_y + 55, 100, 18, "Hive / Hadoop", font_size=13, color="#495057", align="left"))

    # HDFS swatch
    _, *el = labeled_rect(legend_x + 15, legend_y + 79, 18, 14, "", bg=HDFS_BG, stroke=HDFS_STROKE, stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), legend_x + 40, legend_y + 77, 100, 18, "HDFS", font_size=13, color="#495057", align="left"))

    # Terminal marker
    elements.append(make_text(gid(), legend_x + 15, legend_y + 97, 20, 18, "★", font_size=16, color="#e67700"))
    elements.append(make_text(gid(), legend_x + 40, legend_y + 99, 120, 18, "Terminal target", font_size=13, color="#495057", align="left"))

    # Mapping swatch
    _, *el = labeled_rect(legend_x + 150, legend_y + 35, 18, 14, "", bg=MAP_BG, stroke=MAP_STROKE, stroke_w=1, roundness={"type": 3})
    elements.extend(el)
    elements.append(make_text(gid(), legend_x + 175, legend_y + 33, 100, 18, "Transform", font_size=13, color="#495057", align="left"))

    # Risk swatch
    _, *el = labeled_rect(legend_x + 150, legend_y + 57, 18, 14, "", bg=RISK_BG, stroke=RISK_STROKE, stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), legend_x + 175, legend_y + 55, 100, 18, "Migration risk", font_size=13, color="#495057", align="left"))

    # ── Summary callout (bottom left) ──
    summary_id, *el = labeled_rect(60, 970, 330, 130, "", bg="#e7f5ff", stroke="#1971c2", stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), 75, 978, 300, 120,
        "Crawl detected:\n• 8 mappings across 4 technologies\n• 5 cross-platform data hops\n• SYSDATE, NVL, DECODE vendor syntax\n• 0 execution history (dead code risk)\n• 3 terminal targets, 5 external sources",
        font_size=13, color="#1971c2", align="left"))

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "crawl-demo",
        "elements": elements,
        "appState": {"viewBackgroundColor": "#ffffff", "gridSize": 20},
        "files": {},
    }


# ============================================================
# DIAGRAM 2: Crawl Architecture
# ============================================================
def generate_architecture():
    elements = []

    # Colors
    CLI_BG = "#e7f5ff"
    CLI_STROKE = "#1971c2"
    PARSER_BG = "#fff3bf"
    PARSER_STROKE = "#e67700"
    IR_BG = "#d3f9d8"
    IR_STROKE = "#2f9e44"
    ENGINE_BG = "#f3d9fa"
    ENGINE_STROKE = "#9c36b5"
    EXPORT_BG = "#ffe3e3"
    EXPORT_STROKE = "#e03131"
    ARROW_COLOR = "#495057"

    # Title
    elements.append(make_text(gid(), 250, 30, 500, 40, "Crawl — Pre-Migration Intelligence Pipeline", font_size=26, color="#1e1e1e"))
    elements.append(make_text(gid(), 330, 72, 350, 22, "Step 0: Before Datafold, dbt, or SnowConvert", font_size=14, color="#868e96"))

    # ── Pipeline: scan → extract → triage → export ──
    # Main pipeline boxes (top row)
    pipe_y = 140
    bw, bh = 180, 70
    gap = 60

    x1 = 100
    id_scan, *el = labeled_rect(x1, pipe_y, bw, bh, "crawl scan\n--source odi://...", bg=CLI_BG, stroke=CLI_STROKE, font_size=14)
    elements.extend(el)

    x2 = x1 + bw + gap
    id_extract, *el = labeled_rect(x2, pipe_y, bw, bh, "crawl extract\nBusiness Rules", bg=CLI_BG, stroke=CLI_STROKE, font_size=14)
    elements.extend(el)

    x3 = x2 + bw + gap
    id_triage, *el = labeled_rect(x3, pipe_y, bw, bh, "crawl triage\nRisk & Complexity", bg=CLI_BG, stroke=CLI_STROKE, font_size=14)
    elements.extend(el)

    x4 = x3 + bw + gap
    id_export, *el = labeled_rect(x4, pipe_y, bw, bh, "crawl export\nReport Output", bg=CLI_BG, stroke=CLI_STROKE, font_size=14)
    elements.extend(el)

    # Pipeline arrows
    for (sx, sid, tx, tid) in [(x1, id_scan, x2, id_extract), (x2, id_extract, x3, id_triage), (x3, id_triage, x4, id_export)]:
        aid, a = arrow_between(sx, pipe_y, bw, bh, tx, pipe_y, bw, bh, sid, tid, color=ARROW_COLOR, stroke_w=3)
        elements.append(a)

    # ── Parser Layer (below scan) ──
    parser_y = 280
    pw, ph = 170, 55

    # Parser registry box (wide)
    id_registry, *el = labeled_rect(60, parser_y - 15, 350, 155, "", bg="#f8f9fa", stroke="#dee2e6", stroke_w=1)
    elements.extend(el)
    elements.append(make_text(gid(), 70, parser_y - 10, 120, 20, "Parser Registry", font_size=12, color="#868e96", align="left"))

    id_odi_db, *el = labeled_rect(75, parser_y + 15, pw, ph, "OdiDbParser\nodi://host/repo", bg=PARSER_BG, stroke=PARSER_STROKE, font_size=12)
    elements.extend(el)

    id_odi_xml, *el = labeled_rect(75, parser_y + 80, pw, ph, "OdiXmlParser\nodi-export:./file.zip", bg=PARSER_BG, stroke=PARSER_STROKE, font_size=12)
    elements.extend(el)

    id_pg, *el = labeled_rect(255, parser_y + 15, pw-20, ph, "PgParser\npostgres://...", bg=PARSER_BG, stroke=PARSER_STROKE, font_size=12, text_color="#868e96")
    elements.extend(el)
    # "planned" label
    elements.append(make_text(gid(), 280, parser_y + 75, 80, 18, "(planned)", font_size=11, color="#adb5bd"))

    # Arrow: scan → parser layer
    aid, a = arrow_down(x1, pipe_y, bw, bh, 160, parser_y - 15, 200, 10, id_scan, id_registry, color=ARROW_COLOR)
    elements.append(a)

    # ── Common IR (center, below pipeline) ──
    ir_y = 280
    ir_x = 460
    irw, irh = 260, 155

    id_ir, *el = labeled_rect(ir_x, ir_y, irw, irh, "", bg=IR_BG, stroke=IR_STROKE, stroke_w=2)
    elements.extend(el)
    elements.append(make_text(gid(), ir_x + 10, ir_y + 5, irw - 20, 25, "Common IR: ScanResult", font_size=15, color="#2f9e44"))
    elements.append(make_text(gid(), ir_x + 15, ir_y + 35, irw - 30, 110,
        "• DataObject (mappings, procs)\n• Dependency (source → target)\n• BusinessRule (plain English)\n• Contradiction (conflicts)\n• ObjectType, SourcePlatform",
        font_size=12, color="#495057", align="left"))

    # Arrow: parsers → IR
    aid = gid()
    a = make_arrow(aid, 410, parser_y + 70, [[0, 0], [50, 0]], color=IR_STROKE, stroke_w=2)
    elements.append(a)

    # ── Extraction Engine (below extract) ──
    eng_y = 280
    eng_x = 770

    id_eng, *el = labeled_rect(eng_x, eng_y, 220, 155, "", bg=ENGINE_BG, stroke=ENGINE_STROKE, stroke_w=2)
    elements.extend(el)
    elements.append(make_text(gid(), eng_x + 10, eng_y + 5, 200, 25, "Analysis Engine", font_size=15, color="#9c36b5"))
    elements.append(make_text(gid(), eng_x + 15, eng_y + 35, 190, 110,
        "• sqlglot AST parsing\n• LLM extraction (OpenRouter)\n• Cross-platform risk detection\n• Complexity scoring\n• Dead code detection\n• Vendor syntax flagging",
        font_size=12, color="#495057", align="left"))

    # Arrow: IR → Engine
    aid = gid()
    a = make_arrow(aid, ir_x + irw + 5, ir_y + irh/2, [[0, 0], [eng_x - ir_x - irw - 10, 0]], color=ARROW_COLOR, stroke_w=2)
    elements.append(a)

    # Arrow: extract → engine
    aid, a = arrow_down(x2, pipe_y, bw, bh, eng_x, eng_y, 220, 10, id_extract, id_eng, color=ARROW_COLOR)
    elements.append(a)

    # Arrow: triage → engine
    aid, a = arrow_down(x3, pipe_y, bw, bh, eng_x + 100, eng_y, 100, 10, id_triage, id_eng, color=ARROW_COLOR, style="dashed")
    elements.append(a)

    # ── Export Formats (below export) ──
    exp_y = 300
    exp_x = 1040

    id_exp_md, *el = labeled_rect(exp_x, exp_y, 140, 40, "Markdown Report", bg=EXPORT_BG, stroke=EXPORT_STROKE, font_size=12)
    elements.extend(el)

    id_exp_json, *el = labeled_rect(exp_x, exp_y + 50, 140, 40, "JSON Export", bg=EXPORT_BG, stroke=EXPORT_STROKE, font_size=12)
    elements.extend(el)

    id_exp_dbt, *el = labeled_rect(exp_x, exp_y + 100, 140, 40, "dbt-docs YAML", bg=EXPORT_BG, stroke=EXPORT_STROKE, font_size=12, text_color="#868e96")
    elements.extend(el)

    # Arrow: export → formats
    aid, a = arrow_down(x4, pipe_y, bw, bh, exp_x, exp_y, 140, 10, id_export, id_exp_md, color=ARROW_COLOR)
    elements.append(a)

    # ── Safety callout ──
    safety_y = 480
    id_safety, *el = labeled_rect(60, safety_y, 350, 80, "", bg="#fff3bf", stroke="#e67700", stroke_w=2)
    elements.extend(el)
    elements.append(make_text(gid(), 75, safety_y + 5, 320, 20, "🔒 Safety Model", font_size=15, color="#e67700"))
    elements.append(make_text(gid(), 75, safety_y + 28, 320, 50,
        "Read-only • Catalog-only • Query allowlisting\nNo dynamic SQL • LLM credential redaction",
        font_size=12, color="#495057", align="left"))

    # ── "What ODI Studio can't show you" callout ──
    wow_y = 480
    wow_x = 460
    id_wow, *el = labeled_rect(wow_x, wow_y, 310, 80, "", bg="#e7f5ff", stroke="#1971c2", stroke_w=2)
    elements.extend(el)
    elements.append(make_text(gid(), wow_x + 10, wow_y + 5, 290, 20, "💡 What ODI Studio can't show", font_size=15, color="#1971c2"))
    elements.append(make_text(gid(), wow_x + 15, wow_y + 28, 280, 50,
        "Cross-platform migration risks • Dead code\nVendor syntax (SYSDATE→?) • Complexity rank\nBusiness rules in plain English",
        font_size=12, color="#495057", align="left"))

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "crawl-demo",
        "elements": elements,
        "appState": {"viewBackgroundColor": "#ffffff", "gridSize": 20},
        "files": {},
    }


if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))

    # Diagram 1: ETL Lineage
    d1 = generate_etl_lineage()
    path1 = os.path.join(base, "etl-pipeline-lineage.excalidraw")
    with open(path1, "w") as f:
        json.dump(d1, f, indent=2)
    print(f"✓ Generated {path1} ({len(d1['elements'])} elements)")

    # Diagram 2: Architecture
    d2 = generate_architecture()
    path2 = os.path.join(base, "crawl-architecture.excalidraw")
    with open(path2, "w") as f:
        json.dump(d2, f, indent=2)
    print(f"✓ Generated {path2} ({len(d2['elements'])} elements)")
