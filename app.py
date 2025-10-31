import streamlit as st
import streamlit.components.v1 as components
import random
import time
import json

# AIモジュール（オプション）
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    st.warning("⚠️ google-generativeai がインストールされていません。AI機能なしで動作します。")

# ページ設定
st.set_page_config(page_title="🍶 AIルーレット飲みゲーム", page_icon="🍶", layout="wide")

# スマホ対応の高度なCSS実装
st.markdown("""
<style>
    /* モバイル最適化のメインCSS */
    @media (max-width: 768px) {
        .stButton > button {
            width: 100% !important;
            height: 52px !important;
            font-size: 16px !important;
            margin: 8px 0 !important;
            border-radius: 8px !important;
        }
        
        .block-container {
            padding-top: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        .stSelectbox > div > div, .stTextInput > div > div > input, 
        .stNumberInput input, .stSlider label {
            font-size: 16px !important;
        }
        
        .stTextInput > div > div > input {
            height: 45px !important;
        }
        
        .stExpander > div > div > div > button {
            font-size: 16px !important;
            padding: 12px !important;
        }
        
        .stMarkdown h1 { font-size: 24px !important; }
        .stMarkdown h2 { font-size: 20px !important; }
        .stMarkdown h3 { font-size: 18px !important; }
    }
    
    /* クイズ専用スタイル */
    .quiz-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        color: white;
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    
    .quiz-question {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 15px;
        text-align: center;
    }
    
    .quiz-hint {
        font-style: italic;
        opacity: 0.9;
        margin-bottom: 15px;
        text-align: center;
    }
    
    .participant-status {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 15px 0;
    }
    
    .participant-card {
        background: rgba(255,255,255,0.1);
        padding: 10px 15px;
        border-radius: 8px;
        border: 2px solid rgba(255,255,255,0.3);
        color: white;
        font-weight: bold;
    }
    
    .eliminated-card {
        background: rgba(0,255,0,0.2);
        border-color: rgba(0,255,0,0.6);
    }
    
    .penalty-card {
        background: rgba(255,0,0,0.2);
        border-color: rgba(255,0,0,0.6);
    }
</style>
""", unsafe_allow_html=True)

# Gemini API設定
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
        'had_sudden_event': False,
        'spinning': False,
        'selected_player_index': None,
        'last_selected': None,
        'last_drink': None,
        'sudden_event_player': None,
        'sudden_event_drink': None,
        # 口頭回答クイズシステム
        'quiz_phase': 'none',  # 'none', 'active', 'result'
        'quiz_list': [],  # 全クイズリスト
        'current_quiz_index': 0,  # 現在のクイズ番号
        'quiz_participants': [],  # 参加者リスト
        'quiz_eliminated': [],  # 正解して脱落した人
        'quiz_excluded': None,  # 不参加者（飲んだ人）
        # 連続当たり救済システム
        'last_picked_rounds': {}
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ゲームロジック関数群
def calculate_drink_amount(player, multiplier_factor=1.0):
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
    
    return base_multiplier * multiplier_factor

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
    """公平性を考慮した重み計算（連続当たり救済付き）"""
    base = 0.4 + (1.0 - player["drunk_degree"]/100.0) * 1.2
    adj = 1.0 + (5 - player["strength"]) * 0.05 + (player["preference"] - 3) * 0.05
    weight = max(0.1, base * adj)
    
    # 連続当たり救済システム
    player_name = player['name']
    last_picked = st.session_state.last_picked_rounds.get(player_name, -999)
    recent_penalty = 0.5 if st.session_state.round_count - last_picked <= 2 else 1.0
    
    return weight * recent_penalty

def smart_player_selection(players):
    """AI強化版プレイヤー選択（重み付きランダム）"""
    weights = [calculate_player_weight(p) for p in players]
    selected_player = random.choices(players, weights=weights)[0]
    selected_index = players.index(selected_player)
    return selected_index

def generate_ai_quiz_batch(num_quizzes):
    """指定された数のクイズを一度に生成"""
    if not GEMINI_API_KEY or not AI_AVAILABLE:
        fallback_quizzes = [
            {"question": "日本で一番高い山は？", "answer": "富士山", "hint": "静岡県と山梨県の境界"},
            {"question": "1年は平年で何日？", "answer": "365日", "hint": "うるう年は366日"},
            {"question": "日本の首都は？", "answer": "東京", "hint": "関東地方にある"},
            {"question": "地球の衛星は？", "answer": "月", "hint": "夜空に見える"},
            {"question": "水の化学式は？", "answer": "H2O", "hint": "水素と酸素"},
            {"question": "一週間は何日？", "answer": "7日", "hint": "月曜から日曜まで"},
            {"question": "日本の国鳥は？", "answer": "キジ", "hint": "桃太郎の仲間"},
            {"question": "オリンピックは何年に一度？", "answer": "4年", "hint": "夏と冬がある"},
            {"question": "虹は何色？", "answer": "7色", "hint": "赤橙黄緑青藍紫"},
            {"question": "干支は全部で何種類？", "answer": "12種類", "hint": "ねずみから始まる"}
        ]
        
        # 必要な数だけランダムに選択
        return random.sample(fallback_quizzes, min(num_quizzes, len(fallback_quizzes)))
    
    try:
        prompt = f"""
        飲み会で盛り上がる簡単なクイズを{num_quizzes}問作ってください。
        以下のJSON配列形式で回答してください：
        [
            {{
                "question": "問題文1",
                "answer": "正解1", 
                "hint": "ヒント1"
            }},
            {{
                "question": "問題文2",
                "answer": "正解2",
                "hint": "ヒント2"
            }}
        ]
        
        条件：
        - 一般常識レベル
        - 答えは1-5文字程度
        - 楽しい雰囲気になるもの
        - 日本語で出題
        - バラエティに富んだジャンル
        """
        
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        # JSONパース処理
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1]
        
        quiz_list = json.loads(text)
        
        # バリデーション
        valid_quizzes = []
        for quiz in quiz_list:
            if isinstance(quiz, dict) and all(k in quiz for k in ("question", "answer")):
                if "hint" not in quiz:
                    quiz["hint"] = "がんばって！"
                valid_quizzes.append(quiz)
        
        if len(valid_quizzes) >= num_quizzes:
            return valid_quizzes[:num_quizzes]
        else:
            # 不足分をフォールバックで補完
            fallback_quizzes = [
                {"question": "日本で一番高い山は？", "answer": "富士山", "hint": "静岡県と山梨県の境界"},
                {"question": "1年は平年で何日？", "answer": "365日", "hint": "うるう年は366日"},
                {"question": "日本の首都は？", "answer": "東京", "hint": "関東地方にある"}
            ]
            while len(valid_quizzes) < num_quizzes:
                valid_quizzes.append(random.choice(fallback_quizzes))
            return valid_quizzes[:num_quizzes]
            
    except Exception as e:
        st.info(f"AIクイズ生成に失敗: フォールバックを使用")
        fallback_quizzes = [
            {"question": "日本で一番高い山は？", "answer": "富士山", "hint": "静岡県と山梨県の境界"},
            {"question": "1年は平年で何日？", "answer": "365日", "hint": "うるう年は366日"},
            {"question": "日本の首都は？", "answer": "東京", "hint": "関東地方にある"}
        ]
        return random.choices(fallback_quizzes, k=num_quizzes)

def create_roulette_html(players, selected_index=None, spinning=False):
    """スマホ完全対応の美しいルーレット"""
    num_players = len(players)
    colors = ['#FF6666', '#4ECDCA', '#4587D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#88BFCE', '#B5C1E2', '#B8B195', '#C8C6B4',
              '#6C5E7B', '#355C70']
    
    angle_per_section = 360 / num_players
    
    gradient_stops = []
    for i in range(num_players):
        start_angle = i * angle_per_section
        end_angle = (i + 1) * angle_per_section
        color = colors[i % len(colors)]
        gradient_stops.append(f"{color} {start_angle}deg {end_angle}deg")
    
    gradient = ", ".join(gradient_stops)
    
    if selected_index is not None:
        target_angle = -(selected_index * angle_per_section + angle_per_section / 2)
        if spinning:
            total_rotation = target_angle + random.randint(1080, 1800)
        else:
            total_rotation = target_angle
    else:
        total_rotation = 0
    
    labels_html = ""
    for i, player in enumerate(players):
        label_angle = i * angle_per_section + angle_per_section / 2
        name = str(player['name']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        labels_html += f"""
        <div class="player-label" style="--angle: {label_angle}deg;">
            <span>{name}</span>
        </div>
        """
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            width: min(90vw, 90vh, 480px);
            height: min(90vw, 90vh, 480px);
            max-width: 480px;
            max-height: 480px;
            min-width: 260px;
            min-height: 260px;
        }}
        .arrow {{
            position: absolute;
            top: calc(-1 * min(90vw, 90vh, 480px) * 0.04);
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: calc(min(90vw, 90vh, 480px) * 0.04) solid transparent;
            border-right: calc(min(90vw, 90vh, 480px) * 0.04) solid transparent;
            border-top: calc(min(90vw, 90vh, 480px) * 0.08) solid #e74c3c;
            filter: drop-shadow(0 6px 12px rgba(0,0,0,0.4));
            z-index: 30;
        }}
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
        .player-label {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: rotate(var(--angle)) translateY(calc(-1 * (min(90vw, 90vh, 480px) * 0.40))) rotate(calc(-1 * var(--angle)));
            transform-origin: center center;
            pointer-events: none;
        }}
        .player-label span {{
            display: inline-block;
            padding: clamp(3px, 1vw, 8px) clamp(6px, 2vw, 14px);
            color: white;
            font-weight: bold;
            font-size: clamp(12px, 2.8vw, 16px);
            text-shadow: 2px 2px 6px rgba(0,0,0,0.9);
            white-space: nowrap;
            max-width: clamp(70px, 18vw, 140px);
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
            width: calc(min(90vw, 90vh, 480px) * 0.175);
            height: calc(min(90vw, 90vh, 480px) * 0.175);
            background: linear-gradient(135deg, #f39c12, #e67e22);
            border: 4px solid white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: clamp(20px, 5vw, 28px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            z-index: 20;
        }}
        
        @media (max-width: 768px) {{
            .roulette-container {{
                min-width: 240px;
                min-height: 240px;
            }}
        }}
        
        @media (max-width: 480px) {{
            .player-label span {{
                font-size: 10px;
                padding: 2px 5px;
                max-width: 50px;
            }}
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
                        wheel.style.transition = 'transform 3s cubic-bezier(0.25, 0.1, 0.25, 1)';
                        wheel.style.transform = `rotate(${{targetRotation}}deg)`;
                    }});
                }});
            }} else {{
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
st.caption("スマホ対応・口頭クイズ機能付き！")

# メニュー画面
if st.session_state.game_state == 'menu':
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 🎯 ゲームの目的
        このゲームは、**みんなの酔い度を均等にする**ための飲みゲームです！
        
        **✨ 新機能追加:**
        - **📱 完全スマホ対応**: どこでも快適にプレイ
        - **🗣️ 口頭クイズシステム**: 人数-2問で早抜けゲーム
        - **⚖️ 連続当たり救済**: 同じ人が連続で選ばれにくい
        - **⏹️ 途中終了機能**: いつでもゲームを終了可能
        - お酒の強さと好き嫌いに応じて飲み量を調整
        - 15ラウンドのルーレット
        - 突発イベントもあり！
        """)
        
        # リモートプレイの案内
        with st.expander("🌐 リモートプレイの方法", expanded=False):
            st.markdown("""
            **推奨方法: 画面共有**
            
            1. **ゲームマスター**が一人、このアプリを操作
            2. **Zoom/Meet/Discord**などで画面を共有
            3. 参加者は共有画面を見ながら**音声**で参加
            4. クイズは口頭で答える → マスターが正解ボタンを押す
            
            **メリット:**
            - 設定が簡単で安定動作
            - 全員が同じ画面を見て一体感
            - 音声通話で盛り上がる
            - スマホでも快適に参加可能
            """)
    
    with col2:
        st.markdown("### ⚙️ AI機能状態")
        if GEMINI_API_KEY and AI_AVAILABLE:
            st.success("✅ AI機能: 有効")
            st.caption("クイズ自動生成可能")
        else:
            st.info("ℹ️ AI機能: 無効")
            st.caption("固定クイズで動作")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🆕 新しいゲームを開始", use_container_width=True, type="primary"):
            st.session_state.game_state = 'input_players'
            st.session_state.players = []
            st.session_state.last_picked_rounds = {}
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
            st.session_state.last_picked_rounds = {}
            st.session_state.quiz_phase = 'none'
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
        st.session_state.had_sudden_event = False
        st.session_state.selected_player_index = None
        st.session_state.spinning = False
        st.session_state.last_picked_rounds = {}
        st.session_state.quiz_phase = 'none'
        st.rerun()

# ゲーム中
elif st.session_state.game_state == 'playing':
    # 途中終了ボタン（常に表示）
    col_title, col_end = st.columns([4, 1])
    with col_title:
        st.markdown(f"### 🎲 ラウンド {st.session_state.round_count + 1}/{st.session_state.max_rounds}")
    with col_end:
        if st.button("⏹️ ゲーム終了", use_container_width=True, type="secondary"):
            st.session_state.game_state = 'finished'
            st.rerun()
    
    if st.session_state.round_count < st.session_state.max_rounds:
        # 口頭クイズフェーズの処理
        if st.session_state.quiz_phase == 'active':
            st.markdown("---")
            st.markdown('<div class="quiz-container">', unsafe_allow_html=True)
            st.markdown("## 🗣️ 口頭クイズタイム！")
            
            # 現在のクイズ表示
            current_quiz = st.session_state.quiz_list[st.session_state.current_quiz_index]
            st.markdown(f'<div class="quiz-question">第{st.session_state.current_quiz_index + 1}問: {current_quiz["question"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="quiz-hint">💡 ヒント: {current_quiz.get("hint", "がんばって！")}</div>', unsafe_allow_html=True)
            
            # 正解表示（マスター用）
            with st.expander("👀 正解を確認（マスター用）", expanded=False):
                st.success(f"正解: **{current_quiz['answer']}**")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 参加者状況表示
            remaining = [p for p in st.session_state.quiz_participants if p not in st.session_state.quiz_eliminated]
            
            st.markdown("### 👥 参加者状況")
            st.markdown(f"**🏃 参加中**: {', '.join(remaining)} ({len(remaining)}人)")
            if st.session_state.quiz_eliminated:
                st.markdown(f"**✅ 正解済み**: {', '.join(st.session_state.quiz_eliminated)} ({len(st.session_state.quiz_eliminated)}人)")
            if st.session_state.quiz_excluded:
                st.markdown(f"**🍷 不参加**: {st.session_state.quiz_excluded} (直前に飲んだため)")
            
            if len(remaining) > 2:
                # 正解者選択
                selected_correct_player = st.selectbox(
                    "🎯 正解した人は誰ですか？",
                    ['選択してください'] + remaining,
                    key="correct_player_select"
                )
                
                col_quiz_btn1, col_quiz_btn2 = st.columns(2)
                with col_quiz_btn1:
                    if st.button("✅ 正解！", use_container_width=True, type="primary", 
                                disabled=(selected_correct_player == '選択してください')):
                        st.session_state.quiz_eliminated.append(selected_correct_player)
                        st.success(f"🎉 {selected_correct_player}さん正解！クイズから脱落")
                        
                        # 次のクイズへ
                        if st.session_state.current_quiz_index < len(st.session_state.quiz_list) - 1:
                            st.session_state.current_quiz_index += 1
                        else:
                            st.session_state.quiz_phase = 'result'
                        st.rerun()
                
                with col_quiz_btn2:
                    if st.button("⏭️ このクイズをスキップ", use_container_width=True):
                        if st.session_state.current_quiz_index < len(st.session_state.quiz_list) - 1:
                            st.session_state.current_quiz_index += 1
                        else:
                            st.session_state.quiz_phase = 'result'
                        st.rerun()
                        
            else:
                # 残り2人以下 → 結果へ
                st.info("残りが2人以下になりました。クイズ終了です。")
                if st.button("📊 結果発表！", use_container_width=True, type="primary"):
                    st.session_state.quiz_phase = 'result'
                    st.rerun()
                
        elif st.session_state.quiz_phase == 'result':
            st.markdown("---")
            st.markdown("## 🎉 クイズ結果発表")
            
            # 結果表示
            remaining = [p for p in st.session_state.quiz_participants if p not in st.session_state.quiz_eliminated]
            
            if st.session_state.quiz_eliminated:
                st.success("🎊 正解者（クイズから脱落）")
                st.markdown('<div class="participant-status">', unsafe_allow_html=True)
                for name in st.session_state.quiz_eliminated:
                    st.markdown(f'<div class="participant-card eliminated-card">✅ {name}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            if remaining:
                st.warning("🐌 最後まで残った人（ペナルティ対象）")
                st.markdown('<div class="participant-status">', unsafe_allow_html=True)
                for name in remaining:
                    st.markdown(f'<div class="participant-card penalty-card">💥 {name}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # ペナルティ適用
                for player in st.session_state.players:
                    if player['name'] in remaining:
                        penalty_multiplier = 0.5
                        multiplier = calculate_drink_amount(player, penalty_multiplier)
                        drink_display = get_drink_display(multiplier, player['cup_type'])
                        update_drunk_degree(player, multiplier)
                        st.info(f"🍶 {player['name']}のペナルティ: {drink_display}")
            
            if st.session_state.quiz_excluded:
                st.info(f"🍷 不参加: {st.session_state.quiz_excluded}（直前に飲んだため）")
            
            if st.button("🎲 ゲーム再開（次のラウンドへ）", use_container_width=True, type="primary"):
                st.session_state.quiz_phase = 'none'
                st.session_state.quiz_list = []
                st.session_state.current_quiz_index = 0
                st.session_state.quiz_participants = []
                st.session_state.quiz_eliminated = []
                st.session_state.quiz_excluded = None
                st.session_state.selected_player_index = None
                st.session_state.last_selected = None
                st.session_state.sudden_event_player = None
                st.session_state.sudden_event_drink = None
                st.rerun()

        # 通常のルーレット処理
        else:
            # ルーレット表示
            if st.session_state.spinning:
                components.html(
                    create_roulette_html(st.session_state.players, 
                                       selected_index=st.session_state.selected_player_index, 
                                       spinning=True), 
                    height=520, 
                    scrolling=False
                )
                
                with st.spinner("🎯 ルーレット回転中..."):
                    time.sleep(3.2)
                
                st.session_state.spinning = False
                st.rerun()
                
            elif st.session_state.selected_player_index is not None:
                components.html(
                    create_roulette_html(st.session_state.players, 
                                       selected_index=st.session_state.selected_player_index), 
                    height=520, 
                    scrolling=False
                )
            else:
                components.html(create_roulette_html(st.session_state.players), height=520, scrolling=False)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("🎯 ルーレットを回す", use_container_width=True, type="primary", 
                            disabled=st.session_state.spinning):
                    # スマート選択実行
                    selected_index = smart_player_selection(st.session_state.players)
                    selected_player = st.session_state.players[selected_index]
                    
                    st.session_state.selected_player_index = selected_index
                    st.session_state.last_picked_rounds[selected_player['name']] = st.session_state.round_count
                    
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
                        st.session_state.sudden_event_drink = None
                    
                    st.session_state.round_count += 1
                    st.session_state.spinning = True
                    st.rerun()
            
            with col2:
                if st.session_state.selected_player_index is not None and not st.session_state.spinning:
                    # クイズフェーズへ移行するボタン
                    if st.button("🗣️ クイズタイムで一息", use_container_width=True, type="secondary"):
                        # クイズ数を計算（人数-2）
                        num_participants = len(st.session_state.players) - 1  # 飲んだ人を除く
                        if num_participants < 3:  # 最低3人必要（最後に2人残すため）
                            st.warning("クイズに参加できる人が少なすぎます。（飲んだ人を除いて3人以上必要）")
                        else:
                            num_quizzes = num_participants - 2  # 最後の2人になるまで
                            st.session_state.quiz_list = generate_ai_quiz_batch(num_quizzes)
                            st.session_state.current_quiz_index = 0
                            
                            # 参加者設定（飲んだ人を除く）
                            excluded_player = st.session_state.last_selected
                            participants = [p['name'] for p in st.session_state.players if p['name'] != excluded_player]
                            
                            st.session_state.quiz_participants = participants
                            st.session_state.quiz_eliminated = []
                            st.session_state.quiz_excluded = excluded_player
                            st.session_state.quiz_phase = 'active'
                            st.rerun()
            
            with col3:
                if st.session_state.selected_player_index is not None and not st.session_state.spinning:
                    if st.button("➡️ 次のラウンドへ", use_container_width=True):
                        st.session_state.selected_player_index = None
                        st.session_state.last_selected = None
                        st.session_state.sudden_event_player = None
                        st.session_state.sudden_event_drink = None
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
        if not st.session_state.spinning and st.session_state.quiz_phase == 'none':
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
            st.session_state.had_sudden_event = False
            st.session_state.selected_player_index = None
            st.session_state.spinning = False
            st.session_state.last_picked_rounds = {}
            st.session_state.quiz_phase = 'none'
            st.rerun()
    
    with col2:
        if st.button("🏠 メニューに戻る", use_container_width=True):
            st.session_state.game_state = 'menu'
            st.rerun()
