import streamlit as st
import streamlit.components.v1 as components
import random
import time
import json
import base64
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
from io import BytesIO
import numpy as np

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
    
    /* アバタープレビュー強化 */
    .avatar-preview {
        display: flex;
        align-items: center;
        gap: 15px;
        padding: 15px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        margin: 10px 0;
        color: white;
    }
    
    .avatar-comparison {
        display: flex;
        gap: 20px;
        align-items: center;
        justify-content: center;
        margin: 15px 0;
        padding: 15px;
        background: rgba(0,0,0,0.05);
        border-radius: 12px;
    }
    
    .avatar-item {
        text-align: center;
        padding: 10px;
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        min-width: 100px;
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
        'quiz_phase': 'none',
        'quiz_list': [],
        'current_quiz_index': 0,
        'quiz_participants': [],
        'quiz_eliminated': [],
        'quiz_excluded': None,
        # 連続当たり救済システム
        'last_picked_rounds': {}
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# 高度なアニメ風画像処理関数群
def enhance_anime_colors(img, intensity=1.5):
    """アニメ風の鮮やかな色彩に強化"""
    # 彩度を大幅に上げる
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(intensity)
    
    # コントラストを調整
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)
    
    # 明度を少し上げて明るく
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)
    
    return img

def create_anime_edges(img, threshold=30):
    """アニメ風の強い輪郭線を作成"""
    # グレースケールに変換してエッジ検出
    gray = img.convert('L')
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # エッジを二値化して強調
    edges = edges.point(lambda p: 255 if p > threshold else 0)
    
    # エッジを少し太くする
    edges = edges.filter(ImageFilter.MaxFilter(size=3))
    
    return edges

def apply_posterization(img, levels=6):
    """ポスタリゼーション（色数制限）でセル画風に"""
    # 各チャンネルのビット数を制限
    bits = max(1, min(8, levels))
    return ImageOps.posterize(img, bits)

def smooth_anime_texture(img):
    """アニメらしい滑らかな質感を作成"""
    # 複数回のスムージングで滑らかに
    img = img.filter(ImageFilter.SMOOTH)
    img = img.filter(ImageFilter.SMOOTH_MORE)
    
    # ガウシアンブラーで更に滑らかに
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    
    return img

def image_to_base64(image_file, max_size=(96, 96)):
    """画像をBase64エンコードして保存用に変換"""
    try:
        img = Image.open(image_file)
        img = img.convert('RGB')
        
        # 正方形にクロップ
        width, height = img.size
        min_size = min(width, height)
        left = (width - min_size) / 2
        top = (height - min_size) / 2
        right = (width + min_size) / 2
        bottom = (height + min_size) / 2
        img = img.crop((left, top, right, bottom))
        
        # リサイズ
        img = img.resize(max_size, Image.Resampling.LANCZOS)
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        st.error(f"画像処理エラー: {e}")
        return None

def create_circle_mask(img, size=(96, 96)):
    """円形マスクを適用"""
    img = img.resize(size, Image.Resampling.LANCZOS)
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    
    result = Image.new('RGBA', size, (0, 0, 0, 0))
    img_rgba = img.convert('RGBA')
    result.paste(img_rgba, (0, 0), mask)
    return result

def apply_ghibli_color_tone(img):
    """ジブリ風の温かく柔らかい色調を適用"""
    # 色相を少し暖色寄りに
    img_array = np.array(img, dtype=np.float32)
    
    # 赤みを少し増やして温かみを
    img_array[:, :, 0] = np.clip(img_array[:, :, 0] * 1.08, 0, 255)
    
    # 青みを少し抑える
    img_array[:, :, 2] = np.clip(img_array[:, :, 2] * 0.95, 0, 255)
    
    # 全体的に少し明るく
    img_array = np.clip(img_array * 1.05, 0, 255)
    
    return Image.fromarray(img_array.astype(np.uint8))

def create_watercolor_effect(img):
    """水彩画風の効果を作成"""
    # 複数回のバイラテラルフィルタで水彩画風に
    img_array = np.array(img)
    
    # エッジを保持しながらスムージング
    for _ in range(2):
        img = img.filter(ImageFilter.SMOOTH_MORE)
    
    # 少し色を淡くする
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(0.9)
    
    return img

def generate_enhanced_anime_avatar(image_file, style="anime_pro"):
    """高度なアニメ風アバター生成（本人らしさ保持+誇張表現）"""
    try:
        img = Image.open(image_file)
        img = img.convert('RGB')
        
        # 正方形にクロップ
        width, height = img.size
        min_size = min(width, height)
        left = (width - min_size) / 2
        top = (height - min_size) / 2
        right = (width + min_size) / 2
        bottom = (height + min_size) / 2
        img = img.crop((left, top, right, bottom))
        
        # 処理用サイズにリサイズ
        img = img.resize((128, 128), Image.Resampling.LANCZOS)
        
        if style == "ghibli":
            # **ジブリ風処理**
            
            # 1. 水彩画風のスムージング
            img = create_watercolor_effect(img)
            
            # 2. ジブリらしい温かい色調
            img = apply_ghibli_color_tone(img)
            
            # 3. 軽いポスタリゼーション（ジブリは色数が多めなので緩め）
            img = apply_posterization(img, levels=6)
            
            # 4. 優しいエッジ（ジブリは輪郭線が柔らかい）
            edges = create_anime_edges(img, threshold=50)
            edges_inverted = ImageOps.invert(edges)
            
            # エッジを薄めに適用
            img_array = np.array(img)
            edges_array = np.array(edges_inverted) / 255.0
            
            for i in range(3):
                img_array[:, :, i] = img_array[:, :, i] * (0.7 + 0.3 * edges_array)
            
            img = Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))
            
            # 5. 柔らかさを追加
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # 6. 全体的に明度とコントラストを調整
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.1)
            
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.15)
            
        elif style == "anime_pro":
            # **プロ級アニメ風処理**
            
            # 1. 最初に軽くスムージングで細かいノイズを除去
            img = smooth_anime_texture(img)
            
            # 2. 色彩を鮮やかに強化（アニメらしい色合い）
            img = enhance_anime_colors(img, intensity=1.6)
            
            # 3. ポスタリゼーションでセル画風の色数制限
            img = apply_posterization(img, levels=5)
            
            # 4. エッジ検出と強調
            edges = create_anime_edges(img, threshold=25)
            
            # 5. エッジを元画像に合成
            # エッジを反転させて黒い線にする
            edges_inverted = ImageOps.invert(edges)
            
            # エッジ部分を暗くする効果
            img_array = np.array(img)
            edges_array = np.array(edges_inverted) / 255.0
            
            # エッジ部分を暗くしてアニメの輪郭線効果
            for i in range(3):  # RGB各チャンネル
                img_array[:, :, i] = img_array[:, :, i] * (0.3 + 0.7 * edges_array)
            
            img = Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))
            
            # 6. 最終的な色調整
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)
            
        elif style == "anime_vibrant":
            # **超鮮やかアニメ風**
            
            # 極端に鮮やかな色彩
            img = enhance_anime_colors(img, intensity=2.0)
            
            # 強いポスタリゼーション
            img = apply_posterization(img, levels=4)
            
            # 明度を上げて明るく
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.2)
            
            # エッジ強調
            edges = create_anime_edges(img, threshold=20)
            img = Image.blend(img, ImageOps.colorize(edges, black="#000000", white="#ffffff").convert('RGB'), alpha=0.15)
            
        elif style == "anime_soft":
            # **ソフトアニメ風**
            
            # 優しい色調整
            img = enhance_anime_colors(img, intensity=1.2)
            
            # 軽いポスタリゼーション
            img = apply_posterization(img, levels=7)
            
            # 大きくスムージング
            img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
            
            # 軽いエッジ
            edges = create_anime_edges(img, threshold=40)
            img = Image.blend(img, ImageOps.colorize(edges, black="#000000", white="#ffffff").convert('RGB'), alpha=0.08)
            
        else:
            # デフォルト（従来のカートゥーン風）
            quantized = img.quantize(colors=12).convert('RGB')
            edges = img.filter(ImageFilter.FIND_EDGES)
            edges = ImageOps.autocontrast(edges.convert('L'))
            edges = edges.point(lambda p: 0 if p < 50 else 255)
            edges_rgb = ImageOps.colorize(edges, black="#000000", white="#ffffff")
            img = Image.blend(quantized, edges_rgb.convert('RGB'), alpha=0.1)
        
        # 最終サイズ調整
        img = img.resize((96, 96), Image.Resampling.LANCZOS)
        
        # 円形クロップ
        circular = create_circle_mask(img)
        
        buffered = BytesIO()
        circular.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
        
    except Exception as e:
        st.error(f"アニメアバター生成エラー: {e}")
        return None

# ゲームロジック関数群（変更なし）
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
        
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1]
        
        quiz_list = json.loads(text)
        
        valid_quizzes = []
        for quiz in quiz_list:
            if isinstance(quiz, dict) and all(k in quiz for k in ("question", "answer")):
                if "hint" not in quiz:
                    quiz["hint"] = "がんばって！"
                valid_quizzes.append(quiz)
        
        if len(valid_quizzes) >= num_quizzes:
            return valid_quizzes[:num_quizzes]
        else:
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
    """高度なアニメアバター対応のスマホ完全対応ルーレット"""
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
    
    # 高度なアニメアバター対応ラベル生成
    labels_html = ""
    for i, player in enumerate(players):
        label_angle = i * angle_per_section + angle_per_section / 2
        name = str(player['name']).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        if player.get('avatar_base64'):
            # 高度なアニメアバターがある場合
            labels_html += f"""
            <div class="player-avatar" style="--angle: {label_angle}deg;">
                <img src="data:image/png;base64,{player['avatar_base64']}" alt="{name}" class="avatar-image"/>
                <div class="name-overlay">{name}</div>
            </div>
            """
        else:
            # アバターがない場合（従来通り）
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
        .player-avatar {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: rotate(var(--angle)) translateY(calc(-1 * (min(90vw, 90vh, 480px) * 0.40))) rotate(calc(-1 * var(--angle)));
            transform-origin: center center;
            pointer-events: none;
            text-align: center;
        }}
        .avatar-image {{
            width: clamp(55px, 12vw, 85px);
            height: clamp(55px, 12vw, 85px);
            border-radius: 50%;
            border: 4px solid white;
            object-fit: cover;
            box-shadow: 0 8px 20px rgba(0,0,0,0.6);
            display: block;
            margin: 0 auto 6px auto;
            /* アニメアバター用の追加効果 */
            filter: contrast(1.15) saturate(1.3) brightness(1.05);
        }}
        .name-overlay {{
            background: linear-gradient(135deg, rgba(0,0,0,0.9), rgba(50,50,50,0.9));
            color: white;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: clamp(9px, 2.2vw, 14px);
            font-weight: bold;
            white-space: nowrap;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            border: 2px solid rgba(255,255,255,0.4);
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
            .avatar-image {{
                width: 45px;
                height: 45px;
                border-width: 2px;
            }}
            .name-overlay {{
                font-size: 8px;
                padding: 2px 6px;
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
    """高度なアニメアバター対応のステータス表示"""
    st.markdown("---")
    st.subheader("📊 現在の酔い度")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            if p.get('avatar_base64'):
                st.image(base64.b64decode(p['avatar_base64']), width=50)
            st.write(f"**{i}. {p['name']}**")
        with col2:
            st.progress(p['drunk_degree'] / 100)
        with col3:
            st.write(f"酔い度: {p['drunk_degree']:.1f}%")

# メインアプリケーション
st.title("🍶 AIルーレット飲みゲーム")
st.caption("スマホ対応・口頭クイズ＆高度なアニメアバター機能付き！")

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
        - **🎨 高度なアニメアバター生成**: 誇張していても本人とわかるアニメ風変換
        - **⚖️ 連続当たり救済**: 同じ人が連続で選ばれにくい
        - **⏹️ 途中終了機能**: いつでもゲームを終了可能
        - お酒の強さと好き嫌いに応じて飲み量を調整
        - 15ラウンドのルーレット
        - 突発イベントもあり！
        """)
        
        with st.expander("🎨 高度なアニメアバター機能について", expanded=False):
            st.markdown("""
            **新しい高度なアニメ風アバター生成の特徴:**
            
            **🌿 ジブリ風** (NEW!):
            - 温かく柔らかい色調
            - 水彩画のような優しいタッチ
            - ノスタルジックな雰囲気
            - 自然な肌の質感
            - 優しい輪郭線
            - まるでジブリ映画のキャラクターのような仕上がり
            
            **🌟 アニメプロ版**:
            - 本人の特徴を保持しつつ誇張表現
            - セル画風の色数制限処理
            - アニメらしい強い輪郭線
            - 鮮やかで美しい色彩調整
            - 滑らかなアニメ質感
            
            **✨ 超鮮やかアニメ版**:
            - 極端に鮮やかな色彩
            - より派手で目立つスタイル
            - インパクト重視
            
            **🌸 ソフトアニメ版**:
            - 優しいパステル調
            - ソフトで上品な仕上がり
            - 落ち着いた印象
            
            **特徴:**
            - 外部API不要で即座に生成
            - 本人の特徴を残しつつアニメ風に誇張
            - プライバシー配慮（セッション内のみ保持）
            """)
        
        with st.expander("🌐 リモートプレイの方法", expanded=False):
            st.markdown("""
            **推奨方法: 画面共有**
            
            1. **ゲームマスター**が一人、このアプリを操作
            2. **Zoom/Meet/Discord**などで画面を共有
            3. 参加者は共有画面を見ながら**音声**で参加
            4. 顔写真は事前に送ってもらうか、リモートで撮影指示
            5. アニメアバターで本人確認も楽しい
            6. クイズは口頭で答える → マスターが正解ボタンを押す
            """)
    
    with col2:
        st.markdown("### ⚙️ AI機能状態")
        if GEMINI_API_KEY and AI_AVAILABLE:
            st.success("✅ Gemini AI: 有効")
            st.caption("クイズ自動生成可能")
        else:
            st.info("ℹ️ Gemini AI: 無効")
            st.caption("固定クイズで動作")
        
        st.success("✅ 高度アニメアバター: 有効")
        st.caption("本人らしさ + 誇張表現")
    
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

# プレイヤー入力画面（高度なアニメアバター対応）
elif st.session_state.game_state == 'input_players':
    st.markdown("---")
    st.subheader("👥 参加者情報の入力")
    
    num_players = st.number_input("参加人数（3〜12人）", min_value=3, max_value=12, value=5)
    
    st.markdown("---")
    
    players_temp = []
    
    for i in range(num_players):
        with st.expander(f"プレイヤー {i+1}", expanded=True):
            # 基本情報
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                name = st.text_input("名前", key=f"name_{i}", value=f"プレイヤー{i+1}")
            
            with col2:
                strength = st.slider("お酒の強さ", 1, 5, 3, key=f"strength_{i}")
            
            with col3:
                preference = st.slider("お酒の好き嫌い", 1, 5, 3, key=f"preference_{i}")
            
            with col4:
                cup_type = st.selectbox("基準量", ['おちょこ', 'ジョッキ', 'どちらも'], key=f"cup_{i}")
            
            # 顔写真・高度なアニメアバター設定
            st.markdown("**🎨 顔写真・高度なアニメアバター設定（任意）**")
            
            col_photo1, col_photo2 = st.columns(2)
            
            avatar_base64 = None
            original_base64 = None
            
            with col_photo1:
                uploaded_file = st.file_uploader(
                    "写真を選択", 
                    type=['jpg', 'jpeg', 'png'], 
                    key=f"upload_{i}",
                    help="正方形に近い写真がおすすめです"
                )
                
                if uploaded_file:
                    st.image(uploaded_file, width=80, caption="アップロード写真")
                    original_base64 = image_to_base64(uploaded_file)
            
            with col_photo2:
                captured_photo = st.camera_input(f"📸 {name}の写真を撮る", key=f"camera_{i}")
                
                if captured_photo:
                    st.image(captured_photo, width=80, caption="撮影写真")
                    if not original_base64:  # アップロードがない場合のみ
                        original_base64 = image_to_base64(captured_photo)
            
            # 高度なアニメアバター生成
            source_image = uploaded_file if uploaded_file else captured_photo
            
            if source_image:
                col_style, col_generate = st.columns(2)
                
                with col_style:
                    avatar_style = st.selectbox(
                        "アニメアバタースタイル",
                        ["ghibli", "anime_pro", "anime_vibrant", "anime_soft"],
                        format_func=lambda x: {
                            "ghibli": "🌿 ジブリ風（NEW!）",
                            "anime_pro": "🌟 アニメプロ版（推奨）",
                            "anime_vibrant": "✨ 超鮮やかアニメ版",
                            "anime_soft": "🌸 ソフトアニメ版"
                        }[x],
                        key=f"style_{i}",
                        index=0  # デフォルトをジブリ風に
                    )
                
                with col_generate:
                    if st.button(f"🎨 高度アニメアバター生成", key=f"generate_{i}", use_container_width=True):
                        with st.spinner("高度なアニメアバター生成中..."):
                            avatar_base64 = generate_enhanced_anime_avatar(source_image, avatar_style)
                        
                        if avatar_base64:
                            st.success("高度アニメアバター生成完了！")
                        else:
                            st.error("アバター生成に失敗しました")
                
                # 生成されたアバターと元画像の比較表示
                if avatar_base64 and original_base64:
                    st.markdown("### 🔄 アニメ変換結果")
                    st.markdown('<div class="avatar-comparison">', unsafe_allow_html=True)
                    
                    col_orig, col_arrow, col_avatar = st.columns([2, 1, 2])
                    with col_orig:
                        st.markdown('<div class="avatar-item">', unsafe_allow_html=True)
                        st.image(base64.b64decode(original_base64), width=90, caption="元画像")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col_arrow:
                        st.markdown("### ➡️")
                    
                    with col_avatar:
                        st.markdown('<div class="avatar-item">', unsafe_allow_html=True)
                        st.image(base64.b64decode(avatar_base64), width=90, caption="アニメアバター")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 詳細説明
                    style_descriptions = {
                        "ghibli": "🌿 温かく柔らかい色調と水彩画のような優しいタッチで、まるでジブリ映画のキャラクターのような仕上がり",
                        "anime_pro": "本人の特徴を保持しつつ、セル画風の色数制限と強い輪郭線でアニメらしく誇張",
                        "anime_vibrant": "極端に鮮やかな色彩で派手で目立つインパクト重視のスタイル",
                        "anime_soft": "優しいパステル調でソフトで上品な仕上がり"
                    }
                    st.info(f"✨ {style_descriptions.get(avatar_style, '')}")
            
            players_temp.append({
                'name': name,
                'strength': strength,
                'preference': preference,
                'cup_type': cup_type,
                'total_drunk': 0,
                'drunk_degree': 0,
                'avatar_base64': avatar_base64,
                'original_base64': original_base64
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

# ゲーム中（口頭クイズシステム統合）
elif st.session_state.game_state == 'playing':
    # 途中終了ボタン
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
            
            current_quiz = st.session_state.quiz_list[st.session_state.current_quiz_index]
            st.markdown(f'<div class="quiz-question">第{st.session_state.current_quiz_index + 1}問: {current_quiz["question"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="quiz-hint">💡 ヒント: {current_quiz.get("hint", "がんばって！")}</div>', unsafe_allow_html=True)
            
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
                st.info("残りが2人以下になりました。クイズ終了です。")
                if st.button("📊 結果発表！", use_container_width=True, type="primary"):
                    st.session_state.quiz_phase = 'result'
                    st.rerun()
                
        elif st.session_state.quiz_phase == 'result':
            st.markdown("---")
            st.markdown("## 🎉 クイズ結果発表")
            
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
                    if st.button("🗣️ クイズタイムで一息", use_container_width=True, type="secondary"):
                        num_participants = len(st.session_state.players) - 1
                        if num_participants < 3:
                            st.warning("クイズに参加できる人が少なすぎます。（飲んだ人を除いて3人以上必要）")
                        else:
                            num_quizzes = num_participants - 2
                            st.session_state.quiz_list = generate_ai_quiz_batch(num_quizzes)
                            st.session_state.current_quiz_index = 0
                            
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
        
        # 高度なアニメアバター対応ステータス表示
        if not st.session_state.spinning and st.session_state.quiz_phase == 'none':
            display_status()
    
    else:
        st.session_state.game_state = 'finished'
        st.rerun()

# ゲーム終了画面（高度なアニメアバター対応）
elif st.session_state.game_state == 'finished':
    st.markdown("---")
    st.markdown("# 🎉 ゲーム終了！最終ランキング")
    st.markdown("---")
    
    sorted_players = sorted(st.session_state.players, key=lambda x: x['drunk_degree'], reverse=True)
    
    for i, p in enumerate(sorted_players, 1):
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 2, 2])
            
            with col1:
                medals = ["", "🥇", "🥈", "🥉"]
                medal = medals[i] if i <= 3 else ""
                st.markdown(f"### {medal} {i}位")
            
            with col2:
                if p.get('avatar_base64'):
                    st.image(base64.b64decode(p['avatar_base64']), width=60)
            
            with col3:
                st.markdown(f"**{p['name']}**")
            
            with col4:
                st.progress(p['drunk_degree'] / 100)
            
            with col5:
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
