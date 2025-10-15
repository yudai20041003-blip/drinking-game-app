import streamlit as st
import json
import random
import google.generativeai as genai
import time
import plotly.graph_objects as go
import numpy as np

# ページ設定
st.set_page_config(page_title="🍺 AIルーレット飲みゲーム", page_icon="🍺", layout="wide")

# Gemini APIの設定
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# セッション状態の初期化
if 'game_state' not in st.session_state:
    st.session_state.game_state = 'menu'  # menu, input_players, playing, finished
if 'players' not in st.session_state:
    st.session_state.players = []
if 'round_count' not in st.session_state:
    st.session_state.round_count = 0
if 'max_rounds' not in st.session_state:
    st.session_state.max_rounds = 15
if 'had_sudden_event' not in st.session_state:
    st.session_state.had_sudden_event = False
if 'saved_players' not in st.session_state:
    st.session_state.saved_players = []

def calculate_drink_amount(player):
    """飲む量を計算（5段階）"""
    strength = player['strength']
    preference = player['preference']
    
    if strength <= 2:
        if preference <= 2:
            multiplier = 0.5
        elif preference == 3:
            multiplier = 0.75
        else:
            multiplier = 1.0
    elif strength == 3:
        if preference <= 2:
            multiplier = 0.75
        elif preference == 3:
            multiplier = 1.0
        else:
            multiplier = 1.5
    else:
        if preference <= 3:
            multiplier = 1.5
        else:
            multiplier = 2.0
    
    return multiplier

def get_drink_display(multiplier, cup_type):
    """飲む量の表示"""
    if cup_type == 'おちょこ':
        amount = multiplier
        return f"おちょこ {amount}杯"
    elif cup_type == 'ジョッキ':
        amount = multiplier * 0.5
        return f"ジョッキ {amount}杯分"
    else:
        amount_ochoko = multiplier
        return f"おちょこ {amount_ochoko}杯 (またはジョッキ {amount_ochoko*0.5}杯分)"

def update_drunk_degree(player, multiplier):
    """酔い度を更新"""
    player['drunk_degree'] += multiplier * 10
    player['drunk_degree'] = min(player['drunk_degree'], 100)
    player['total_drunk'] += multiplier

def display_roulette(players, selected_index=None, spinning=False):
    """ルーレットの表示"""
    num_players = len(players)
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', 
              '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B195', '#C06C84',
              '#6C5B7B', '#355C7D']
    
    # 回転角度の計算
    if spinning:
        rotation = "rotate(1080deg)"  # 3回転
        transition = "transform 3s cubic-bezier(0.17, 0.67, 0.12, 0.99)"
    elif selected_index is not None:
        # 選ばれた人が上（12時の位置）に来るように回転
        angle = -360 * (selected_index / num_players)
        rotation = f"rotate({angle}deg)"
        transition = "transform 3s cubic-bezier(0.17, 0.67, 0.12, 0.99)"
    else:
        rotation = "rotate(0deg)"
        transition = "transform 0.3s ease"
    
    # HTML/CSS でルーレットを描画
    roulette_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 600px;
                background: transparent;
            }}
            .roulette-container {{
                width: 500px;
                height: 500px;
                position: relative;
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
    </head>
    <body>
        <div class="roulette-container">
            <div class="arrow"></div>
            <div class="roulette-wheel" id="rouletteWheel">
    """
    
    for i, player in enumerate(players):
        angle = 360 / num_players
        rotation_angle = angle * i
        skew_angle = 90 - angle
        color = colors[i % len(colors)]
        
        # テキストの回転角度を計算
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
    </body>
    </html>
    """
    
    return roulette_html

def display_status():
    """現在のステータス表示"""
    st.markdown("---")
    st.subheader("📊 現在の酔い度")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            st.write(f"**{i}. {p['name']}**")
        with col2:
            st.progress(p['drunk_degree'] / 100)
        with col3:
            st.write(f"{p['drunk_degree']:.1f}%")
    """現在のステータス表示"""
    st.markdown("---")
    st.subheader("📊 現在の酔い度")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            st.write(f"**{i}. {p['name']}**")
        with col2:
            st.progress(p['drunk_degree'] / 100)
        with col3:
            st.write(f"{p['drunk_degree']:.1f}%")

# タイトル
st.title("🍺 AIルーレット飲みゲーム")

# メニュー画面
if st.session_state.game_state == 'menu':
    st.markdown("---")
    st.markdown("""
    ### ゲームの目的
    このゲームは、**みんなの酔い度を均等にする**ための飲みゲームです！
    
    - お酒の強さと好き嫌いに応じて飲む量を調整
    - 15ラウンドのルーレット
    - 突発イベントもあり！
    """)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🎮 新しいゲームを開始", use_container_width=True):
            st.session_state.game_state = 'input_players'
            st.session_state.players = []
            st.rerun()
    
    with col2:
        if st.session_state.saved_players and st.button("📂 前回のプレイヤーで開始", use_container_width=True):
            st.session_state.players = st.session_state.saved_players.copy()
            for p in st.session_state.players:
                p['drunk_degree'] = 0
                p['total_drunk'] = 0
            st.session_state.game_state = 'playing'
            st.session_state.round_count = 0
            st.session_state.had_sudden_event = False
            st.rerun()

# プレイヤー入力画面
elif st.session_state.game_state == 'input_players':
    st.markdown("---")
    st.subheader("参加者情報の入力")
    
    num_players = st.number_input("参加人数（5～12人）", min_value=5, max_value=12, value=5)
    
    st.markdown("---")
    
    players_temp = []
    
    for i in range(num_players):
        with st.expander(f"プレイヤー {i+1}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                name = st.text_input(f"名前", key=f"name_{i}", value=f"プレイヤー{i+1}")
            
            with col2:
                strength = st.slider(f"お酒の強さ", 1, 5, 3, key=f"strength_{i}")
            
            with col3:
                preference = st.slider(f"お酒の好き嫌い", 1, 5, 3, key=f"preference_{i}")
            
            with col4:
                cup_type = st.selectbox(f"基準量", ['おちょこ', 'ジョッキ', 'どちらも'], key=f"cup_{i}")
            
            players_temp.append({
                'name': name,
                'strength': strength,
                'preference': preference,
                'cup_type': cup_type,
                'total_drunk': 0,
                'drunk_degree': 0
            })
    
    st.markdown("---")
    
    if st.button("✅ ゲーム開始", use_container_width=True, type="primary"):
        st.session_state.players = players_temp
        st.session_state.saved_players = [p.copy() for p in players_temp]
        st.session_state.game_state = 'playing'
        st.session_state.round_count = 0
        st.session_state.had_sudden_event = False
        st.rerun()

# ゲーム中
elif st.session_state.game_state == 'playing':
    
    # ラウンド表示
    st.markdown(f"### 🎰 ラウンド {st.session_state.round_count + 1}/{st.session_state.max_rounds}")
    
    if st.session_state.round_count < st.session_state.max_rounds:
        
        # ルーレット表示エリア
        roulette_placeholder = st.empty()
        
        # 初期状態または結果表示
        if 'spinning' not in st.session_state:
            st.session_state.spinning = False
        
        if 'selected_player_index' not in st.session_state:
            st.session_state.selected_player_index = None
        
        # ルーレット表示
        if st.session_state.spinning:
            # 回転中
            roulette_placeholder.markdown(display_roulette(st.session_state.players, spinning=True), unsafe_allow_html=True)
            time.sleep(3)
            st.session_state.spinning = False
            st.rerun()
        elif st.session_state.selected_player_index is not None:
            # 結果表示
            roulette_placeholder.markdown(display_roulette(st.session_state.players, selected_index=st.session_state.selected_player_index), unsafe_allow_html=True)
        else:
            # 初期状態
            roulette_placeholder.markdown(display_roulette(st.session_state.players), unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🎡 ルーレットを回す", use_container_width=True, type="primary", disabled=st.session_state.spinning):
                # ルーレット開始
                st.session_state.spinning = True
                
                # ランダムで選択
                selected_player = random.choice(st.session_state.players)
                st.session_state.selected_player_index = st.session_state.players.index(selected_player)
                
                multiplier = calculate_drink_amount(selected_player)
                drink_display = get_drink_display(multiplier, selected_player['cup_type'])
                
                st.session_state.last_selected = selected_player['name']
                st.session_state.last_drink = drink_display
                
                update_drunk_degree(selected_player, multiplier)
                
                # 突発イベント判定
                if (random.random() < 0.3 or 
                    (st.session_state.round_count == st.session_state.max_rounds - 1 and 
                     not st.session_state.had_sudden_event)):
                    
                    random_player = random.choice(st.session_state.players)
                    multiplier_sudden = calculate_drink_amount(random_player)
                    drink_display_sudden = get_drink_display(multiplier_sudden, random_player['cup_type'])
                    
                    st.session_state.sudden_event_player = random_player['name']
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
        
        # 結果表示
        if hasattr(st.session_state, 'last_selected') and st.session_state.last_selected:
            st.markdown("---")
            st.success(f"🎯 選ばれた人: **{st.session_state.last_selected}**")
            st.info(f"飲む量: **{st.session_state.last_drink}**")
            
            if st.session_state.sudden_event_player:
                st.markdown("---")
                st.error(f"💥 **{st.session_state.sudden_event_player}さん、アウトー！**")
                st.warning(f"飲む量: **{st.session_state.sudden_event_drink}**")
        
        # 現在のステータス
        display_status()
    
    else:
        # ゲーム終了
        st.session_state.game_state = 'finished'
        st.rerun()

# ゲーム終了画面
elif st.session_state.game_state == 'finished':
    st.markdown("---")
    st.markdown("# 🏆 ゲーム終了！最終ランキング")
    st.markdown("---")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
            
            with col1:
                if i == 1:
                    st.markdown(f"### 🥇 {i}位")
                elif i == 2:
                    st.markdown(f"### 🥈 {i}位")
                elif i == 3:
                    st.markdown(f"### 🥉 {i}位")
                else:
                    st.markdown(f"### {i}位")
            
            with col2:
                st.markdown(f"**{p['name']}**")
            
            with col3:
                st.progress(p['drunk_degree'] / 100)
                st.write(f"酔い度: {p['drunk_degree']:.1f}%")
            
            with col4:
                st.write(f"飲んだ量: {p['total_drunk']:.1f}杯分")
        
        st.markdown("---")
    
    # 勝者特権
    winner = sorted_players[0]
    st.success(f"🥇 **{winner['name']}さんが勝者です！**")
    st.info(f"**{winner['name']}さんは他の1人に1杯飲ませることができます！**")
    
    victim_name = st.selectbox("誰に飲ませますか？", [p['name'] for p in st.session_state.players if p['name'] != winner['name']])
    
    if st.button("👑 特権発動！", use_container_width=True):
        for p in st.session_state.players:
            if p['name'] == victim_name:
                multiplier = calculate_drink_amount(p)
                drink_display = get_drink_display(multiplier, p['cup_type'])
                st.success(f"👑 {winner['name']}の特権発動！")
                st.warning(f"**{p['name']}さんが飲みます: {drink_display}**")
                break
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 もう1回遊ぶ", use_container_width=True):
            for p in st.session_state.players:
                p['drunk_degree'] = 0
                p['total_drunk'] = 0
            st.session_state.game_state = 'playing'
            st.session_state.round_count = 0
            st.session_state.had_sudden_event = False
            st.rerun()
    
    with col2:
        if st.button("🏠 メニューに戻る", use_container_width=True):
            st.session_state.game_state = 'menu'
            st.rerun()
