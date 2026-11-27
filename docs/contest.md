# Contest


## `/index`
Contest 模式下的NavBar 會有以下 Entry

- Icon
- Info
- ProblemSet
- Challenges
- Scoreboard

如果是 Contest User 會有以下 Entry

- Q & A

如果是 Contest Admin 會有以下 Entry

- Manage

當 User 收到 Reply 後，NavBar 會在 Q&A 上面顯示紅點
當 Admin 公告 Announcement 後，User 的 NavBar 上 Q&A 會顯示紅點
當 Admin 有新的 Question 時，NavBar 上的 Mange 會顯示紅點

## `/contests`
列出所有比賽
包含以下內容

- Title
- Start Time
- End Time
- Time Length
- Contest Type
- Is Public Scoreboard

依據比賽時間狀態分成四類
- Active (比賽進行中)
- Upcoming (比賽還沒開始)
- Recent (比賽已經結束)
- Permanent (永久比賽)

## `/contests/\d+` && `/contests/\d+/info`
顯示 Contest Info
包含以下內容

- Title
- Start Time
- End Time
- Registration Deadline
- Registration Mode
- User Registertion Status
- Time Length
- Contest Type
- Is Public Scoreboard
- Contest Description (Support Markdown and LaTex)

Contest Description 分為

- 賽前
- 賽中
- 賽後

## `/contests/\d+/chal`
Contest標準

用來顯示比賽所有 challenge 的 Total Result，不顯示 Response
一頁顯示 20 個筆 Challenges
當頁面中的 challenges 有狀態更新時，會透過 WebSocket 自動更新
當有新的 challenges 時，最上面會顯示新增幾個 chals (只有 ProblemStatus 是 [ONLINE](../system#problem-status) 或是 [CONTEST](../system#problem-status))

### Filter Options

- Problem ID List: 顯示指定使用者的 challenges
- Account ID List: 顯示指定題目的 challenges
- [state](../system#challenge-state): 可選所有 State
- [Compiler](../system#support-compilers): 可選所有 Compiler
當 state 的 filter 選 Not Started 或是 Challenging 時，下方會出現 rechallenge all 的按鈕，將會 rejudge 該頁面中 chals

NotImpl
所顯示的 challenges 由以下規則指定

| Viewer User Type | Challenge Submitter User Type | Contest Running Status | 是否顯示 |
| ---------------- | ----------------------------- | ---------------------- | -------- |
| Not Member       | Contest User                  | Not Start              | 不存在這種情況 |
| Not Member       | Contest User                  | Running                | 依照 Public Scoreboard 決定 |
| Not Member       | Contest User                  | Ended                  | 依照 Public Scoreboard 決定 |
| Not Member       | Contest Admin                 | Not Start              | Permission Denied |
| Not Member       | Contest Admin                 | Running                | Permission Denied |
| Not Member       | Contest Admin                 | Ended                  | Permission Denied |
| Contest User     | Self                          | Not Start              | 不存在這種情況 |
| Contest User     | Self                          | Running                | 顯示 |
| Contest User     | Self                          | Ended                  | 顯示 |
| Contest User     | Other Contest User            | Not Start              | 不存在這種情況 |
| Contest User     | Other Contest User            | Running                | 依照 Public Scoreboard 決定 |
| Contest User     | Other Contest User            | Ended                  | 依照 Public Scoreboard 決定 |
| Contest User     | Contest Admin                 | ANY                    | Permission Denied |
| Contest Admin    | Contest User                  | Not Start              | 不存在這種情況 |
| Contest Admin    | Contest User                  | Running                | 顯示 |
| Contest Admin    | Contest User                  | Ended                  | 顯示 |
| Contest Admin    | Contest Admin                 | ANY                    | 顯示 |

## `/contests/\d+/chal/(\d+)`
顯示比賽的 Challenge
規則用 [`/contests/\d+/chal`](#contestsdchal)

如果 Enable System Test
Subtask Results 不會顯示帶有 `system-test` tag 的 Subtask
Testdata Results 不會顯示帶有 `system-test` tag 的 Testdata

Contest Admin 不受此影響
也就是說，Contest Admin 查看 Contest User 的 Challenge 時，會看到 [State 為 Skipped](../system#challenge-state) 的 [Testdata Result](../system#subtask-results) 與 [Subtask Result](../system#subtask-results)

[Total Result](../system#total-result) 的 Message, [Testdata Results](../system#testdata-results), Code 只能在管理員或是該 Challenge 的上傳者查看時顯示，如果是管理員觀看會有審計log
如果 Code 遺失，則會顯示 `ERROR: The code is lost on the server.`

依據 [Message Type](../system#message-type)
- NONE: 不顯示任何 Message
- TEXT: 會對 Message 做跳脫 (Escape)
- HTML: 不會對 Message 做跳脫 (Escape)

按照 Contest 的 [Challenge Style](#challenge-style) 顯示 [Total Result](../system#total-result), [Subtask Results](../system#subtask-results), [Testdata Results](../system#testdata-results)
Contest Admin 永遠使用 [Full Challenge Style](#full)
### Challenge Style
#### Full
與 `/chal/(\d+)` 相同

#### Testdata [State](../system#challenge-state) Count
不顯示 [Testdata Results](../system#testdata-results)
只對所有 [Testdata Results](../system#testdata-results) 的 [State](../system#challenge-state) 進行統計
For Example:
3xAC, 1xWA, 2xTLE

#### Subtask [State](../system#challenge-state) Count
不顯示 [Testdata Results](../system#testdata-results)
只顯示所有 [Subtask Results](../system#subtask-results) 的 [Testdata Result](../system#testdata-results) [State](../system#challenge-state) 的統計
For Example:

- Subtask 1: 2xAC, 1xWA
- Subtask 2: 3xAC
- Subtask 3: 1xTLE, 2xRE

#### Subtask Only
不顯示 [Testdata Results](../system#testdata-results)

#### Total Only
不顯示 [Subtask Results](../system#subtask-results) 與 [Testdata Results](../system#testdata-results)

admin 能透過 reject 功能將特定 challenge 取消評分，且該筆 challenge 直到被取消 rejected 狀態前，不應該被 rechallenge (not impl)

## `/contests/\d+/pro/(\d+)`
| Viewer User Type | [Problem Status](../system#problem-status) | Contest Running Status | Behavior |
| ---------------- | ------------------------------------------ | ---------------------- | -------- |
| Not Member       | ONLINE                                     | ANY                    | Redirect to std |
| Not Member       | CONTEST                                    | ANY                    | Redirect to std (But Will Get Permission Denied) |
| Not Member       | HIDDEN                                     | ANY                    | 不存在這種情況 |
| Contest User     | ONLINE                                     | Not Start              | Permission Denied |
| Contest User     | ONLINE                                     | Running                | Allow |
| Contest User     | ONLINE                                     | Ended                  | Redirect to Std Problem |
| Contest User     | CONTEST                                    | Not Start              | Permission Denied |
| Contest User     | CONTEST                                    | Running                | Allow |
| Contest User     | CONTEST                                    | Ended                  | Redirect to Std Problem (But Will Get Permission Denied) |
| Contest User     | HIDDEN                                     | ANY                    | 不存在這種情況 |
| Contest Admin    | ONLINE                                     | Not Start              | Allow |
| Contest Admin    | ONLINE                                     | Running                | Allow |
| Contest Admin    | ONLINE                                     | Ended                  | Allow |
| Contest Admin    | CONTEST                                    | Not Start              | Allow |
| Contest Admin    | CONTEST                                    | Running                | Allow |
| Contest Admin    | CONTEST                                    | Ended                  | Allow |
| Contest Admin    | HIDDEN                                     | ANY                    | 不存在這種情況 |

不顯示 TopCoder

## `/contests/\d+/proset`
| Viewer User Type | [Problem Status](../system#problem-status) | Contest Running Status | Behavior |
| ---------------- | ------------------------------------------ | ---------------------- | -------- |
| Not Member       | ANY                                        | ANY                    | Permission Denied |
| Contest User     | ANY                                        | Not Start              | Permission Denied |
| Contest User     | ANY                                        | Running                | Allow |
| Contest User     | ONLINE                                     | Ended                  | Allow, but click problem link will redirect to std problem |
| Contest User     | CONTEST                                    | Ended                  | Allow |
| Contest User     | HIDDEN                                     | Ended                  | 不存在這種情況 |
| Contest Admin    | ANY                                        | ANY                    | Allow |

依照該題目的 Score Type 顯示該題狀態 (必須要與 Scoreboard 一樣)

- IOI2013: Best Score or TODO
- IOI2017: Best Score or TODO
- ICPC: Best State or TODO

| Viewer User Type | Is Public Scoreboard | Freeze Time | Contest Running Status | Behavior |
| ---------------- | -------------------- | ----------- | ---------------------- | -------- |
| Not Member       | ANY                  | ANY         | ANY                    | Permission Denied |
| Contest User     | No                   | ANY         | ANY                    | No AC Ratio |
| Contest User     | Yes                  | Not set     | Running                | Show AC Ratio |
| Contest User     | Yes                  | Set         | Running                | Show AC Ratio (Freeze Apply) |
| Contest User     | No                   | ANY         | Ended                  | No AC Ratio |
| Contest User     | Yes                  | ANY         | Ended                  | Show AC Ratio |
| Contest Admin    | ANY                  | ANY         | ANY                    | Show AC Ratio |

AC Ratio 包含以下內容

- Challenge AC Ratio (Challenge AC Count / Challenge Count)
- User AC Ratio (User Challenged AC Count / User Challenged Count)

題目會按照新增順序排序

## `/contests/\d+/reg`

## `/contests/\d+/scoreboard`
| Viewer User Type | Target User Type | Contest Running Status | Freeze Scoreboard Period | Is Public Scoreboard | 是否顯示 |
| ---------------- | ---------------- | ---------------------- | ------------------------ | -------------------- | -------- |
| Not Member       | Contest User     | Not Start              | ANY                      | ANY                  | 不存在這種情況 |
| Not Member       | Contest User     | Running                | Not set                  | Yes                  | Allow |
| Not Member       | Contest User     | Running                | Set                      | Yes                  | Allow (Freeze Apply) |
| Not Member       | Contest User     | Running                | ANY                      | No                   | Permission Denied |
| Not Member       | Contest User     | Ended                  | ANY                      | Yes                  | Allow |
| Not Member       | Contest User     | Ended                  | ANY                      | No                   | Permission Denied |
| Not Member       | Contest Admin    | Not Start              | ANY                      | ANY                  | Permission Denied |
| Not Member       | Contest Admin    | Running                | ANY                      | ANY                  | Permission Denied |
| Not Member       | Contest Admin    | Ended                  | ANY                      | ANY                  | Permission Denied |
| Contest User     | Self             | Not Start              | ANY                      | ANY                  | Contest Not Start |
| Contest User     | Self             | Running                | Not set                  | ANY                  | Allow |
| Contest User     | Self             | Running                | Set                      | ANY                  | Allow (Freeze Apply) |
| Contest User     | Self             | Ended                  | ANY                      | ANY                  | Allow |
| Contest User     | Other Contest User | Not Start            | ANY                      | ANY                  | Contest Not Start |
| Contest User     | Other Contest User | Running              | Not set                  | Yes                  | Allow |
| Contest User     | Other Contest User | Running              | Set                      | Yes                  | Allow (Freeze Apply) |
| Contest User     | Other Contest User | Running              | ANY                      | No                   | Permission Denied |
| Contest User     | Other Contest User | Ended                | ANY                      | Yes                  | Allow |
| Contest User     | Other Contest User | Ended                | ANY                      | No                   | Permission Denied |
| Contest User     | Contest Admin    | ANY                    | ANY                      | ANY                  | Permission Denied |
| Contest Admin    | Contest User     | Not Start              | ANY                      | ANY                  | 不存在這種情況 |
| Contest Admin    | Contest User     | Running                | ANY                      | ANY                  | Allow |
| Contest Admin    | Contest User     | Ended                  | ANY                      | ANY                  | Allow |
| Contest Admin    | Contest Admin    | ANY                    | ANY                      | ANY                  | Allow |

依照 [Contest Mode](../system#contest-mode) 與 [Score Type](../system#score-type-only-for-ioi) 選擇 [Scoreboard 排名算法](../system#scoreboard-計分算法)

## `/contests/\d+/submit/(\d+)`
可選 [Compiler](../system#support-compilers) 為該題目允許的 Compiler 與 Contest 允許的 Compiler 的交集
無法上傳情況 (檢查順序按照下面)

- 沒有可用的 judge
- 長度大於 3227 或內容為空
- 不允許的 [Compiler](../system#support-compilers)
- 同一題同一類型的Compiler上傳相同 Code
- 上傳冷卻時間計時尚未結束 (秒數為比賽自訂)

上傳成功後，會更新上傳冷卻時間與[使用者的 Last Compiler](../system#user-system)

## `/contests/\d+/qa`
用來發問問題，查看公告與回覆，管理員沒有此頁面
左側為公告列表，右側為問題列表
當管理員回覆問題後，參賽者會收到一個紅點通知

發問問題有以下 Field 要設定

- Subject (最多 50 字)
- Content (最多 256 字)
每次發問後會有冷卻時間 (180 秒)

| Viewer User Type | Contest Running Status | Read Announcement | Ask Question |
| ---------------- | ---------------------- | ----------------- | ------------- |
| Not Member       | ANY                    | Allow             | Permission Denied |
| Contest User     | ANY                    | Allow             | Allow |
| Contest Admin    | ANY                    | Allow             | Permission Denied |