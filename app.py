import streamlit as st
import json
import random
import google.generativeai as genai

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
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🎡 ルーレットを回す", use_container_width=True, type="primary"):
                # ルーレット
                selected_player = random.choice(st.session_state.players)
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
        
        # 結果表示
        if hasattr(st.session_state, 'last_selected'):
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
