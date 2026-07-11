# Hina Agent

Sorasaki Hina, a character from Blue Archive, is my waifu — I'd like to have her take on the role of my AI agent persona, powered by Gemini.

一個懸浮在桌面右下角的 AI 小助手,點擊頭像即可彈出聊天面板互動。主要使用 **PyQt5** 打造桌面 GUI,並透過 **LangChain / LangGraph** 串接 Gemini 打造具備工具呼叫能力的 Agent。

## 環境建置

**1. 安裝套件**

```bash
pip install -r requirements.txt
```

**2. 設定 Google API Key**

在專案根目錄建立 `.env` 檔案(不會上傳到 GitHub),內容:

```
GOOGLE_API_KEY=你的Key
```

**3. 準備頭像圖片(選用)**

在專案根目錄建立 `avatar/` 資料夾,放入以下圖片(沒有的話會自動使用預設圖示):

```
avatar/
├── avatar.png            # 預設頭像
├── avatar_happy.png       # 開心表情(選用)
├── avatar_thinking.png    # 思考表情(選用)
└── avatar_sad.png         # 難過表情(選用)
```

**4. 自訂角色人設(選用)**

在專案根目錄建立 `persona_prompt.txt`,寫入你想要的角色人設 prompt。沒有這個檔案時會使用預設的保底人設文字。

**5. 執行**

```bash
python main.py
```

`tmp/`(截圖暫存)、`schedule.json`(行程)、`user_profile.json`(使用者記憶)這些檔案/資料夾會在執行時自動建立,不需手動準備。

## 圖示製作

`toico.py` 是把 `avatar.png` 轉成打包執行檔用的 `.ico` 圖示的小工具,執行後可得到 `cover.ico`,供 PyInstaller 打包時的 `--icon` 參數使用。
