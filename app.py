>import streamlit as st
import streamlit.components.v1 as components
import random
import time

# ページ設定
st.set_page_config(page_title="🍶 AIルーレット飲みゲーム", page_icon="🍶", layout="wide")

# セッション状態の初期化
def init_session_state():
    defaults = {
        'game_state': 'menu',
        'players': [],
        'saved_players': [],
        'round_count': 0,
        'max_rounds': 15,
        'had_sudden_event': False,
        'spinning': False,
        'selected_player_index': None,
        'last_selected': None,
        'last_drink': None,
        'sudden_event_player': None,
        'sudden_event_drink': None
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

def calculate_drink_amount(player):
    """飲み量を計算（5段階）"""
    strength = player['strength']
    preference = player['preference']
    
    if strength <= 2:
        if preference <= 2: multiplier = 0.5
        elif preference == 3: multiplier = 0.75
        else: multiplier = 1.0
    elif strength == 3:
        if preference <= 2: multiplier = 0.75
        elif preference == 3: multiplier = 1.0
        else: multiplier = 1.5
    else:
        if preference <= 3: multiplier = 1.5
        else: multiplier = 2.0
    
    return multiplier

def get_drink_display(multiplier, cup_type):
    """飲み物の表示"""
    if cup_type == 'おちょこ':
        return f"おちょこ {multiplier:.1f}杯"
    elif cup_type == 'ジョッキ':
        return f"ジョッキ {multiplier*0.5:.1f}杯分"
    else:
        return f"おちょこ {multiplier:.1f}杯（またはジョッキ {multiplier*0.5:.1f}杯分）"

def update_drunk_degree(player, multiplier):
    """酔い度を更新"""
    player['drunk_degree'] += multiplier * 10
    player['drunk_degree'] = min(player['drunk_degree'], 100)
    player['total_drunk'] += multiplier

def create_roulette_html(players, selected_index=None, spinning=False):
    """名前がルーレットと完璧に連動する美しいルーレット"""
    num_players = len(players)
    colors = ['#FF6666', '#4ECDCA', '#4587D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#88BFCE', '#B5C1E2', '#B8B195', '#C8C6B4',
              '#6C5E7B', '#355C70']
    
    # 各セクションの角度
    angle_per_section = 360 / num_players
    
    # conic-gradientでセクションを作成
    gradient_stops = []
    for i in range(num_players):
        start_angle = i * angle_per_section
        end_angle = (i + 1) * angle_per_section
        color = colors[i % len(colors)]
        gradient_stops.append(f"{color} {start_angle}deg {end_angle}deg")
    
    gradient = ", ".join(gradient_stops)
    
    # 回転角度の計算
    if selected_index is not None:
        # 選択されたプレイヤーが上（12時方向）に来るように
        target_angle = -(selected_index * angle_per_section + angle_per_section / 2)
        if spinning:
            # スピン時は3-5回転を追加
            total_rotation = target_angle + random.randint(1080, 1800)  # 3-5回転
        else:
            total_rotation = target_angle
    else:
        total_rotation = 0
    
    # プレイヤー名のラベル生成（CSS変数を使用した洗練されたアプローチ）
    labels_html = ""
    for i, player in enumerate(players):
        # セクション中央の角度を計算
        label_angle = i * angle_per_section + angle_per_section / 2
        # 名前をHTMLエスケープ
        name = str(player['name']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # CSS変数を使用してエレガントに配置
        labels_html += f"""
        <div class="player-label" style="--angle: {label_angle}deg;">
            <span>{name}</span>
        </div>
        """
    
    # 完全なHTML文書
    html_content = f"""
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
            min-height: 100vh;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .roulette-container {{
            position: relative;
            width: 480px;
            height: 480px;
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
            border-top: 40px solid #e74c3c;
            filter: drop-shadow(0 6px 12px rgba(0,0,0,0.4));
            z-index: 30;
        }}
        /* 回転するルーレット本体 */
        #wheel {{
            position: relative;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: conic-gradient({gradient});
            border: 4px solid #333;
            box-shadow: 0 20px 60px rgba(0,0,0,0.35);
            overflow: visible;
            transform: rotate(0deg);
            transition: transform 0.1s ease;
            z-index: 5;
        }}
        /* プレイヤー名ラベル（ルーレットの子要素として回転） */
        .player-label {{
            position: absolute;
            top: 50%;
            left: 50%;
            /* CSS変数を使用した洗練された配置 */
            transform: rotate(var(--angle)) translateY(-190px) rotate(calc(-1 * var(--angle)));
            transform-origin: center center;
            pointer-events: none;
        }}
        .player-label span {{
            display: inline-block;
            padding: 4px 12px;
            color: white;
            font-weight: bold;
            font-size: 16px;
            text-shadow: 2px 2px 6px rgba(0,0,0,0.9);
            white-space: nowrap;
            max-width: 140px;
            overflow: hidden;
            text-overflow: ellipsis;
            text-align: center;
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            backdrop-filter: blur(4px);
        }}
        .center-circle {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 84px;
            height: 84px;
            background: linear-gradient(135deg, #f39c12, #e67e22);
            border: 4px solid white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            z-index: 20;
        }}
    </style>
</head>
<body>
    <div class="roulette-container">
        <div class="arrow"></div>
        
        <!-- 重要：ラベルをルーレット内部に配置 -->
        <div id="wheel">
            {labels_html}
        </div>
        
        <div class="center-circle">🍶</div>
    </div>
    
    <script>
        (function() {{
            const wheel = document.getElementById('wheel');
            const spinning = {str(spinning).lower()};
            const targetRotation = {total_rotation};
            
            if (spinning) {{
                // スピン開始時の設定
                wheel.style.transition = 'none';
                wheel.style.transform = 'rotate(0deg)';
                
                // スムーズなアニメーション開始
                requestAnimationFrame(() => {{
                    requestAnimationFrame(() => {{
                        wheel.style.transition = 'transform 3s cubic-bezier(0.25, 0.1, 0.25, 1)';
                        wheel.style.transform = `rotate(${{targetRotation}}deg)`;
                    }});
                }});
            }} else {{
                // 静止状態
                wheel.style.transition = 'transform 0.5s ease-out';
                wheel.style.transform = `rotate(${{targetRotation}}deg)`;
            }}
        }})();
    </script>
</body>
</html>
"""
    return html_content

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
            st.write(f"酔い度: {p['drunk_degree']:.1f}%")

# メインアプリケーション
st.title("🍶 AIルーレット飲みゲーム")

# メニュー画面
if st.session_state.game_state == 'menu':
    st.markdown("---")
    st.markdown("""
    ### 🎯 ゲームの目的
    このゲームは、**みんなの酔い度を均等にする**ための飲みゲームです！
    
    - お酒の強さと好き嫌いに応じて飲み量を調整
    - 15ラウンドのルーレット
    - 突発イベントもあり！
    """)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🆕 新しいゲームを開始", use_container_width=True, type="primary"):
            st.session_state.game_state = 'input_players'
            st.session_state.players = []
            st.rerun()
    
    with col2:
        if st.session_state.saved_players and st.button("👥 前回のプレイヤーで開始", use_container_width=True):
            st.session_state.players = [p.copy() for p in st.session_state.saved_players]
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
    st.subheader("👥 参加者情報の入力")
    
    num_players = st.number_input("参加人数（5〜12人）", min_value=5, max_value=12, value=5)
    
    st.markdown("---")
    
    players_temp = []
    
    for i in range(num_players):
        with st.expander(f"プレイヤー {i+1}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                name = st.text_input("名前", key=f"name_{i}", value=f"プレイヤー{i+1}")
            
            with col2:
                strength = st.slider("お酒の強さ", 1, 5, 3, key=f"strength_{i}")
            
            with col3:
                preference = st.slider("お酒の好き嫌い", 1, 5, 3, key=f"preference_{i}")
            
            with col4:
                cup_type = st.selectbox("基準量", ['おちょこ', 'ジョッキ', 'どちらも'], key=f"cup_{i}")
            
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
        st.session_state.selected_player_index = None
        st.session_state.spinning = False
        st.rerun()

# ゲーム中
elif st.session_state.game_state == 'playing':
    st.markdown(f"### 🎲 ラウンド {st.session_state.round_count + 1}/{st.session_state.max_rounds}")
    
    if st.session_state.round_count < st.session_state.max_rounds:
        # ルーレット表示
        if st.session_state.spinning:
            # 回転アニメーション表示
            components.html(
                create_roulette_html(st.session_state.players, 
                                   selected_index=st.session_state.selected_player_index, 
                                   spinning=True), 
                height=520, 
                scrolling=False
            )
            
            # アニメーション完了を待つ
            with st.spinner("🎯 ルーレット回転中..."):
                time.sleep(3.2)  # アニメーション時間 + 少し余裕
            
            st.session_state.spinning = False
            st.rerun()
            
        elif st.session_state.selected_player_index is not None:
            # 結果表示状態
            components.html(
                create_roulette_html(st.session_state.players, 
                                   selected_index=st.session_state.selected_player_index), 
                height=520, 
                scrolling=False
            )
        else:
            # 初期状態
            components.html(create_roulette_html(st.session_state.players), height=520, scrolling=False)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🎯 ルーレットを回す", use_container_width=True, type="primary", 
                        disabled=st.session_state.spinning):
                # 結果を事前に決定
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
                st.session_state.spinning = True
                st.rerun()
        
        with col2:
            if st.session_state.selected_player_index is not None and not st.session_state.spinning:
                if st.button("➡️ 次のラウンドへ", use_container_width=True):
                    st.session_state.selected_player_index = None
                    st.session_state.last_selected = None
                    st.rerun()
        
        # 結果表示
        if st.session_state.last_selected and not st.session_state.spinning:
            st.markdown("---")
            st.success(f"🎯 選ばれた人: **{st.session_state.last_selected}**")
            st.info(f"🍶 飲む量: **{st.session_state.last_drink}**")
            
            if st.session_state.sudden_event_player:
                st.markdown("---")
                st.error(f"⚡ **{st.session_state.sudden_event_player}**さん、アウト！")
                st.warning(f"🍷 飲む量: **{st.session_state.sudden_event_drink}**")
        
        # 現在のステータス
        if not st.session_state.spinning:
            display_status()
    
    else:
        st.session_state.game_state = 'finished'
        st.rerun()

# ゲーム終了画面
elif st.session_state.game_state == 'finished':
    st.markdown("---")
    st.markdown("# 🎉 ゲーム終了！最終ランキング")
    st.markdown("---")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
            
            with col1:
                medals = ["", "🥇", "🥈", "🥉"]
                medal = medals[i] if i <= 3 else ""
                st.markdown(f"### {medal} {i}位")
            
            with col2:
                st.markdown(f"**{p['name']}**")
            
            with col3:
                st.progress(p['drunk_degree'] / 100)
            
            with col4:
                st.write(f"酔い度: {p['drunk_degree']:.1f}%")
                st.write(f"飲んだ量: {p['total_drunk']:.1f}杯分")
    
    st.markdown("---")
    
    # 勝者特権
    winner = sorted_players[0]
    st.success(f"🏆 **{winner['name']}**さんが勝者です！")
    st.info(f"**{winner['name']}**さんは他の人に1杯飲ませることができます！")
    
    victim_name = st.selectbox("誰に飲ませますか？", 
                              [p['name'] for p in st.session_state.players if p['name'] != winner['name']])
    
    if st.button("👑 特権発動！", use_container_width=True):
        for p in st.session_state.players:
            if p['name'] == victim_name:
                multiplier = calculate_drink_amount(p)
                drink_display = get_drink_display(multiplier, p['cup_type'])
                st.success(f"👑 {winner['name']}の特権発動！")
                st.warning(f"**{p['name']}**さんが飲みます: {drink_display}")
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
            st.session_state.selected_player_index = None
            st.session_state.spinning = False
            st.rerun()
    
    with col2:
        if st.button("🏠 メニューに戻る", use_container_width=True):
            st.session_state.game_state = 'menu'
            st.rerun()
