# 🍺 AIルーレット飲みゲーム 完全統合版 (2025/10版)

import streamlit as st
import json
import random
import google.generativeai as genai
import time
import plotly.graph_objects as go
import numpy as np
import streamlit.components.v1 as components

# ページ設定
st.set_page_config(page_title="🍺 AIルーレット飲みゲーム", page_icon="🍺", layout="wide")

# Gemini API設定
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# セッション初期化
if "game_state" not in st.session_state:
    st.session_state.game_state = "menu"
if "players" not in st.session_state:
    st.session_state.players = []
if "round_count" not in st.session_state:
    st.session_state.round_count = 0
if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = 15
if "had_sudden_event" not in st.session_state:
    st.session_state.had_sudden_event = False
if "saved_players" not in st.session_state:
    st.session_state.saved_players = []

# ===== 基本関数 =====

def calculate_drink_amount(player):
    """飲む量を計算"""
    strength = player["strength"]
    preference = player["preference"]
    if strength <= 2:
        multiplier = 0.5 if preference <= 2 else 1.0
    elif strength == 3:
        multiplier = 0.75 if preference <= 3 else 1.5
    else:
        multiplier = 1.5 if preference <= 3 else 2.0
    return multiplier


def get_drink_display(multiplier, cup_type):
    """飲む量表示"""
    if cup_type == "おちょこ":
        return f"おちょこ {multiplier:.1f}杯"
    elif cup_type == "ジョッキ":
        return f"ジョッキ {multiplier*0.5:.1f}杯分"
    else:
        return f"おちょこ {multiplier:.1f}杯（ジョッキ {multiplier*0.5:.1f}杯分）"


def update_drunk_degree(player, multiplier):
    """酔い度更新"""
    player["drunk_degree"] += multiplier * 10
    player["drunk_degree"] = min(player["drunk_degree"], 100)
    player["total_drunk"] += multiplier


# ===== ルーレットHTML描画 =====

def display_roulette(players, selected_index=None, spinning=False):
    num = len(players)
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8",
        "#F7DC6F", "#BB8FCE", "#85C1E2", "#F8B195", "#C06C84",
        "#6C5B7B", "#355C7D"
    ]
    angle = 360 / num

    if spinning:
        rotation_css = "rotate(1440deg)"
        transition_css = "transform 3s cubic-bezier(0.17,0.67,0.12,0.99)"
    elif selected_index is not None:
        rotation_value = -(selected_index * angle) - angle / 2
        rotation_css = f"rotate({rotation_value}deg)"
        transition_css = "transform 2s cubic-bezier(0.17,0.67,0.12,0.99)"
    else:
        rotation_css = "rotate(0deg)"
        transition_css = "transform 0.3s ease"

    html = f"""
    <html><head><meta charset="utf-8"/>
    <style>
    :root {{ --size: 480px; }}
    body {{ margin:0; background:transparent; }}
    .wrapper {{
        display:flex; justify-content:center; align-items:center;
        height:600px;
    }}
    .board {{ position:relative; }}
    .arrow {{
        position:absolute; top:0; left:50%; transform:translateX(-50%);
        width:0; height:0;
        border-left:20px solid transparent;
        border-right:20px solid transparent;
        border-bottom:30px solid #e74c3c;
        z-index:20;
    }}
    .roulette {{
        width:var(--size); height:var(--size); border-radius:50%;
        position:relative; top:30px;
        overflow:hidden;
        transform:{rotation_css};
        transition:{transition_css};
        box-shadow:0 10px 30px rgba(0,0,0,0.3);
    }}
    .slice {{
        position:absolute;
        width:50%; height:50%;
        top:50%; left:50%;
        transform-origin:0% 0%;
    }}
    .slice-inner {{
        width:200%; height:200%;
        transform-origin:0% 100%;
        border:1px solid rgba(255,255,255,0.2);
    }}
    .label {{
        position:absolute;
        width:40%;
        left:50%; top:50%;
        transform-origin:0 0;
        font-size:14px; font-weight:bold;
        color:#fff; text-shadow:1px 1px 3px rgba(0,0,0,0.7);
        pointer-events:none;
    }}
    .center {{
        position:absolute; width:70px; height:70px;
        background:#fff; border-radius:50%;
        top:calc(50% + 30px); left:calc(50% - 35px);
        display:flex; justify-content:center; align-items:center;
        font-size:24px; border:4px solid gold;
        box-shadow:0 6px 15px rgba(0,0,0,0.2);
        z-index:10;
    }}
    </style></head>
    <body><div class="wrapper"><div class="board">
    <div class="arrow"></div>
    <div class="roulette">
    """

    for i, player in enumerate(players):
        color = colors[i % len(colors)]
        slice_rotate = i * angle
        label_rotate = i * angle + angle / 2
        html += f"""
        <div class="slice" style="transform:rotate({slice_rotate}deg) skewY({-(90-angle)}deg);">
            <div class="slice-inner" style="background:{color}; transform:skewY({90-angle}deg);"></div>
        </div>
        <div class="label" style="transform:rotate({label_rotate}deg) translateY(-220px) translateX(-50%);">
            {player['name']}
        </div>
        """

    html += """</div><div class="center">🍺</div></div></div></body></html>"""
    return html


# ===== ステータス表示 =====

def display_status():
    st.markdown("---")
    st.subheader("📊 現在の酔い度")

    sorted_players = sorted(st.session_state.players, key=lambda x: x["drunk_degree"], reverse=True)

    for i, p in enumerate(sorted_players, 1):
        col1, col2, col3 = st.columns([2, 3, 2])
        col1.write(f"**{i}. {p['name']}**")
        col2.progress(p["drunk_degree"] / 100)
        col3.write(f"{p['drunk_degree']:.1f}%")


# ===== メイン画面 =====

st.title("🍺 AIルーレット飲みゲーム")

if st.session_state.game_state == "menu":
    st.markdown("""
    ---
    ### ゲームの説明
    - 15ラウンドのルーレット飲み会ゲーム！  
    - お酒の強さ・好き嫌いに応じて飲む量を調整  
    - ランダム突発イベントあり！
    ---
    """)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎮 新しいゲームを開始", use_container_width=True):
            st.session_state.game_state = "input_players"
            st.session_state.players = []
            st.rerun()
    with col2:
        if st.session_state.saved_players and st.button("📂 前回のメンバーで開始", use_container_width=True):
            st.session_state.players = [p.copy() for p in st.session_state.saved_players]
            for p in st.session_state.players:
                p["drunk_degree"] = 0
                p["total_drunk"] = 0
            st.session_state.round_count = 0
            st.session_state.game_state = "playing"
            st.rerun()


# ===== プレイヤー登録 =====

elif st.session_state.game_state == "input_players":
    st.markdown("---")
    st.subheader("参加者情報の入力")

    num_players = st.number_input("人数（5～12）", min_value=5, max_value=12, value=5)
    st.markdown("---")

    players_temp = []
    for i in range(num_players):
        with st.expander(f"プレイヤー {i+1}", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            name = c1.text_input("名前", value=f"プレイヤー{i+1}", key=f"name_{i}")
            strength = c2.slider("お酒の強さ", 1, 5, 3, key=f"str_{i}")
            preference = c3.slider("お酒の好き嫌い", 1, 5, 3, key=f"pref_{i}")
            cup_type = c4.selectbox("基準量", ["おちょこ", "ジョッキ", "どちらも"], key=f"cup_{i}")

            players_temp.append({
                "name": name,
                "strength": strength,
                "preference": preference,
                "cup_type": cup_type,
                "total_drunk": 0,
                "drunk_degree": 0,
            })

    st.markdown("---")
    if st.button("✅ ゲーム開始", use_container_width=True, type="primary"):
        st.session_state.players = players_temp
        st.session_state.saved_players = [p.copy() for p in players_temp]
        st.session_state.round_count = 0
        st.session_state.game_state = "playing"
        st.rerun()


# ===== プレイ画面 =====

elif st.session_state.game_state == "playing":
    st.markdown(f"### 🎰 ラウンド {st.session_state.round_count+1}/{st.session_state.max_rounds}")

    if st.session_state.round_count < st.session_state.max_rounds:
        if "spinning" not in st.session_state:
            st.session_state.spinning = False
        if "selected_player_index" not in st.session_state:
            st.session_state.selected_player_index = None

        # ルーレット描画
        if st.session_state.spinning:
            components.html(display_roulette(st.session_state.players, spinning=True), height=650)
            time.sleep(3)
            st.session_state.spinning = False
            st.rerun()
        elif st.session_state.selected_player_index is not None:
            components.html(display_roulette(st.session_state.players, selected_index=st.session_state.selected_player_index), height=650)
        else:
            components.html(display_roulette(st.session_state.players), height=650)

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🎡 ルーレットを回す", use_container_width=True, type="primary"):
                st.session_state.spinning = True
                selected_player = random.choice(st.session_state.players)
                st.session_state.selected_player_index = st.session_state.players.index(selected_player)

                multiplier = calculate_drink_amount(selected_player)
                drink_display = get_drink_display(multiplier, selected_player["cup_type"])

                st.session_state.last_selected = selected_player["name"]
                st.session_state.last_drink = drink_display
                update_drunk_degree(selected_player, multiplier)

                # 突発イベント
                if (random.random() < 0.3 or
                    (st.session_state.round_count == st.session_state.max_rounds - 1 and not st.session_state.had_sudden_event)):
                    random_player = random.choice(st.session_state.players)
                    multiplier_sudden = calculate_drink_amount(random_player)
                    drink_display_sudden = get_drink_display(multiplier_sudden, random_player["cup_type"])
                    st.session_state.sudden_event_player = random_player["name"]
                    st.session_state.sudden_event_drink = drink_display_sudden
                    update_drunk_degree(random_player, multiplier_sudden)
                    st.session_state.had_sudden_event = True
                else:
                    st.session_state.sudden_event_player = None

                st.session_state.round_count += 1
                st.rerun()

        with col2:
            if st.session_state.selected_player_index is not None:
                if st.button("➡️ 次のラウンドへ", use_container_width=True):
                    st.session_state.selected_player_index = None
                    st.session_state.last_selected = None
                    st.rerun()

        if hasattr(st.session_state, "last_selected") and st.session_state.last_selected:
            st.markdown("---")
            st.success(f"🎯 選ばれた人: **{st.session_state.last_selected}**")
            st.info(f"飲む量: **{st.session_state.last_drink}**")
            if st.session_state.sudden_event_player:
                st.error(f"💥 突発イベント: {st.session_state.sudden_event_player}さんが飲みます！")
                st.warning(f"量: **{st.session_state.sudden_event_drink}**")

        display_status()

    else:
        st.session_state.game_state = "finished"
        st.rerun()


# ===== 結果画面 =====

elif st.session_state.game_state == "finished":
    st.header("🏁 ゲーム終了！最終結果")
    st.markdown("---")

    sorted_players = sorted(st.session_state.players, key=lambda x: x["drunk_degree"], reverse=True)
    for i, p in enumerate(sorted_players, 1):
        col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
        col1.markdown(f"### {['🥇','🥈','🥉'][i-1] if i<=3 else f'{i}位'}")
        col2.write(p["name"])
        col3.progress(p["drunk_degree"] / 100)
        col4.write(f"飲んだ量 {p['total_drunk']:.1f} 杯分")
        st.markdown("---")

    winner = sorted_players[0]
    st.success(f"👑 {winner['name']}さんが優勝！")
    victim = st.selectbox("誰に飲ませますか？", [p["name"] for p in st.session_state.players if p["name"] != winner["name"]])
    if st.button("👑 特権発動"):
        st.warning(f"{winner['name']} → {victim} さんに1杯！🍻")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("🔄 もう一度遊ぶ", use_container_width=True):
        for p in st.session_state.players:
            p["drunk_degree"] = 0
            p["total_drunk"] = 0
        st.session_state.round_count = 0
        st.session_state.game_state = "playing"
        st.rerun()
    if c2.button("🏠 メニューに戻る", use_container_width=True):
        st.session_state.game_state = "menu"
        st.rerun()
