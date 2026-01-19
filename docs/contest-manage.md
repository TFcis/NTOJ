# Contest Manage

## `/contests/manage/add`
用於新增比賽
有以下 Field 要設定
- Contest Name (最多 50 字)

## `/contests/\d+/manage/acct`
用於新增參賽者與管理員
管理員自己不能移除自己
每次新增完後會按照 acct_id 進行排序
比賽建立者不能被刪除 (Not Impl)

當模式為 Approval，如果管理員手動加入等待 approval 的 acct，該acct 將會從 approval list 移除

## `/contests/\d+/manage/desc`
Contest Description 分為

- 賽前
- 賽中
- 賽後
可以 Preview 內容 (會 Render Markdown 與 LaTex)
(最多 20000 字, NotImpl)

## `/contests/\d+/manage/general`
有以下 Field 要設定

- Contest Name (最多 50 字, NotImpl)
- [Contest Mode](../system#contest-mode)
- Contest Start Time
- Contest End Time (必須 > Contest Start Time)
- [Registration Mode](../system#registration-mode)
- Registration Deadline (必須 <= Contest End Time)
- Submit CD Time (ms)
- Freeze Scoreboard Period (minutes) (必須在 <= Contest End Time - Contest Start Time)
- Is Public Scoreboard
- Enable System Test
- [Allow Compilers](../system#support-compilers)

當 [Contest Mode](../system#contest-mode) 切換到 ICPC/ACM 時，會有以下行為
- 可以設定 Penalty Time (minutes)，預設為 20 分鐘
- 將 Submit CD Time 設為 1 秒
- 將所有題目的 [Score Type](../system#score-type) 改為 ICPC

當 [Contest Mode](../system#contest-mode) 切換到 IOI 時，會有以下行為
- 不能設定 Penalty Time
- 將 Submit CD Time 設為 30 秒
- 將所有題目的 [Score Type](../system#score-type) 改為 IOI2017

當 Registration Mode 從 Approval 轉到 Free 時，所有等待 approve 的帳號將會自動通過

## `/contests/\d+/manage/pro`
用於新增或刪除題目，只能新增 [ONLINE](../system#problem-status) 與 [CONTEST](../system#problem-status) 狀態的題目
題目順序按照新增順序排列

當 Contest Mode = IOI 時，每個題目可以設定 Score Mode，有 IOI2013 與 IOI2017
Contest Mode = ICPC 時，Score Mode 固定為 ICPC

對於每個題目可以設定 Challenge Style
包含以下五種選項

- Full
- Testdata [State](../system#challenge-state) Count
- Subtask [State](../system#challenge-state) Count (NotImpl)
- Subtask Only
- Total Only

當比賽結束後，可以使用 Public Problem，會將題目狀態改為 [ONLINE](../system#problem-status)
Public All Problems 會將所有題目狀態改為 [ONLINE](../system#problem-status)
Rechallenge 會將賽中該題所有 challenge rejudge 一次，但不會跑 rejected (NotImpl)
當 Enable System Test 時，會多出 System Test All 與 System Test 按鈕，只能在 Contest Running Status 為 Ended 時使用

### System Test
對於所有 Contest Admin 的 Challenge 不會執行 System Test

## `/contests/\d+/manage/reg`
Reg有三種模式，分別為 Invited, Free Registration, Registration Approval

可以 Approve 與 Reject 等待 approve 的帳號

## `/contests/\d+/manage/question`
用來回覆參賽者問題
有提供以下幾個預設回覆內容

- Yes
- No
- No comment
- Answered in problem description
- Invalid question

選擇 Other 可以自行填寫回覆內容

已經回覆後可以更新回覆內容，會更新回覆時間
當參賽者被從 Contest 移除後，該參賽者的所有問題不會被刪除
當參賽者發問問題後，會收到一個紅點通知
當管理員回覆問題後，參賽者會收到一個紅點通知，且 Contest Admin 的紅點數量會減一

## `/contests/\d+/manage/announce`
用來發布公告
有兩個 Field 要設定

- Subject (最多 50 字)
- Content (最多 256 字)

對於已發佈的公告，可以進行以下操作

- Edit, 會更新公告時間，更新成功後參賽者會收到更新紅點
- Popup, 會向所有參賽者彈出公告視窗
