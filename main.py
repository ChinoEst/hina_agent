import sys
import os
import json
import base64
import subprocess
import random
import re
from PIL import Image, ImageGrab
from ddgs import DDGS
from playwright.sync_api import sync_playwright



from dotenv import load_dotenv
load_dotenv()

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QMessageBox, QComboBox,
    QFileDialog
)
from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QColor, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer

from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage



"""
Attribute:
"""

AVAILABLE_MODELS = ["gemini-3.5-flash","gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"]
CURRENT_MODEL = AVAILABLE_MODELS[0] 
SCHEDULE_FILE = "schedule.json"
SCREENSHOT_TEMP_PATH = os.path.join("tmp", "screenshot_temp.png")   
USER_PROFILE_FILE = "user_profile.json"   
AVATAR_DIR = "avatar"
AVATAR_PATH = os.path.join(AVATAR_DIR, "avatar.png")   
BUTTON_SIZE = 72
TAIL_WIDTH = 24
TAIL_HEIGHT = 16
MAX_WIDTH = 1280


GREETING_MESSAGES = [
    "老師，早上好",
]

FAREWELL_MESSAGES = [
    "今天辛苦老師了，晚安",
]


PERSONA_PROMPT_FILE = "persona_prompt.txt"

def load_persona_prompt() -> str:
    try:
        with open(PERSONA_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "你是使用者的專屬 AI小助理。"

PERSONA_SYSTEM_PROMPT = load_persona_prompt()

#emotion_image
EMOTION_AVATARS = {
    "happy": "avatar_happy.png",
    "thinking": "avatar_thinking.png",
    "sad": "avatar_sad.png",
    "neutral": "avatar.png",
}

EMOTION_TAG_PATTERN = re.compile(r"^\s*\[emotion:(\w+)\]\s*")


def extract_emotion(content: str):
    match = EMOTION_TAG_PATTERN.match(content)
    if match:
        emotion = match.group(1).lower()
        clean_text = EMOTION_TAG_PATTERN.sub("", content, count=1)
        return emotion, clean_text
    return "neutral", content


def normalize_content(content) -> str:
    """
    response of message.content to str
    """

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def load_user_profile() -> str:
    #load user_profile, each time add into input
    if not os.path.exists(USER_PROFILE_FILE):
        return ""
    try:
        with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except Exception:
        return ""
    if not profile:
        return ""
    lines = [f"- {k}: {v}" for k, v in profile.items()]
    return "\n\n【已知的使用者資訊,請自然運用在對話中,不要生硬複誦或每句話都提起】\n" + "\n".join(lines)




"""
tool: 
"""


#for test code correct or not
@tool
# 這個工具用於執行 Python 程式碼並回傳輸出結果
def run_python(code: str) -> str:
    
    try:
        result = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=15)
        return result.stdout if result.returncode == 0 else f"執行錯誤:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "執行逾時(超過 15 秒)。"
    except Exception as e:
        return f"發生例外:{e}"


@tool
# 這個工具用於透過 DuckDuckGo 搜尋並回傳摘要結果
def web_search(query: str) -> str:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"- {r['title']}: {r['body'][:150]}...\n  來源: {r['href']}")
        return "\n".join(results) if results else "沒有找到相關搜尋結果。"
    except Exception as e:
        return f"搜尋失敗:{e}"


@tool
# 這個工具用於讀取文字檔案內容，最多回傳 3000 字元
def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content[:3000]
    except Exception as e:
        return f"讀取失敗:{e}"


@tool
# 這個工具用於寫入文字檔案內容
def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已寫入檔案:{path}"
    except Exception as e:
        return f"寫入失敗:{e}"


@tool
# 這個工具用於列出指定資料夾內容
def list_directory(path: str = ".") -> str:
    try:
        items = os.listdir(path)
        return "\n".join(items) if items else "(空資料夾)"
    except Exception as e:
        return f"讀取資料夾失敗:{e}"


@tool
# 這個工具用於新增行程並儲存到排程檔案
def schedule_add(title: str, date: str, time: str, note: str = "") -> str:
    try:
        items = []
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        items.append({"title": title, "date": date, "time": time, "note": note})
        items.sort(key=lambda x: (x["date"], x["time"]))
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return f"已新增行程:{date} {time} - {title}"
    except Exception as e:
        return f"新增行程失敗:{e}"


@tool
# 這個工具用於列出所有儲存的行程
def schedule_list() -> str:
    try:
        if not os.path.exists(SCHEDULE_FILE):
            return "目前沒有任何行程。"
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
        if not items:
            return "目前沒有任何行程。"
        return "\n".join(f"- {i['date']} {i['time']}  {i['title']}" for i in items)
    except Exception as e:
        return f"讀取行程失敗:{e}"


@tool
# 這個工具用於記住使用者資訊並儲存到個人設定檔
def remember_user_fact(key: str, value: str) -> str:
    try:
        profile = {}
        if os.path.exists(USER_PROFILE_FILE):
            with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
                profile = json.load(f)
        profile[key] = value
        with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return f"已記住:{key} = {value}"
    except Exception as e:
        return f"記憶失敗:{e}"


@tool
# 這個工具用於從個人設定檔中刪除已記住的資訊
def forget_user_fact(key: str) -> str:
    try:
        if not os.path.exists(USER_PROFILE_FILE):
            return "目前沒有任何已記住的資訊。"
        with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
        if key in profile:
            del profile[key]
            with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            return f"已忘記:{key}"
        return f"沒有找到「{key}」這項資訊。"
    except Exception as e:
        return f"刪除失敗:{e}"


@tool
# 這個工具用於讀取網頁並截圖後分析畫面內容
def read_webpage(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, timeout=20000, wait_until="networkidle")
            screenshot_bytes = page.screenshot(full_page=True)
            browser.close()

        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        """
        use same type but another mode to  analyze image and as input to origin model
        """
        vision_llm = ChatGoogleGenerativeAI(model=CURRENT_MODEL)
        vision_message = HumanMessage(content=[
            {"type": "text", "text": "這是一張網頁截圖,請詳細描述畫面上的標題、重點文字與整體內容大意。"},
            {"type": "image_url", "image_url": f"data:image/png;base64,{b64_image}"},
        ])
        response = vision_llm.invoke([vision_message])
        return f"網址:{url}\n畫面內容摘要:\n{response.content}"
    except Exception as e:
        return f"讀取網頁截圖失敗:{e}"


@tool
# 這個工具用於擷取螢幕截圖並回傳分析結果
def take_screenshot() -> str:
    try:
        image = ImageGrab.grab()

        #compression
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            new_size = (MAX_WIDTH, int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        image.save(SCREENSHOT_TEMP_PATH)
        with open(SCREENSHOT_TEMP_PATH, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        
        vision_llm = ChatGoogleGenerativeAI(model=CURRENT_MODEL)
        vision_message = HumanMessage(content=[
            {"type": "text", "text": "這是使用者目前的螢幕截圖,請詳細描述畫面上的視窗、文字與整體內容大意。"},
            {"type": "image_url", "image_url": f"data:image/png;base64,{b64_image}"},
        ])
        response = vision_llm.invoke([vision_message])
        return f"螢幕截圖內容摘要:\n{normalize_content(response.content)}"
    except Exception as e:
        return f"截圖失敗:{e}"


RISKY_TOOLS = {"run_python", "write_file", "schedule_add", "remember_user_fact", "forget_user_fact", "take_screenshot"}
ALL_TOOLS = [
    run_python, web_search, read_file, write_file, list_directory,
    schedule_add, schedule_list, remember_user_fact, forget_user_fact,
    read_webpage, take_screenshot,
]


def build_agent(model_name: str, memory: MemorySaver):
    llm = ChatGoogleGenerativeAI(model=model_name)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def call_model(state: MessagesState):
        system_text = PERSONA_SYSTEM_PROMPT + load_user_profile()
        messages = [("system", system_text)] + state["messages"]
        return {"messages": [llm_with_tools.invoke(messages)]}

    #build
    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(ALL_TOOLS))

    #active:  
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=memory, interrupt_before=["tools"])


def is_quota_error(err: Exception) -> bool:
    msg = str(err)
    return "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower()


"""
backround thread
main thread for UI, subthread for others(AI agent)
"""

class AgentWorker(QThread):
    finished_signal = pyqtSignal(str)
    need_confirm_signal = pyqtSignal(str, str)
    error_signal = pyqtSignal(str)
    quota_error_signal = pyqtSignal(str)

    def __init__(self, agent_app, config, user_input=None, resume=False, image_path=None):
        super().__init__()
        self.agent_app = agent_app
        self.config = config
        self.user_input = user_input
        self.resume = resume
        self.image_path = image_path

    def _build_human_message(self):
        
        if not self.image_path:
            return ("user", self.user_input)

        with open(self.image_path, "rb") as f:
            image_bytes = f.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        ext = os.path.splitext(self.image_path)[1].lower().lstrip(".") or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext

        content = [{"type": "text", "text": self.user_input or "請看看這張圖片。"}]
        content.append({"type": "image_url", "image_url": f"data:image/{mime};base64,{b64_image}"})
        return HumanMessage(content=content)

    #when worker.start()
    def run(self):
        try:
            if not self.resume:
                human_message = self._build_human_message()
                result = self.agent_app.invoke({"messages": [human_message]}, config=self.config)
            else:
                result = self.agent_app.invoke(None, config=self.config)

            snapshot = self.agent_app.get_state(self.config)
            if snapshot.next:
                last_msg = snapshot.values["messages"][-1]
                tool_call = last_msg.tool_calls[0]
                tool_name = tool_call["name"]
                if tool_name in RISKY_TOOLS:
                    self.need_confirm_signal.emit(tool_name, str(tool_call["args"]))
                else:
                    auto_result = self.agent_app.invoke(None, config=self.config)
                    self.finished_signal.emit(normalize_content(auto_result["messages"][-1].content))
            else:
                self.finished_signal.emit(normalize_content(result["messages"][-1].content))
        except Exception as e:
            if is_quota_error(e):
                self.quota_error_signal.emit(str(e))
            else:
                self.error_signal.emit(str(e))


#button
class FloatingButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag_pos = None
        self._pixmap = self._load_avatar()

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - BUTTON_SIZE - 30, screen.height() - BUTTON_SIZE - 60)

    def _load_avatar(self, path=None):
        target = path or AVATAR_PATH
        if os.path.exists(target):
            pix = QPixmap(target)
            return pix.scaled(BUTTON_SIZE, BUTTON_SIZE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        return None

    def set_avatar(self, path: str):
        new_pixmap = self._load_avatar(path)
        if new_pixmap is not None:
            self._pixmap = new_pixmap
        else:
            self._pixmap = self._load_avatar(AVATAR_PATH)
        self.update()  # call paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, BUTTON_SIZE, BUTTON_SIZE)
        painter.setClipPath(path)

        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            painter.fillRect(0, 0, BUTTON_SIZE, BUTTON_SIZE, QColor("#6C63FF"))
            painter.setPen(Qt.white)
            painter.setFont(QFont("Microsoft JhengHei", 20, QFont.Bold))
            painter.drawText(0, 0, BUTTON_SIZE, BUTTON_SIZE, Qt.AlignCenter, "AI")

        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawEllipse(1, 1, BUTTON_SIZE - 2, BUTTON_SIZE - 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            #use offset to decide click or mmousemoving
            self._drag_pos = event.globalPos() - self.pos()
            self._moved = False

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            self._moved = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not getattr(self, "_moved", False):
                self.clicked.emit()
            self._drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #6C63FF;
                color: white;
            }
        """)

        close_action = QAction("關閉程式", self)
        close_action.triggered.connect(self._on_close_requested)
        menu.addAction(close_action)

        menu.exec_(event.globalPos())

    def _on_close_requested(self):
        reply = QMessageBox.question(
            self, "確認關閉",
            "確定要關閉 AI 小助手嗎?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "再見", random.choice(FAREWELL_MESSAGES))
            QApplication.instance().quit()


#chat
class ChatBubblePanel(QWidget):
    def __init__(self, anchor_button: FloatingButton):
        super().__init__()
        self.anchor_button = anchor_button
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(460, 620 + TAIL_HEIGHT) 

        self.memory = MemorySaver()
        self.current_model = AVAILABLE_MODELS[0]
        self.agent_app = build_agent(self.current_model, self.memory)
        self.config = {"configurable": {"thread_id": "floating-session-1"}}
        self.worker = None
        self.pending_image_path = None  

        self._build_ui()
        self.add_bubble("Agent", random.choice(GREETING_MESSAGES), is_user=False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        body_height = self.height() - TAIL_HEIGHT

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), body_height, 18, 18)

        
        tail_center_x = self.width() - 50
        tail = QPainterPath()
        tail.moveTo(tail_center_x - TAIL_WIDTH / 2, body_height)
        tail.lineTo(tail_center_x, body_height + TAIL_HEIGHT)
        tail.lineTo(tail_center_x + TAIL_WIDTH / 2, body_height)
        tail.closeSubpath()

        full_path = path.united(tail)

        painter.fillPath(full_path, 255, 240, 245, 235)
        painter.setPen(QColor(0, 0, 0, 40))
        painter.drawPath(full_path)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, TAIL_HEIGHT)  

        container = QWidget()
        container.setObjectName("bubbleContainer")
        container.setStyleSheet("""
            #bubbleContainer {
                background: transparent;
            }
        """)
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 12)

        top_row = QHBoxLayout()
        title = QLabel("今日的值日生")
        title.setStyleSheet("font-weight: bold; font-size: 17px;")
        top_row.addWidget(title)
        top_row.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        top_row.addWidget(self.model_combo)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("border: none; font-weight: bold;")
        close_btn.clicked.connect(self.hide)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            QTextEdit {
                border: none;
                background: transparent;
                font-size: 16px;
            }
        """)
        layout.addWidget(self.chat_area)

        self.status_label = QLabel("就緒")
        self.status_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self.status_label)

        # 附加圖片的預覽列,平常隱藏,選好圖片後才顯示檔名跟一個移除按鈕
        self.image_preview_row = QHBoxLayout()
        self.image_preview_label = QLabel("")
        self.image_preview_label.setStyleSheet("color: #6C63FF; font-size: 11px;")
        self.image_remove_btn = QPushButton("移除圖片")
        self.image_remove_btn.setStyleSheet("font-size: 11px; border: none; color: gray;")
        self.image_remove_btn.clicked.connect(self.on_remove_image)
        self.image_preview_row.addWidget(self.image_preview_label)
        self.image_preview_row.addWidget(self.image_remove_btn)
        self.image_preview_row.addStretch()
        self._set_image_preview_visible(False)
        layout.addLayout(self.image_preview_row)

        input_row = QHBoxLayout()

        attach_btn = QPushButton("📎")
        attach_btn.setFixedSize(32, 32)
        attach_btn.setStyleSheet("border-radius: 16px; background-color: #eee; font-weight: bold;")
        attach_btn.setToolTip("附加圖片")
        attach_btn.clicked.connect(self.on_attach_image)
        input_row.addWidget(attach_btn)

        screenshot_btn = QPushButton("📷")
        screenshot_btn.setFixedSize(32, 32)
        screenshot_btn.setStyleSheet("border-radius: 16px; background-color: #eee; font-weight: bold;")
        screenshot_btn.setToolTip("擷取螢幕畫面")
        screenshot_btn.clicked.connect(self.on_take_screenshot)
        input_row.addWidget(screenshot_btn)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("輸入訊息…")
        self.input_box.returnPressed.connect(self.on_send)
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 14px;
                padding: 8px 12px;
                font-size: 15px;
            }
        """)
        input_row.addWidget(self.input_box)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(32, 32)
        send_btn.setStyleSheet("border-radius: 16px; background-color: #6C63FF; color: white; font-weight: bold;")
        send_btn.clicked.connect(self.on_send)
        input_row.addWidget(send_btn)

        layout.addLayout(input_row)

    def _set_image_preview_visible(self, visible: bool):
        self.image_preview_label.setVisible(visible)
        self.image_remove_btn.setVisible(visible)

    def on_attach_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇要附加的圖片", "", "圖片檔案 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.pending_image_path = path
            self.image_preview_label.setText(f"🖼 已附加:{os.path.basename(path)}")
            self._set_image_preview_visible(True)

    def on_remove_image(self):
        self.pending_image_path = None
        self.image_preview_label.setText("")
        self._set_image_preview_visible(False)

    def on_take_screenshot(self):
        
        self.hide()
        QTimer.singleShot(300, self._capture_screen_after_hide)

    def _capture_screen_after_hide(self):
        try:
            image = ImageGrab.grab()
            image.save(SCREENSHOT_TEMP_PATH)
            self.pending_image_path = SCREENSHOT_TEMP_PATH
            self.image_preview_label.setText("🖼 已附加:螢幕截圖")
            self._set_image_preview_visible(True)
        except Exception as e:
            QMessageBox.warning(self, "截圖失敗", f"擷取螢幕畫面時發生錯誤:{e}")
        finally:
            self.show_near_button()

    def add_bubble(self, who: str, text: str, is_user: bool):
        color = "#A0AAFF" if is_user else "#f7bee2"
        text_color = "white" if is_user else "black"
        align = "right" if is_user else "left"
        html = f"""
        <div style="text-align:{align}; margin: 6px 0;">
            <span style="
                background-color:{color};
                color:{text_color};
                padding:8px 12px;
                border-radius:14px;
                display:inline-block;
                max-width:75%;
                font-size:16px;">
                {text}
            </span>
        </div>
        """
        self.chat_area.append(html)

    def set_busy(self, busy: bool, status: str = ""):
        self.input_box.setEnabled(not busy)
        self.status_label.setText(status if status else ("處理中…" if busy else "就緒"))

    def on_model_changed(self, model_name: str):
        global CURRENT_MODEL
        CURRENT_MODEL = model_name
        self.current_model = model_name
        self.agent_app = build_agent(model_name, self.memory)
        self.add_bubble("系統", f"已切換模型為 {model_name}", is_user=False)

    def on_send(self):
        text = self.input_box.text().strip()
        image_path = self.pending_image_path
        if not text and not image_path:
            return

        bubble_text = text if text else "(僅附加圖片)"
        if image_path:
            bubble_text += f"<br><span style='font-size:11px; opacity:0.8;'>🖼 {os.path.basename(image_path)}</span>"
        self.add_bubble("你", bubble_text, is_user=True)

        self.input_box.clear()
        self.on_remove_image()  # 送出後清空附加圖片預覽,避免下一則訊息重複帶到舊圖
        self.set_busy(True, "思考中…")

        self.worker = AgentWorker(self.agent_app, self.config, user_input=text, image_path=image_path)
        self._connect_worker()
        self.worker.start()

    def _connect_worker(self):
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.need_confirm_signal.connect(self.on_need_confirm)
        self.worker.error_signal.connect(self.on_error)
        self.worker.quota_error_signal.connect(self.on_quota_error)

    def on_finished(self, content: str):
        emotion, clean_text = extract_emotion(content)
        self.add_bubble("Agent", clean_text, is_user=False)
        self.anchor_button.set_avatar(os.path.join(AVATAR_DIR, EMOTION_AVATARS.get(emotion, "avatar.png")))
        self.set_busy(False)

    def on_error(self, msg: str):
        self.add_bubble("系統", f"發生錯誤:{msg}", is_user=False)
        self.set_busy(False)

    def on_quota_error(self, msg: str):
        self.add_bubble("系統", f"⚠️ 模型「{self.current_model}」已達額度上限,請切換其他模型。", is_user=False)
        self.set_busy(False, "額度已滿,請更換模型")

    def on_need_confirm(self, tool_name: str, tool_args: str):
        self.set_busy(True, "等待確認…")
        reply = QMessageBox.question(
            self, "需要確認",
            f"Agent 想要呼叫工具:\n\n工具:{tool_name}\n參數:{tool_args}\n\n是否允許執行?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.add_bubble("系統", f"已允許執行 {tool_name}", is_user=False)
            self.worker = AgentWorker(self.agent_app, self.config, resume=True)
            self._connect_worker()
            self.worker.start()
        else:
            self.add_bubble("系統", f"已拒絕執行 {tool_name}", is_user=False)
            self.set_busy(False)

    def show_near_button(self):
        btn_pos = self.anchor_button.pos()
        x = btn_pos.x() - self.width() + BUTTON_SIZE
        y = btn_pos.y() - self.height() - 10
        self.move(max(0, x), max(0, y))
        self.show()
        self.raise_()
        self.activateWindow()


# ---------------------------------------------------------------------------
# 進入點
# ---------------------------------------------------------------------------

def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("錯誤:找不到 GOOGLE_API_KEY,請確認 .env 檔案設定正確。")
        sys.exit(1)

    app = QApplication(sys.argv)
    #close chat can*t close all program
    app.setQuitOnLastWindowClosed(False) 

    button = FloatingButton()
    panel = ChatBubblePanel(button)

    def on_button_clicked():
        if panel.isVisible():
            panel.hide()
        else:
            panel.show_near_button()

    button.clicked.connect(on_button_clicked)
    button.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()