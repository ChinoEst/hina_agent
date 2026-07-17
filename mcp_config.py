import os

# ---------------------------------------------------------------------------
# 套件版本鎖定
# ---------------------------------------------------------------------------
# npx 預設每次都抓最新版,官方套件哪天改了工具名稱或參數,程式可能無預警壞掉。
# 這裡統一管理版本號:測試過覺得穩定後,把對應版本填進來鎖住;
# 留空字串 "" = 沿用 npx 預設抓最新版(尚未鎖定,不建議長期這樣用,只適合剛裝、還在測試階段)。
# 填法範例:"0.6.2"
MCP_PACKAGE_VERSIONS = {
    "filesystem": "",
    "github": "",
    "brave-search": "",
    "gdrive": "",
    "slack": "",
    "postgres": "",
    "sqlite": "",
    "puppeteer": "",
    "google-maps": "",
}


def _pinned(server_name: str, package: str) -> str:
    """如果 MCP_PACKAGE_VERSIONS 有填版本號,回傳 package@version;沒填就回傳原本的套件名稱(吃最新版)。"""
    version = MCP_PACKAGE_VERSIONS.get(server_name, "")
    return f"{package}@{version}" if version else package


# ---------------------------------------------------------------------------
# MCP Server 設定
# ---------------------------------------------------------------------------
# 每個 server 是一組 stdio 設定,靠 npx 拉起來跑。
# 要停用某個 server,直接註解掉那個 entry 就好,不用動 main.py。
#
# filesystem server 的 sandbox 範圍 = 傳進去的那個目錄(這裡設成專案根目錄),
# agent 能讀寫的檔案範圍就是以這裡為界。
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

MCP_SERVERS = {
    "filesystem": {
        "command": "npx",
        "args": ["-y", _pinned("filesystem", "@modelcontextprotocol/server-filesystem"), PROJECT_ROOT],
        "transport": "stdio",
    },
    "github": {
        "command": "npx",
        "args": ["-y", _pinned("github", "@modelcontextprotocol/server-github")],
        "transport": "stdio",
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
    },

    # 網路搜尋(Brave Search API)。去 https://brave.com/search/api/ 申請免費 key,
    # 放進 .env 的 BRAVE_API_KEY。
    "brave-search": {
        "command": "npx",
        "args": ["-y", _pinned("brave-search", "@modelcontextprotocol/server-brave-search")],
        "transport": "stdio",
        "env": {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")},
    },

    # Google Drive。需要先跑過官方 OAuth 設定流程產生 credentials,
    # 詳見 server 套件說明;GDRIVE_CREDENTIALS_PATH 指向該憑證檔案路徑。
    "gdrive": {
        "command": "npx",
        "args": ["-y", _pinned("gdrive", "@modelcontextprotocol/server-gdrive")],
        "transport": "stdio",
        "env": {"GDRIVE_CREDENTIALS_PATH": os.environ.get("GDRIVE_CREDENTIALS_PATH", "")},
    },

    # Slack。到 Slack App 設定頁建立 Bot Token(xoxb-...)與取得 Team ID,
    # 放進 .env 的 SLACK_BOT_TOKEN / SLACK_TEAM_ID。
    "slack": {
        "command": "npx",
        "args": ["-y", _pinned("slack", "@modelcontextprotocol/server-slack")],
        "transport": "stdio",
        "env": {
            "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN", ""),
            "SLACK_TEAM_ID": os.environ.get("SLACK_TEAM_ID", ""),
        },
    },

    # Postgres 資料庫。
    # ⚠️ 強烈建議 DATABASE_URL 用「唯讀帳號」連線(在資料庫另外建一個帳號,
    # 只 GRANT SELECT,不要共用有寫入權限的主帳號)。這是業界對「agent 直連正式資料庫」
    # 一致的最小權限建議——agent 出錯或被誘導亂下指令時,唯讀帳號能擋掉的傷害是天差地遠的。
    "postgres": {
        "command": "npx",
        "args": ["-y", _pinned("postgres", "@modelcontextprotocol/server-postgres"), os.environ.get("DATABASE_URL", "")],
        "transport": "stdio",
    },

    # SQLite 資料庫,直接指向本機的 .db 檔案路徑(SQLITE_DB_PATH)。
    # 跟上面的 postgres 是二選一,用不到的話可以直接刪掉這個 entry。
    "sqlite": {
        "command": "npx",
        "args": ["-y", _pinned("sqlite", "mcp-server-sqlite-npx"), os.environ.get("SQLITE_DB_PATH", "")],
        "transport": "stdio",
    },

    # 瀏覽器自動化(可操控 headless Chrome:開網頁、點擊、截圖等)。
    # 高風險工具,也是最容易被惡意網頁(prompt injection)誘導亂跳轉、亂點的工具,
    # 所以額外用 PUPPETEER_ALLOWED_DOMAINS 做網域白名單(main.py 會在呼叫前檢查)。
    "puppeteer": {
        "command": "npx",
        "args": ["-y", _pinned("puppeteer", "@modelcontextprotocol/server-puppeteer")],
        "transport": "stdio",
    },

    # Google Maps。去 Google Cloud Console 開通 Maps 相關 API 並取得 key,
    # 放進 .env 的 GOOGLE_MAPS_API_KEY。
    "google-maps": {
        "command": "npx",
        "args": ["-y", _pinned("google-maps", "@modelcontextprotocol/server-google-maps")],
        "transport": "stdio",
        "env": {"GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", "")},
    },
}

# 工具名稱裡只要包含這些關鍵字,一律視為高風險工具、需要使用者確認
# (MCP server 提供的工具名稱不受我們控制,沒辦法像自製工具一樣一個個列進白名單)
MCP_RISKY_KEYWORDS = (
    "write", "edit", "delete", "remove", "move", "rename", "create",
    "push", "commit", "merge", "update", "comment", "fork", "publish",
    "click", "navigate", "fill", "submit", "execute", "query",
)

# ---------------------------------------------------------------------------
# Puppeteer 網域白名單
# ---------------------------------------------------------------------------
# 留空 = 不限制(不建議);填了以後,main.py 會在呼叫 puppeteer 相關工具前檢查
# 網址的網域是否在清單內,不在清單內就直接擋下來、不會真的呼叫該工具。
# 填法範例:["example.com", "github.com"] (子網域如 docs.example.com 也會自動放行)
PUPPETEER_ALLOWED_DOMAINS = [
    # "example.com",
]

# ---------------------------------------------------------------------------
# 啟動前環境變數檢查
# ---------------------------------------------------------------------------
# 目的:啟動時就知道「是缺 key」還是「npx/網路問題」,不用等連線失敗才去猜原因。
MCP_REQUIRED_ENV = {
    "github": ["GITHUB_TOKEN"],
    "brave-search": ["BRAVE_API_KEY"],
    "gdrive": ["GDRIVE_CREDENTIALS_PATH"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    "postgres": ["DATABASE_URL"],
    "sqlite": ["SQLITE_DB_PATH"],
    "google-maps": ["GOOGLE_MAPS_API_KEY"],
}


def check_mcp_env() -> list:
    """
    檢查所有已啟用(出現在 MCP_SERVERS 裡)的 server 是否缺少必要環境變數,
    缺少的話印出警告並回傳警告清單。同時提醒 postgres/puppeteer 的權限注意事項。
    """
    warnings = []
    for server, keys in MCP_REQUIRED_ENV.items():
        if server not in MCP_SERVERS:
            continue
        missing = [k for k in keys if not os.environ.get(k)]
        if missing:
            msg = f"⚠️ MCP server「{server}」缺少環境變數:{', '.join(missing)},啟動時很可能會連線失敗。"
            print(msg)
            warnings.append(msg)

    if "postgres" in MCP_SERVERS:
        print("ℹ️ 提醒:確認 postgres 用的是唯讀帳號(GRANT SELECT ONLY),不要用有寫入權限的主帳號。")

    if "puppeteer" in MCP_SERVERS and not PUPPETEER_ALLOWED_DOMAINS:
        print("⚠️ 提醒:puppeteer 已啟用,但 PUPPETEER_ALLOWED_DOMAINS 是空的,目前沒有網域限制。")

    return warnings