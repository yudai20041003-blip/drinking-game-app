import streamlit as st
import json
import random
import time
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
import google.generativeai as genai

# ==============================
# ページ設定
# ==============================
st.set_page_config(page_title="🍺 AIルーレット飲み会ゲーム", page_icon="🎡", layout="wide")

# ==============================
# Gemini API設定
# ==============================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==============================
# セッション初期化
# ==============================
if "game_state" not in st.session_state:
    st.session_state.game_state = "menu"  # menu, playing, finished
if "players" not in st.session_state:
    st.session_state.players = []
if "round_count" not in st.session_state:
    st.session_state.round_count = 0
if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = 15
if "spinning" not in st.session_state:
    st.session_state.spinning = False
if "selected_player_index" not in st.session_state:
    st.session_state.selected_player_index = None
if "drunk_levels" not in st.session_state:
    st.session_state.drunk_levels = {}
if "saved_players" not in st.session_state:
    st.session_state.saved_players = []

# ==============================
# 関数定義
# ==============================

def display_roulette(players, selected_index=None, spinning=False):
    """ルーレットのHTMLを生成"""
    num_players = len(players) if players else 1
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B195', '#C06C84',
              '#6C5B7B', '#355C7D']

    if spinning:
        rotation = "rotate(1080deg)"  # 3回転
        transition = "transform 3s cubic-bezier(0.17, 0.67, 0.12, 0.99)"
    elif selected_index is not None:
        angle = -360 * (selected_index / num_players)
        rotation = f"rotate({angle}deg)"
        transition = "transform 3s cubic-bezier(0.17, 0.67, 0.12, 0.99)"
    else:
        rotation = "rotate(0deg)"
        transition = "transform 0.3s ease"

    roulette_html = f"""
    <style>
        .roulette-container {{
            width: 500px;
            height: 500px;
            position: relative;
            margin: 0 auto;
        }}
        .roulette-wheel {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            position: relative;
            transform: {rotation};
            transition: {transition};
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}
        .roulette-section {{
            position: absolute;
            width: 50%;
            height: 50%;
            transform-origin: 100% 100%;
            overflow: hidden;
        }}
        .roulette-section-inner {{
            width: 200%;
            height: 200%;
            transform-origin: 0 100%;
            border: 2px solid white;
        }}
        .roulette-text {{
            position: absolute;
            width: 40%;
            top: 35%;
            left: 55%;
            font-size: 16px;
            font-weight: bold;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            transform-origin: 0 0;
        }}
        .arrow {{
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 20px solid transparent;
            border-right: 20px solid transparent;
            border-top: 40px solid #FF0000;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
            z-index: 100;
        }}
        .center-circle {{
            position: absolute;
            width: 80px;
            height: 80px;
            background: white;
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            border: 5px solid #FFD700;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }}
    </style>
    <div class="roulette-container">
        <div class="arrow"></div>
        <div class="roulette-wheel" id="rouletteWheel">
    """

    angle = 360 / num_players
    for i, player in enumerate(players):
        rotation_angle = angle * i
        skew_angle = 90 - angle
        color = colors[i % len(colors)]
        text_rotation = rotation_angle + angle / 2

        roulette_html += f"""
            <div class="roulette-section" style="transform: rotate({rotation_angle}deg) skewY({-skew_angle}deg);">
                <div class="roulette-section-inner" style="background: {color}; transform: skewY({skew_angle}deg);"></div>
                <div class="roulette-text" style="transform: rotate({text_rotation}deg) translateY(-150px);">
                    {player['name']}
                </div>
            </div>
        """

    roulette_html += """
        </div>
        <div class="center-circle">🍺</div>
    </div>
    """
    return roulette_html


def update_drunk_level(player_name, multiplier):
    """酔い度を更新"""
    if player_name not in st.session_state.drunk_levels:
        st.session_state.drunk_levels[player_name] = 0.0
    st.session_state.drunk_levels[player_name] += multiplier
    st.session_state.drunk_levels[player_name] = min(st.session_state.drunk_levels[player_name], 1.0)


def display_drunk_chart():
    """酔い度を棒グラフで表示"""
    players = list(st.session_state.drunk_levels.keys())
    values = list(st.session_state.drunk_levels.values())

    if not players:
        return

    fig = go.Figure(go.Bar(
        x=values,
        y=players,
        orientation='h',
        marker_color='rgba(255,99,132,0.6)'
    ))
    fig.update_layout(title="現在の酔い度", xaxis=dict(range=[0, 1]))
    st.plotly_chart(fig, use_container_width=True)

# ==============================
# メイン画面
# ==============================

st.title("🎡 AIルーレット飲み会ゲーム")
st.write("プレイヤーを登録してルーレットで飲み係を決めよう！")

# プレイヤー登録
with st.form("player_form"):
    name = st.text_input("プレイヤー名を入力")
    submitted = st.form_submit_button("追加")
    if submitted and name:
        st.session_state.players.append({"name": name})
        st.session_state.drunk_levels[name] = 0.0

if st.session_state.players:
    st.write("### 登録プレイヤー")
    st.write(", ".join([p["name"] for p in st.session_state.players]))

# ルーレットエリア
if st.session_state.players:
    st.subheader(f"ラウンド {st.session_state.round_count + 1}/{st.session_state.max_rounds}")

    roulette_placeholder = st.empty()

    if st.session_state.spinning:
        components.html(display_roulette(st.session_state.players, spinning=True), height=600)
        time.sleep(3)
        st.session_state.spinning = False
        st.rerun()

    elif st.session_state.selected_player_index is not None:
        components.html(display_roulette(st.session_state.players, selected_index=st.session_state.selected_player_index), height=600)
    else:
        components.html(display_roulette(st.session_state.players), height=600)

    # ルーレットを回すボタン
    if st.button("🎯 ルーレットを回す", use_container_width=True):
        st.session_state.spinning = True
        st.session_state.selected_player_index = random.randint(0, len(st.session_state.players) - 1)
        selected = st.session_state.players[st.session_state.selected_player_index]["name"]
        multiplier = random.choice([0.1, 0.2, 0.3, 0.4])
        update_drunk_level(selected, multiplier)
        st.session_state.round_count += 1
        st.rerun()

    st.divider()
    display_drunk_chart()
