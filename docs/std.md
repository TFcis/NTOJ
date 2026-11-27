# Standard

## `/index`
NavBar 會有以下 Entry

- Icon
- Info
- Board
- Challenges
- ProblemSet
- Contests
- Rank
- Make A Wish
- About
- DevInfo
- Reg | Log

登入以後 Reg | Log 會變成 Leave 與 account name

如果是 User 會有以下 Entry

- Question

如果是 Admin 會有以下 Entry

- Manage

當 User 收到 Reply 後，NavBar 會顯示 Get Reply
當 Admin 有新的 Question 時，NavBar 會顯示 New Question
當有新的 Bulletin 時，NavBar 會顯示 New Bulletin

在 NavBar 下方會顯示 Bulletin List
表格包含以下內容

- Title
- Time
- Author

如果 bulletin 有標記 pin, 會在 title 最前方加上一個 ICON

## `/about`
關於 TOJ 與 NTOJ 歷年開發者，不按照任何順序排序
TOJ 包含以下成員

- allenwhale
- [LFsWang](https://github.com/LFsWang)
- [PZ Read](https://github.com/pzread)
- [Xiplus](https://github.com/Xi-Plus)

NTOJ 包含以下成員

- [tobiichi3227](https://github.com/tobiichi3227)
- [ccccchhhheeenng](https://github.com/ccccchhhheeenng)
- [LifeAdventurer](https://github.com/LifeAdventurer)
- [blameazu](https://github.com/blameazu)
- [Wonderhoi](https://github.com/linushuan)
- [Yushiuan9499](https://github.com/yushiuan9499)
- [Chen Kai Liu](https://github.com/ChenKaiLiuG)

## `/acct/(\d+)`
顯示使用者的個人訊息
包含以下內容

- Name
- Motto
- Total Rate && AC Count && AC Rate (Normal Std)
- Problem Matrix (Only Online Problem)
- Photo && Cover

如果 Photo 沒有設定，預設使用 `https://www.gravatar.com/avatar/{acct_id}?d=identicon&f=y&s=480`

如果是當前使用者與帳號界面使用者相同，可以前往帳號設定
如果是管理員，則可前往修改密碼

Problem Matrix 會根據題目狀態有不同的顏色

## `/acct-config/(\d+)`
有以下 Field 要設定

- Name (最多 27 字)
- Photo && Cover (最多 1110 字, NotImpl)
- Motto (最多 100 字)
- Password (最多 1024 字)

### Login Device
可以檢視登入設備 IP, 時間, UserAgent，並遠端登出該設備
可以登出所有設備，這時候使用者當前頁面會被強制登出

### Password
如果是當前使用者，可以修改密碼，需要輸入當前密碼
如果是管理員，可以修改密碼，不需要輸入當前密碼，會有審計log

## `/acct/proclass/(\d+)`
### Add ProClass
有以下 Field 要設定

- Name (最多 50 字)
- [Type](../system#proclass-type) (USER_PUBLIC / USER_HIDDEN)
- Problem ID List
- Description (最多 2048 字，支援 Markdown 與 LaTex)

可以 Preview 內容 (會 Render Markdown 與 LaTex)

### Update ProClass
有以下 Field 要設定

- Name (最多 50 字)
- [Type](../system#proclass-type) (USER_PUBLIC / USER_HIDDEN)
- Problem ID List
- Description (最多 2048 字，支援 Markdown 與 LaTex)

可以 Preview 內容 (會 Render Markdown 與 LaTex)

## `/board`
顯示該使用者有權限存取的 board

| [Viewer User Type](../system#user-level) | [Board Status](../system#board-type) | 是否顯示 |
| ---------------------------------------- | ------------------------------------ | ------- |
| GUEST                                    | ONLINE                               | Yes |
| GUEST                                    | HIDEEN                               | No  |
| USER                                     | ONLINE                               | Yes |
| USER                                     | HIDEEN                               | No  |
| KERNEL                                   | ONLINE                               | Yes |
| KERNEL                                   | HIDDEN                               | Yes |

依據 board 時間狀態分成三類

- Running
- Future
- Over

## `/board/(\d+)`
如果 board 已經結束了，會顯示 Over，否則會顯示距離結束還有多久時間
如果使用者在 board 中，會 highlight 使用者所在的那一行
每一行會顯示以下內容

- Rank
- User Name
- Score
- Each Problem Solved Status (Score / Count of Attempts)

最後一行會有以下內容

- Each Problem Total Solved Status (Total Score / Total Count of Attempts)

Score 採用 IOI2013 標準計算

## `/bulletin/(\d+)`
顯示

- 公告的內容, 可以使用 Markdown 與 LaTeX
- 公告者
- 公告建立時間

## `/chal`
用來顯示所有 Challenge 的 [Total Result](../system#total-result)，不顯示 Message
一頁顯示 20 個筆 Challenges
當頁面中的 challenges 有狀態更新時，會透過 WebSocket 自動更新
當有新的 challenges 時，最上面會顯示新增幾個 chals (只有 [ProblemStatus](../system#problem-status) 是 ONLINE)

### Filter Options
- Account ID List: 顯示指定使用者的 challenges
- Problem ID List: 顯示指定題目的 challenges
- [state](../system#challenge-state): 可選所有 State
- [Compiler](../system#support-compilers): 可選所有 Compiler
當 state 的 filter 選 Not Started 或是 Challenging 時，下方會出現 rechallenge all 的按鈕，將會 rejudge 該頁面中 chals

所顯示的 challenges 由以下規則指定

| [Viewer User Type](../system#user-level) | [Problem Status](../system#problem-status) | 是否顯示 |
| ----- | -------------- | ------ |
| GUEST | ONLINE | 顯示 |
| GUEST | HIDDEN | 不顯示 |
| GUEST | CONTEST | Permission Denied |
| USER | ONLINE | 顯示 |
| USER | HIDDEN | Permission Denied |
| USER | CONTEST | Permission Denied |
| KERNEL | ONLINE | 顯示 |
| KERNEL | HIDDEN | 顯示 |
| KERNEL | CONTEST | Permission Denied |

## `/chal/(\d+)`
用來顯示指定 Challenge
會顯示 Challenge 的 [Total Result](../system#total-result), [Subtask Results](../system#subtask-results), [Testdata Results](../system#testdata-results), Code
如果 Code 遺失，則會顯示 `ERROR: The code is lost on the server.`
[Total Result](../system#total-result) 的 Message, [Testdata Results](../system#testdata-results), Code 只能在管理員或是該 Challenge 的上傳者查看時顯示，如果是管理員觀看會有審計log

依據 [Message Type](../system#message-type)
- NONE: 不顯示任何 Message
- TEXT: 會對 Message 做跳脫 (Escape)
- HTML: 不會對 Message 做跳脫 (Escape)

管理員會有一個 rechallenge 的按鈕，可以 rejudge 該題目，會有審計log
管理員會有一個 reject, 用來取消該 challenge 的評分，並且可以填寫理由，會有審計log
使用者會有一個 report problem 的按鈕，會將該 challenge 與 report 頁面連結起來

當 challenge 有狀態更新時，會透過 WebSocket 自動更新

## `/code`
用於 chal 看上傳的 Code
能否查看請參考 [`/chal`](#chald)

## `/log`
用來查詢審計 log，僅管理員
可以 Filter By LogType

## `/pack`
用來上傳檔案，僅管理員

## `/pro/(\d+)`
用來顯示題目內容

| [Viewer User Type](../system#user-level) | [Problem Status](../system#problem-status) | 是否顯示 |
| ----- | -------------- | ------ |
| GUEST | ONLINE | 顯示 |
| GUEST | HIDDEN | Permission Denied |
| GUEST | CONTEST | Permission Denied |
| USER | ONLINE | 顯示 |
| USER | HIDDEN | Permission Denied |
| USER | CONTEST | Permission Denied |
| KERNEL | ONLINE | 顯示 |
| KERNEL | HIDDEN | 顯示 |
| KERNEL | CONTEST | Permission Denied |

顯示內容包含

- Problem ID
- Name
- TopCoder
- [Problem Limit Settings](../system#limit)
- [Problem Subtask Settings](../system#subtask), 不包含 Testdata
- Tags

如果使用者不是管理員或沒有 AC 該題目，則 tags 不會顯示
管理員可以修改 tags，會有審計 log

如果題目同時有 html 與 pdf，html 優先於 pdf

## `/pro/(\d+)/(.*)`
用來讀取題目放在 `http/` 下面的[檔案](../system#http-content--achievement)
能否查看請參考 [`/pro/(\d+)`](#prod)

## `/proset`
用來顯示題目，一頁顯示40個

| [Viewer User Type](../system#user-level) | [Problem Status](../system#problem-status) | 是否顯示 |
| ---------------------------------------- | ------------------------------------------ | -------- |
| GUEST                                    | ONLINE                                     | 顯示     |
| GUEST                                    | HIDDEN                                     | 不顯示   |
| GUEST                                    | CONTEST                                    | 不顯示   |
| USER                                     | ONLINE                                     | 顯示     |
| USER                                     | HIDDEN                                     | 不顯示   |
| USER                                     | CONTEST                                    | 不顯示   |
| KERNEL                                   | ONLINE                                     | 顯示     |
| KERNEL                                   | HIDDEN                                     | 顯示     |
| KERNEL                                   | CONTEST                                    | 不顯示   |

每個題目顯示以下內容

- User State (取最好的 [State](../system#challenge-state), 如果沒有則顯示 TODO)
- Problem Name
- TopCoder 的 Photo
- User AC Ratio (User Challenged AC Count / User Challenged Count)
- Challenge AC Ratio (Challenge AC Count / Challenge Count)
- 該題目的 Chal Count(上傳次數) / Chal AC Count(上傳AC次數)
- 該題目的 User Count(上傳人數) / User AC Count(AC人數)
- Tags (如果使用者不是管理員或沒有 AC 該題目，則 tags 不會顯示)

### Filter Options
- ProClass
- Search By Name
- Search By Tags
- Show Only Problme Status = Online (只有在管理員時出現)

如果使用者不是管理員，則 Search By Tags 只搜索有 AC 的題目的 Tags

### [Sort](./system#rate-system)
- Challenge AC Ratio (Challenge AC Count / Challenge Count)
- User AC Ratio (User Challenged AC Count / User Challenged Count)
- Challenge Count
- Challenge AC Count
- User Challenged Count
- User Challenged AC Count

如果選擇 ProClass 後，會出現 Progress Bar 顯示該 ProClass 的完成度

### ProClass

| [Viewer User Type](../system#user-level) | [ProClass Type](../system#proclass-type) | 顯示分類 |
| ---------------------------------------- | ---------------------------------------- | -------- |
| GUEST                                    | OFFICIAL_PUBLIC                          | Official |
| GUEST                                    | OFFICIAL_HIDDEN                          | 不顯示 |
| GUEST                                    | USER_PUBLIC                              | User Shared |
| GUEST                                    | USER_HIDDEN                              | 不顯示 |
| USER                                     | OFFICIAL_PUBLIC                          | Official |
| USER                                     | OFFICIAL_HIDDEN                          | 不顯示 |
| USER                                     | USER_PUBLIC                              | User Shared |
| USER                                     | USER_HIDDEN                              | 不顯示 |
| USER (Self)                              | USER_HIDDEN                              | My Problem Class |
| KERNEL                                   | OFFICIAL_PUBLIC                          | Official |
| KERNEL                                   | OFFICIAL_HIDDEN                          | Official |
| KERNEL                                   | USER_PUBLIC                              | User Shared |
| KERNEL                                   | USER_HIDDEN                              | 不顯示 |
| KERNEL (Self)                            | USER_HIDDEN                              | My Problem Class |

顯示以下四個分類

- Official (OFFICIAL_PUBLIC, 如果是使用者 UserType = KERNEL 則包含 OFFICIAL_HIDDEN)
- User Shared (USER_PUBLIC)
- My Collected (使用者本人收藏的 ProClass)
- My Problem Class (使用者本人建立的 ProClass, 包含 USER_PUBLIC 與 USER_HIDDEN)

顯示以下內容

- ProClass Name
- Progress (AC Problme Count / Total Problme Count)
- Creator Name (如果 ProClass 是 OFFICIAL_PUBLIC 或 OFFICIAL_HIDDEN，則顯示 Official)
- Collect Button
- Goto~

## `/question`
用來向管理員發問題，僅使用者可以使用
如果問題超過 10 個，較早問的問題將被刪除
當管理員回覆問題後，在主頁上會顯示 Get Reply
發問內容最多 1024 字

## `/rank/(\d+)`
顯示該題所有上傳者排名，一頁顯示 20 個
Access Permission 與 [`/pro/(\d+)`](#prod) 相同
顯示內容為

- Submitter Name
- Rate ([Total Result](../system#total-result))
- Runtime ([Total Result](../system#total-result))
- Memory ([Total Result](../system#total-result))
- Timestamp ([Total Result](../system#total-result))

排序標準為

- Rate ([Total Result](../system#total-result)) 降序
- Runtime ([Total Result](../system#total-result)) 升序
- Memory ([Total Result](../system#total-result)) 升序
- Timestamp ([Total Result](../system#total-result)) 升序
只會計算使用者最好的一次 chal

## `/report`
用來回報問題
使用 question 的 API，因此會在 question 頁面中出現

## `/sign`
### 登入帳號
帳號不存在或是密碼錯誤時顯示無法登入
如果帳號有指定登入 IP，且當前 IP 不在允許範圍內，則無法登入

### 註冊新帳號
有以下 Field 要設定

- Email (最多 1024 字, 改成 264 字, NotImpl)
- Password (最多 1024 字)
- Name (最多 27 字)

Email 在系統中需要唯一不能重複
重複將無法註冊

## `/submit/(\d+)`
用於上傳題目，題目上傳權限與 `/pro/(\d+)` 相同
會顯示本題可使用的語言選項，並預設使用 last_compiler
如果該題目的 Limit 有設定特定 Compiler 的資源限制，則本次 Submit 使用該資源限制

無法上傳情況 (檢查順序按照下面)

- 沒有可用的 judge
- 上傳內容為空
- 上傳內容長度大於 3227
- 不允許的 [Compiler](../system#support-compilers)
- 上傳冷卻時間計時尚未結束 (30秒)

上傳成功後，會更新上傳冷卻時間與[使用者的 Last Compiler](../system#user-system)

## `/users`
顯示所有使用者的排名，一頁顯示 20 個
顯示內容為

- Name
- Photo
- AC Problme Count
- AC Ratio (AC Problme Challenge Count / Total Problem Challenge Count)

排序標準為

- Total Rate 降序 
- AC Problme Count 降序
- AC Ratio 降序
