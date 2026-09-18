# Standard Manage

更新都會有審計log

## `/manage/acct`
表格有以下內容

- 帳號名稱
- 帳號Mail
- 最後一次登入的IP
- 指定 IP
- 帳號權限

## `/manage/acct/update`
更新 UserType 與 指定 IP
指定 IP 必須為 IPv4 格式

## `/manage/board`
顯示所有的 board

表格有以下內容

- Name
- [Board Status](../system#board-type)

## `/manage/board/add`
新增 board

有以下 Field 要設定

- Name (最多 100 字, NotImpl)
- [Status](../system#board-type)
- Start Time
- End Time (必須 > Start Time)
- Account ID List
- Problem ID List

## `/manage/board/update`
更新 board

有以下 Field 要設定

- Name (最多 100 字, NotImpl)
- Status
- Start Time
- End Time (必須 > Start Time)
- Account ID List
- Problem ID List

## `/manage/bulletin`
顯示所有 Bulletin

表格有以下內容

- Title
- Color
- Creator
- Create Timestamp

如果 bulletin 有標記 pin, 會在 title 最前方加上一個 ICON

## `/manage/bulletin/add`
有以下 Field 要設定

- Title (最多 50 字)
- Title Color (CSS) (最多 64 字, NotImpl)
- Is pinned
- Content (Support Markdown 與 LaTex, 最多 2048 字)

如果 Title Color 填入空字串，則使用 `white`

## `/manage/bulletin/update`
有以下 Field 要設定

- Title (最多 50 字)
- Title Color (CSS) (最多 64 字, NotImpl)
- Is pinned
- Content (Support Markdown 與 LaTex, 最多 2048 字)

可以 Preview 內容 (會 Render Markdown 與 LaTex)

## `/manage/pro`
表格有以下內容

- Problem Name
- [Status](../system#problem-status)
- Rechallenge 的按鈕 與 Rechallenge All 的按鈕

Rechallenge 僅 rejudge 狀態為 Not Started 與 Challenging 的 challenges
Rechallenge All 會 rejudge 全部的 challenges，需要系統密碼
上面兩個都會有審計log

## `/manage/pro/add`
有以下 Field 要設定

- Name (最多 64 字)
- [Status](../system#problem-status)
- Add Mode

### Add Mode
- Upload: 上傳檔案，支援 TOJ 格式的題目包
- SetupByUI: 透過 UI 設定題目內容，預設會建立一個空的題目

## `/manage/pro/update`
有以下 Field 要設定

- Name (最多 64 字)
- [Status](../system#problem-status)
- Is Allow Submit
- Tags (只允許 A~Z, a~z, 0~9, ` `, `-`, `_`, `,`, 最多 64 字 NotImpl)

與 [`/manage/pro`](#managepro) 一樣有 Rejudge 與 Rejudge All 的按鈕
可以上傳 TOJ 格式的題目包，會完全覆蓋原有題目內容 (如果上傳錯誤的格式，該題目內容會錯誤而被清空，十分危險)，只要更新成功後，**該題所有的 challenges 的狀態皆會變成 Not Started (方便 Rechallenge)**

## `/manage/pro/updatetestdata`
用來更新題目的測資，測資檔案架構由 [Problem Type](../system#problem-system) 決定
包含以下功能

- Preview Single Testdata File (超過 25 行不會顯示)
- Download Single Testdata File
- Add Single Testdata
- Delete Single Testdata
- Update Single Testdata File
- Update Testdata Tags (目前只支援 system-test)

測資新增與刪除，子任務新增刪除與分數更新，**該題所有的 challenges 的狀態皆會變成 [Not Started](../system#challenge-state) (方便 Rechallenge)**

TODO: 限制總測資大小與數量

## `/manage/pro/updatelimit`
設定題目 [Limit](../system#limit)
包含以下三種

- Time Limit (ms)
- Memory Limit (KiB)
- Output Limit (KiB)

可以設定不同 Compiler 的資源限制，Compiler 會受到題目支援的 Compiler 限制

## `/manage/pro/updatesubtask`
用來更新題目的 [Subtask](../system#subtask)
包含以下功能

- Add Subtask
- Delete Subtask
- Update Subtask Rate
- Update Testdata (testdata 必須要存在)
- Update Subtask Dependencies (id 必須要存在, 且不能有 Cycle)
- Update Subtask Tags (目前只支援 system-test)

## `/manage/pro/updatejudge`
取決於 [Problem Type](../system#problem-system)

## `/manage/pro/filemanager`
用來更新題目的附屬檔案
包含以下功能

- Preview File
- Download File
- Add Single File
- Delete Single File
- Update Single File
- Rename Single File

有哪些 Folder 取決於 [Problem Type](../system#problem-system)
一定會有 [`http/`](../system#http-content--achievement)

TODO: 限制總檔案大小與數量

## `/manage/proclass`
顯示所有的 Official ProClass

表格有以下內容

- Name
- Type (Public / Hidden)

## `/manage/proclass/add`
有以下 Field 要設定

- Name (最多 50 字)
- [Type](../system#proclass-type) (OFFICIAL_PUBLIC / OFFICIAL_HIDDEN)
- Problem ID List
- Description (最多 2048 字，支援 Markdown 與 LaTex)

可以 Preview 內容 (會 Render Markdown 與 LaTex)

## `/manage/proclass/update`
有以下 Field 要設定

- Name (最多 50 字)
- [Type](../system#proclass-type) (OFFICIAL_PUBLIC / OFFICIAL_HIDDEN)
- Problem ID List
- Description (最多 2048 字，支援 Markdown 與 LaTex)

可以 Preview 內容 (會 Render Markdown 與 LaTex)

## `/manage/question`
顯示所有的有問問題的帳號

## `/manage/question/reply`
顯示指定帳號的所有問題
可以回覆問題，回覆後該帳號會在主頁上看到 Get Reply
第一次回覆按鈕會是 Reply，回覆過就會變成 Re Reply
重複回覆會覆蓋之前的訊息
回覆內容最多 1024 字

## `/manage/judge`
顯示所有設定的 judge 與該 judge 執行 Challenge 的數量
當頁面中的 judge 有狀態更新時，會透過 WebSocket 自動更新
disconnect 需要系統密碼
connect 不需要系統密碼

## `/manage/info`
顯示系統資訊，包含以下內容

### Git Information
- Git Branch
- Git Commit Hash

### Database Information
- PostgreSQL Version
- Database Size
- Connected Clients Count
- Run VACUUM ANALYZE 按鈕

### Redis Information
- Redis Version
- Connected Clients Count

### Path and Storage Information
- Installation Path
- Code Folder Path
- Problem Folder Path

### System Configuation
- Site Title
- Base URL
- Port
- Timezone
- Active WebSocket connection count
- Can See Code User

### Python Information
- Python Version
- Executable Path
- Package Dependencies

### OS Information
- System
- Architecture
- System Version
- Uptime
- Service Running Time
- Environment Type (docker-release, docker-dev, installation-script, unknown)

### Disk Usage Information
- Total Size
- Used Size
- Free Size
- Usage Progress Bar

### System Resources
- CPU Cores
- CPU Usage
- Memory Total
- Memory Usage Progress Bar