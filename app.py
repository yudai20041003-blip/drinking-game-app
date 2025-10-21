import streamlit as st
import streamlit.components.v1 as components
import random
import time

# AIモジュール（オプション）
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    st.warning("⚠️ google-generativeai がインストールされていません。AI機能なしで動作します。")

# ページ設定
st.set_page_config(page_title="🍶 バランサールーレット2.0", page_icon="🍶", layout="wide")

# Gemini API設定（オプション）
GEMINI_API_KEY = None
if AI_AVAILABLE:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
        except Exception as e:
            st.error(f"Gemini API設定エラー: {e}")
            GEMINI_API_KEY = None

# セッション状態の初期化
def init_session_state():
    defaults = {
        'game_state': 'menu',
        'players': [],
        'saved_players': [],
        'round_count': 0,
        'max_rounds': 15,
        'spinning': False,
        'selected_player_index': None,
        'selected_special': None,
        'last_selected': None,
        'last_drink': None,
        'last_special_effect': None,
        'ai_event_description': None,
        'special_effects_active': {}
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

def calculate_drink_amount(player, multiplier=1.0):
    """飲み量を計算（倍率対応）"""
    strength = player['strength']
    preference = player['preference']
    
    if strength <= 2:
        if preference <= 2: base_multiplier = 0.5
        elif preference == 3: base_multiplier = 0.75
        else: base_multiplier = 1.0
    elif strength == 3:
        if preference <= 2: base_multiplier = 0.75
        elif preference == 3: base_multiplier = 1.0
        else: base_multiplier = 1.5
    else:
        if preference <= 3: base_multiplier = 1.5
        else: base_multiplier = 2.0
    
    return base_multiplier * multiplier

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

def calculate_player_weight(player):
    """公平性を考慮した重み計算"""
    # 酔い度が低いほど重くなる公平ウェイト
    base = 0.4 + (1.0 - player["drunk_degree"]/100.0) * 1.2
    # 個人特性による微調整
    adj = 1.0 + (5 - player["strength"]) * 0.05 + (player["preference"] - 3) * 0.05
    weight = max(0.1, base * adj)
    return weight

def smart_player_selection(players):
    """AI強化版プレイヤー選択"""
    # 特別セクション判定（15%の確率）
    if random.random() < 0.15:
        special_types = ['shield', 'double', 'everyone']
        selected_special = random.choice(special_types)
        return None, selected_special
    
    # 通常のプレイヤー選択（重み付きランダム）
    weights = [calculate_player_weight(p) for p in players]
    selected_player = random.choices(players, weights=weights)[0]
    selected_index = players.index(selected_player)
    
    return selected_index, None

def generate_ai_event(selected_player, all_players):
    """AI による追加イベント生成"""
    if not GEMINI_API_KEY or not AI_AVAILABLE:
        return None
    
    try:
        # 他のプレイヤーの状況を要約
        other_status = []
        for p in all_players:
            if p['name'] != selected_player['name']:
                other_status.append(f"{p['name']}: 酔い度{p['drunk_degree']:.1f}%")
        
        other_info = ", ".join(other_status) if other_status else "他にプレイヤーなし"
        
        prompt = f"""
        飲みゲームのAIマスターとして、ゲームを盛り上げる追加イベントを提案してください。
        
        選ばれたプレイヤー: {selected_player['name']}
        酔い度: {selected_player['drunk_degree']:.1f}%
        総飲酒量: {selected_player['total_drunk']:.1f}杯
        
        他のプレイヤー: {other_info}
        
        以下のいずれかの形式で簡潔に提案してください：
        - 「追加で0.5杯飲む」（さらに飲む）
        - 「今回は免除」（飲まなくてよい）
        - 「全員で乾杯」（みんなで少し飲む）
        - 「特別なことなし」（通常通り）
        
        理由も一言で添えてください。
        """
        
        response = genai.GenerativeModel('gemini-pro').generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        return f"AIイベント生成エラー: {str(e)[:50]}..."

def process_special_effect(special_type, players):
    """特別効果の処理"""
    if special_type == 'shield':
        target = random.choice(players)
        if target['name'] not in st.session_state.special_effects_active:
            st.session_state.special_effects_active[target['name']] = {}
        st.session_state.special_effects_active[target['name']]['shield'] = True
        return f"🛡️ **{target['name']}**さんにシールドが付与されました！"
        
    elif special_type == 'double':
        target = random.choice(players)
        multiplier = calculate_drink_amount(target, 2.0)
        drink_info = get_drink_display(multiplier, target['cup_type'])
        update_drunk_degree(target, multiplier)
        return f"⚡ **{target['name']}**さんが倍々アタック！{drink_info}"
        
    elif special_type == 'everyone':
        for player in players:
            update_drunk_degree(player, 0.5)
        return "🍻 みんなで乾杯！全員でおちょこ半分ずつ飲みましょう！"
    
    return "特別効果が発生しました！"

def create_enhanced_roulette_html(players, selected_index=None, selected_special=None, spinning=False):
    """進化したルーレットHTML生成"""
    num_players = len(players)
    colors = ['#FF6666', '#4ECDCA', '#4587D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#88BFCE', '#B5C1E2', '#B8B195', '#C8C6B4',
              '#6C5E7B', '#355C70']
    
    # 特別セクションも含めた全セクション数
    special_sections = 3
    total_sections = num_players + special_sections
    angle_per_section = 360 / total_sections
    
    # グラデーション作成
    gradient_stops = []
    section_index = 0
    
    # プレイヤーセクション
    for i in range(num_players):
        start_angle = section_index * angle_per_section
        end_angle = (section_index + 1) * angle_per_section
        color = colors[i % len(colors)]
        gradient_stops.append(f"{color} {start_angle}deg {end_angle}deg")
        section_index += 1
    
    # 特別セクション
    special_colors = ['#3498db', '#e74c3c', '#f39c12']  # シールド、倍々、みんなで乾杯
    for i, color in enumerate(special_colors):
        start_angle = section_index * angle_per_section
        end_angle = (section_index + 1) * angle_per_section
        gradient_stops.append(f"{color} {start_angle}deg {end_angle}deg")
        section_index += 1
    
    gradient = ", ".join(gradient_stops)
    
    # 回転角度の計算
    if selected_index is not None:
        target_angle = -(selected_index * angle_per_section + angle_per_section / 2)
        if spinning:
            total_rotation = target_angle + random.randint(1440, 2160)  # 4-6回転
        else:
            total_rotation = target_angle
    elif selected_special is not None:
        special_map = {'shield': 0, 'double': 1, 'everyone': 2}
        special_index = num_players + special_map.get(selected_special, 0)
        target_angle = -(special_index * angle_per_section + angle_per_section / 2)
        if spinning:
            total_rotation = target_angle + random.randint(1440, 2160)
        else:
            total_rotation = target_angle
    else:
        total_rotation = 0
    
    # ラベル生成
    labels_html = ""
    
    # プレイヤーラベル
    for i, player in enumerate(players):
        label_angle = i * angle_per_section + angle_per_section / 2
        name = str(player['name']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # シールド効果の表示
        shield_icon = "🛡️" if st.session_state.special_effects_active.get(player['name'], {}).get('shield', False) else ""
        
        labels_html += f"""
        <div class="player-label" style="--angle: {label_angle}deg;">
            <span>{shield_icon}{name}</span>
        </div>
        """
    
    # 特別セクションラベル
    special_names = ['🛡️ シールド', '⚡ 倍々', '🍻 乾杯']
    for i, special_name in enumerate(special_names):
        label_angle = (num_players + i) * angle_per_section + angle_per_section / 2
        
        labels_html += f"""
        <div class="special-label" style="--angle: {label_angle}deg;">
            <span>{special_name}</span>
        </div>
        """
    
    html_content = f"""<!DOCTYPE html>
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
            width: 500px;
            height: 500px;
        }}
        .arrow {{
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 25px solid transparent;
            border-right: 25px solid transparent;
            border-top: 50px solid #e74c3c;
            filter: drop-shadow(0 8px 16px rgba(0,0,0,0.4));
            z-index: 30;
        }}
        #wheel {{
            position: relative;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: conic-gradient({gradient});
            border: 5px solid #2c3e50;
            box-shadow: 0 25px 70px rgba(0,0,0,0.4);
            overflow: visible;
            transform: rotate(0deg);
            transition: transform 0.1s ease;
            z-index: 5;
        }}
        .player-label, .special-label {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: rotate(var(--angle)) translateY(-200px) rotate(calc(-1 * var(--angle)));
            transform-origin: center center;
            pointer-events: none;
        }}
        .player-label span, .special-label span {{
            display: inline-block;
            padding: 6px 14px;
            color: white;
            font-weight: bold;
            font-size: 14px;
            text-shadow: 2px 2px 8px rgba(0,0,0,0.9);
            white-space: nowrap;
            max-width: 120px;
            overflow: hidden;
            text-overflow: ellipsis;
            text-align: center;
            background: rgba(0,0,0,0.4);
            border-radius: 15px;
            backdrop-filter: blur(6px);
            border: 2px solid rgba(255,255,255,0.3);
        }}
        .special-label span {{
            background: rgba(255,215,0,0.3);
            border: 2px solid rgba(255,215,0,0.6);
            font-size: 12px;
        }}
        .center-circle {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90px;
            height: 90px;
            background: linear-gradient(135deg, #f39c12, #e67e22);
            border: 5px solid white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
            z-index: 20;
        }}
    </style>
</head>
<body>
    <div class="roulette-container">
        <div class="arrow"></div>
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
                wheel.style.transition = 'none';
                wheel.style.transform = 'rotate(0deg)';
                
                requestAnimationFrame(() => {{
                    requestAnimationFrame(() => {{
                        wheel.style.transition = 'transform 4s cubic-bezier(0.25, 0.1, 0.25, 1)';
                        wheel.style.transform = `rotate(${{targetRotation}}deg)`;
                    }});
                }});
            }} else {{
                wheel.style.transition = 'transform 0.6s ease-out';
                wheel.style.transform = `rotate(${{targetRotation}}deg)`;
            }}
        }})();
    </script>
</body>
</html>"""
    return html_content

def analyze_game_balance():
    """ゲームバランス分析"""
    if len(st.session_state.players) < 2:
        return "分析データが不足しています。"
    
    drunk_degrees = [p['drunk_degree'] for p in st.session_state.players]
    avg_drunk = sum(drunk_degrees) / len(drunk_degrees)
    max_drunk = max(drunk_degrees)
    min_drunk = min(drunk_degrees)
    
    if max_drunk == min_drunk:
        balance_score = 100
    else:
        balance_score = max(0, 100 - (max_drunk - min_drunk))
    
    analysis = f"""
    **🎯 ゲームバランス分析（ラウンド {st.session_state.round_count}）**
    
    **バランススコア**: {balance_score:.1f}/100
    **平均酔い度**: {avg_drunk:.1f}%
    **最大差**: {max_drunk - min_drunk:.1f}%
    """
    
    if balance_score >= 80:
        analysis += "\n✅ **素晴らしいバランス**です！"
    elif balance_score >= 60:
        analysis += "\n⚖️ **良好なバランス**です。"
    elif balance_score >= 40:
        analysis += "\n⚠️ **やや不均衡**です。"
    else:
        analysis += "\n🚨 **バランス調整中**です。"
    
    return analysis

def display_enhanced_status():
    """強化されたステータス表示"""
    st.markdown("---")
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("📊 現在の酔い度")
        
        sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
        
        for i, p in enumerate(sorted_players, 1):
            col_rank, col_name, col_progress, col_stats = st.columns([1, 2, 3, 2])
            
            with col_rank:
                medals = ["", "🥇", "🥈", "🥉"]
                medal = medals[i] if i <= 3 else f"{i}位"
                st.write(medal)
            
            with col_name:
                effects = st.session_state.special_effects_active.get(p['name'], {})
                shield_icon = "🛡️" if effects.get('shield') else ""
                st.write(f"**{shield_icon}{p['name']}**")
            
            with col_progress:
                st.progress(p['drunk_degree'] / 100)
            
            with col_stats:
                st.write(f"{p['drunk_degree']:.1f}%")
                st.caption(f"{p['total_drunk']:.1f}杯")
    
    with col2:
        st.subheader("🤖 AI分析")
        analysis = analyze_game_balance()
        st.markdown(analysis)
        
        # AI機能の状態表示
        if GEMINI_API_KEY and AI_AVAILABLE:
            st.success("✅ AI機能: 有効")
        else:
            st.info("ℹ️ AI機能: 無効")

# メインアプリケーション
st.title("🍶 バランサールーレット2.0")
st.caption("AI強化版 - より公平で盛り上がる飲みゲーム！")

# メニュー画面
if st.session_state.game_state == 'menu':
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🚀 新機能満載の進化版！
        
        **✨ 追加された革新的機能:**
        - **🤖 真のAI活用**: Gemini APIによるリアルタイム分析
        - **⚖️ スマート重み付け**: 酔い度が低い人ほど選ばれやすい
        - **🎭 特別セクション**: 3種類の特殊効果
        - **📊 AIバランス分析**: ゲーム公平性の可視化
        - **🛡️ 戦略要素**: シールドや倍々効果
        
        **🎪 特別セクション:**
        - 🛡️ **シールド**: 次回1回まで選ばれても無効
        - ⚡ **倍々**: 飲む量が2倍に
        - 🍻 **みんなで乾杯**: 全員で少しずつ
        """)
    
    with col2:
        st.markdown("### ⚙️ 設定")
        
        difficulty = st.selectbox(
            "ゲーム設定",
            ["ソフト（ゆるめ）", "ノーマル（標準）", "ハード（激しめ）"],
            index=1
        )
        
        if difficulty == "ソフト（ゆるめ）":
            st.session_state.max_rounds = 12
            st.info("🌸 ゆったりペース")
        elif difficulty == "ハード（激しめ）":
            st.session_state.max_rounds = 20
            st.warning("🔥 上級者向け")
        else:
            st.session_state.max_rounds = 15
            st.success("⚖️ バランス良好")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🆕 新しいゲームを開始", use_container_width=True, type="primary"):
            st.session_state.game_state = 'input_players'
            st.session_state.players = []
            st.session_state.special_effects_active = {}
            st.rerun()
    
    with col2:
        if st.session_state.saved_players and st.button("👥 前回のプレイヤーで開始", use_container_width=True):
            st.session_state.players = [p.copy() for p in st.session_state.saved_players]
            for p in st.session_state.players:
                p['drunk_degree'] = 0
                p['total_drunk'] = 0
            st.session_state.game_state = 'playing'
            st.session_state.round_count = 0
            st.session_state.special_effects_active = {}
            st.rerun()

# プレイヤー入力画面
elif st.session_state.game_state == 'input_players':
    st.markdown("---")
    st.subheader("👥 参加者情報の入力")
    
    num_players = st.number_input("参加人数（3〜12人）", min_value=3, max_value=12, value=5)
    
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
        st.session_state.selected_player_index = None
        st.session_state.selected_special = None
        st.session_state.spinning = False
        st.session_state.special_effects_active = {}
        st.rerun()

# ゲーム中
elif st.session_state.game_state == 'playing':
    st.markdown(f"### 🎲 ラウンド {st.session_state.round_count + 1}/{st.session_state.max_rounds}")
    
    if st.session_state.round_count < st.session_state.max_rounds:
        # ルーレット表示
        if st.session_state.spinning:
            components.html(
                create_enhanced_roulette_html(st.session_state.players, 
                                            selected_index=st.session_state.selected_player_index,
                                            selected_special=st.session_state.selected_special,
                                            spinning=True), 
                height=550, 
                scrolling=False
            )
            
            with st.spinner("🎯 バランサールーレット回転中..."):
                time.sleep(4.2)
            
            st.session_state.spinning = False
            st.rerun()
            
        elif st.session_state.selected_player_index is not None or st.session_state.selected_special is not None:
            components.html(
                create_enhanced_roulette_html(st.session_state.players, 
                                            selected_index=st.session_state.selected_player_index,
                                            selected_special=st.session_state.selected_special), 
                height=550, 
                scrolling=False
            )
        else:
            components.html(create_enhanced_roulette_html(st.session_state.players), height=550, scrolling=False)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if st.button("🎯 スマートルーレットを回す", use_container_width=True, type="primary", 
                        disabled=st.session_state.spinning):
                
                # スマート選択実行
                selected_index, selected_special = smart_player_selection(st.session_state.players)
                
                st.session_state.selected_player_index = selected_index
                st.session_state.selected_special = selected_special
                
                if selected_special:
                    # 特別効果の処理
                    effect_msg = process_special_effect(selected_special, st.session_state.players)
                    st.session_state.last_special_effect = effect_msg
                    
                elif selected_index is not None:
                    # 通常のプレイヤー選択
                    selected_player = st.session_state.players[selected_index]
                    
                    # シールド効果の確認
                    if st.session_state.special_effects_active.get(selected_player['name'], {}).get('shield', False):
                        st.session_state.last_selected = selected_player['name']
                        st.session_state.last_drink = "シールドで無効化！"
                        # シールド消費
                        st.session_state.special_effects_active[selected_player['name']]['shield'] = False
                    else:
                        multiplier = calculate_drink_amount(selected_player)
                        drink_display = get_drink_display(multiplier, selected_player['cup_type'])
                        
                        st.session_state.last_selected = selected_player['name']
                        st.session_state.last_drink = drink_display
                        
                        update_drunk_degree(selected_player, multiplier)
                        
                        # AI追加イベント生成
                        ai_event = generate_ai_event(selected_player, st.session_state.players)
                        if ai_event:
                            st.session_state.ai_event_description = ai_event
                
                st.session_state.round_count += 1
                st.session_state.spinning = True
                st.rerun()
        
        with col2:
            if (st.session_state.selected_player_index is not None or st.session_state.selected_special is not None) and not st.session_state.spinning:
                if st.button("➡️ 次のラウンドへ", use_container_width=True):
                    st.session_state.selected_player_index = None
                    st.session_state.selected_special = None
                    st.session_state.last_selected = None
                    st.session_state.last_special_effect = None
                    st.session_state.ai_event_description = None
                    st.rerun()
        
        # 結果表示
        if not st.session_state.spinning:
            if st.session_state.last_special_effect:
                st.markdown("---")
                st.success("🎊 特別効果発動！")
                st.info(st.session_state.last_special_effect)
                
            elif st.session_state.last_selected:
                st.markdown("---")
                st.success(f"🎯 選ばれた人: **{st.session_state.last_selected}**")
                st.info(f"🍶 飲む量: **{st.session_state.last_drink}**")
                
                # AIイベント表示
                if st.session_state.ai_event_description:
                    st.markdown("**🤖 AIマスターからの追加提案:**")
                    st.warning(st.session_state.ai_event_description)
        
        # 強化されたステータス表示
        if not st.session_state.spinning:
            display_enhanced_status()
    
    else:
        st.session_state.game_state = 'finished'
        st.rerun()

# ゲーム終了画面
elif st.session_state.game_state == 'finished':
    st.markdown("---")
    st.markdown("# 🎉 バランサールーレット2.0 ゲーム終了！")
    st.markdown("---")
    
    # 最終分析
    final_analysis = analyze_game_balance()
    st.markdown(final_analysis)
    
    st.markdown("### 🏆 最終ランキング")
    
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
    
    other_players = [p['name'] for p in st.session_state.players if p['name'] != winner['name']]
    if other_players:
        victim_name = st.selectbox("誰に飲ませますか？", other_players)
        
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
            st.session_state.selected_player_index = None
            st.session_state.selected_special = None
            st.session_state.spinning = False
            st.session_state.special_effects_active = {}
            st.rerun()
    
    with col2:
        if st.button("🏠 メニューに戻る", use_container_width=True):
            st.session_state.game_state = 'menu'
            st.rerun()
