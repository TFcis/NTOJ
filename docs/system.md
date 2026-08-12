# System

## Something Common
ID List 是指 `1, 2, 3`, `1-3, 5-9, 11,10` 這種列表  
時區由系統決定，預設為 UTC+8

## User System
### User Level
- GUEST
- USER
- KERNEL


- Mail
- Name
- Photo
- Cover
- Motto
- Lastip
- [Last Compiler](#support-compilers)
- ProClass Collection
- Specific IP

ProClass Collection 範圍是該使用者所能看到的 ProClass

## Judge System
### Support Compilers
- GCC GNU17
- Clang C17
- G++ GNU++17
- Clang++ C++17
- Rustc
- CPython
- OpenJDK
- Gas x86_64 Linux with Libc
- Gas x86_64 Linux with Libstdc++

## Rate System
用於計算在 Std 的題目與使用者統計資訊
這邊的使用者包含了 [KERNEL](#user-level) 與 [USER](#user-level)

- User Total Rate: 該使用者在 Std 中所有 [ONLINE](#problem-status) 題目的 Challenge 的 [Subtask Results](#subtask-results) 中 [State](#challenge-state) 為 AC 的 Rate 的總和
- User Problem AC Count: 該使用者在 Std 中所有 [ONLINE](#problem-status) 題目中有至少一筆 Challenge 的 [Total Result](#total-result) [State](#challenge-state) 為 AC 的總和
- Problem Challenge Count: 該題目在 Std 中所有使用者的 Challenge 總和
- Problem Challenge AC Count: 該題目在 Std 中所有使用者的 Challenge 中 [Total Result](#total-result) [State](#challenge-state) 為 AC 的總和
- Problem User Challenged Count: 該題目在 Std 中所有使用者中有至少一筆 Challenge 的使用者數量
- Problem User AC Count: 該題目在 Std 中所有使用者中有至少一筆 Challenge 的 [Total Result](#total-result) [State](#challenge-state) 為 AC 的**使用者數量**
- Problem AC Ratio: Problem Challenge AC Count / Problem Challenge Count
- Problem User AC Ratio: Problem User AC Count / Problem User Challenged Count

## Rank System

## Board System
### Board Type
- ONLINE
- HIDDEN

## ProClass System
### ProClass Type
- OFFICIAL_PUBLIC
- OFFICIAL_HIDEEN
- USER_PUBLIC
- USER_HIDDEN


## Problem System
### Problem Status
- ONLINE
- CONTEST
- HIDDEN

### Limit
- Time Limit (ms)
- Memory Limit (KiB)
- Output Limit (KiB)

Default 一定要設定
其他可以設定題目開放的 [Compiler](#support-compilers)

### Base Testdata
- Tags

### Subtask
- Testdata
- Rate
- Dependency Subtasks (不會有 Cycle)
- Tags

什麼是 Cycle, Simple Example

- Subtask 1 (Depends on 2)
- Subtask 2 (Depends on 3)
- Subtask 3 (Depends on 1)

這三個 Subtask 構成了一個 Cycle
Cycle 的詳細定義請參考 https://en.wikipedia.org/wiki/Cycle_(graph_theory)

### HTTP Content / Achievement
放在 `http/`，育社會有 `cont.html` 或是 `cont.pdf`

### BatchType
最常見的題目類型

#### `/manage/pro/updatejudge`
有以下 Field 要設定

Compiler Settings

- Allow Compilers
- Enable Grader
- User Program Additinoal Compile Args

Checker Configuration

Checker Type
- diff
- diff-strict
- diff-float, max error 1e-4
- diff-float, max error 1e-6
- diff-float, max error 1e-9
- CMS/TPS Testlib
- Standard Testlib (Polygon)
- IORedir (WIP)
- TOJ (WIP)

在 Checker Type 為 CMS/TPS Testlib, Standard Testlib, TOJ 時，還需要設定以下內容

- Checker Compiler
- Checker Additinoal Compile Args

在 Checker Type 為 IORedir 時，還需要設定以下內容

- Checker Compiler
- Checker Additinoal Compile Args
- IORedir Settings (JSON)

Summary Configuration

Summary Type

- GroupMin
- Overwrite
- Custom

Judge 需要保證 `GroupMin` 與 CMS 的 `GroupMin` 行為一樣

在 Summary Type 為 Custom 時，還需要設定以下內容

- Summary Compiler
- Summary Additinoal Compile Args

Scoring Configuration

- Score Precision (0 ~ 3)

#### `/manage/pro/updatetestdata`
更新測資檔案
由 `.in` 與 `.out` 組成

#### `/manage/pro/filemanager`
題目檔案

`http`
用於放置題目描述檔案如 cont.html, cont.pdf

`checker`
當 Checker Type 為 CMS/TPS Testlib, Standard Testlib, IORedir, TOJ 時，用於放置 Checker 程式碼

`grader`
當 Enable Grader 時，用於放置 Grader 程式碼
會根據 Compiler 設定分資料夾
For Example:
```
grader/
  c/
    grader.c
  cpp/
    grader.cpp
  python/
    grader.py
```

## Challenge System
### Challenge State
- Accepted (AC): Judge 認為答案完全正確
- Partial Correct (PC): Judge 認為答案部份正確
- Wrong Answer (WA): Judge 認為答案錯誤
- Runtime Error (RE): Judge 過程中遇到 exit status 不為 0
- Runtime Error Killed by signal (RESIG): Judge 過程中遇到 Signal 錯誤
- Time Limit Exceeded (TLE): 執行時間超過 [Limit](#limit)
- Memory Limit Exceeded (MLE): 記憶體超過 [Limit](#limit)
- Output Limit Exceeded (OLE): 輸出超過 [Limit](#limit)
- Compile Error (CE): 編譯錯誤
- Compilation Limit Exceeded (CLE): 編譯超過 Judge 限制
- Internal Error (IE): Backend 或是 Judge 內部出錯
- Judge Error (JE): 題目出錯 (Checker, Custom Summary, ......)
- Challenging: Judge 中
- Not Started: 尚未 Judge
- Skipped: 跳過該 Subtask 或是 Testdata
- Rejected: 被管理員拒絕

#### Judge 需要保證只回傳以下 State
- AC
- PC
- WA
- RE
- RESIG
- TLE
- MLE
- OLE
- CE
- CLE
- IE
- JE
- Skipped

#### 以下 State 是由 Backend 設定的
- Challenging
- Not Started
- Rejected

如果上傳的當下 Code 遺失了，則會得到 IE

### Message Type
- NONE
- TEXT
- HTML

### Total Result  
- Runtime: Challenge 執行時間，依照 Judge 回傳值決定，Backend 無權決定此事，單位為毫秒
- Memory: Challenge 記憶體消耗，依照 Judge 回傳值決定，Backend 無權決定此事，單位為 KiB
- [State](#challenge-state): Challenge 狀態，依照 Judge 回傳值決定，Backend 無權決定此事
- Rate: Challenge 分數，由 Judge 回傳值決定，Backend 無權決定此事，依據題目的 Rate Precision 決定小數點位數
- Message: Challenge 回應，依照 Judge 回傳值決定，Backend 無權決定此事，只有在狀態為 Rejected 時 Backend 才可修改
- [MessageType](#message-type): Challenge 回應類型，依照 Judge 回傳值決定，Backend 無權決定此事
- [Compiler](#support-compilers): 使用者上傳的 [Compiler](#support-compilers)
- Problem: 使用者上傳的 Problem
- Account: 使用者上傳的 Account
- Timestamp: 使用者 Submit 當下的 Timestamp
- Challenge ID: 對應的 Challenge ID

### Subtask Results  
- Runtime: 該 Subtask 的執行時間，依照 Judge 回傳值決定，Backend 無權決定此事
- Memory: 該 Subtask 的記憶體消耗，依照 Judge 回傳值決定，Backend 無權決定此事
- [State](#challenge-state): 該 Subtask 的狀態， 依照 Judge 回傳值決定，Backend 無權決定此事
- Rate: 該 Subtask 的分數，由 Judge 回傳值決定，Backend 無權決定此事，[Subtask](#subtask) 的 Rate 僅供 Judge 參考，依據題目的 Rate Precision 決定小數點位數

### Testdata Results  
- Runtime: 該 Subtask 的執行時間，依照 Judge 回傳值決定，Backend 無權決定此事
- Memory: 該 Subtask 的記憶體消耗，依照 Judge 回傳值決定，Backend 無權決定此事
- [State](#challenge-state): 該 Subtask 的狀態， 依照 Judge 回傳值決定，Backend 無權決定此事
- Message: 該 Testdata 的回應，依照 Judge 回傳值決定，Backend 無權決定此事
- [MessageType](#message-type): Challenge 回應類型，依照 Judge 回傳值決定，Backend 無權決定此事

## Contest System
### Field
- Contest Name
- Contest Creator
- Contest Desc Before Contest
- Contest Desc During Contest
- Contest Desc After Contest
- [Contest Mode](#contest-mode)
- Contest Start Time
- Contest End Time
- [Registration Mode](#registration-mode)
- Registration Deadline
- [Allow Compilers](#support-compilers)
- Submit CD Time
- Penalty Time
- Freeze Scoreboard Period
- Is Public Scoreboard

### Contest Mode
- IOI
- ACM/ICPC

### Score Type
- IOI2013
- IOI2017
- ICPC

### Scoreboard 計分算法
- [IOI2013](#score-type)
- [IOI2017](#score-type)
- [ICPC](#score-type)

當 [Contest Mode](#contest-mode) 為 IOI 時，[Score Type](#score-type-only-for-ioi) 可以混用 IOI2013 與 IOI2017，不可選 ICPC
當 [Contest Mode](#contest-mode) 為 ACM/ICPC 時，不可選 [Score Type](#score-type-only-for-ioi)，排名算法一定是 ICPC

#### IOI2013
取該題目該使用者所有 Challenge 的 [Total Result](total-result) rate 最大值用於排名，若同分則排名相同
<!-- 如果分數相同排名相同
但在顯示上, 排序標準為
- Total Rate 降序
- AC Problme Count 降序
- 最早達到分數的 Challenge Timestamp 升序 -->

舉例
Problem A 有以下 [Subtasks](#subtask)

- [Subtask](#subtask) 1 (Rate 40)
- [Subtask](#subtask) 2 (Rate 30)
- [Subtask](#subtask) 3 (Rate 20)
- [Subtask](#subtask) 4 (Rate 10)

User X 有以下 Challenge 的 Total Result

- [Challenge Total Result 1](#total-result) (Total Rate 60)
- [Challenge Total Result 2](#total-result) (Total Rate 40)

則 User X 在 Problem A 的分數為 Challenge 1 的 60 與 Challenge 2 的 40 最大值為 60

#### IOI2017
取該題目該使用者所有 Challenge 的 [Subtask Results](../system#subtask-results) rate 聯集用於排名，若同分則排名相同
<!-- 如果分數相同排名相同
但在顯示上, 排序標準為
- Total Rate 降序
- AC Problme Count 降序
- 最早達到分數的 Challenge Timestamp 升序 -->

舉例
Problem A 有以下 [Subtasks](#subtask)

- [Subtask](#subtask) 1 (Rate 40)
- [Subtask](#subtask) 2 (Rate 30)
- [Subtask](#subtask) 3 (Rate 20)
- [Subtask](#subtask) 4 (Rate 10)

User X 有以下 Challenge

- Challenge 1
    - [Subtask Result 1](#subtask-results) (Rate 40)
    - [Subtask Result 2](#subtask-results) (Rate 0)
    - [Subtask Result 3](#subtask-results) (Rate 20)
    - [Subtask Result 4](#subtask-results) (Rate 0)

- Challenge 2
    - [Subtask Result 1](#subtask-results) (Rate 0)
    - [Subtask Result 2](#subtask-results) (Rate 30)
    - [Subtask Result 3](#subtask-results) (Rate 0)
    - [Subtask Result 4](#subtask-results) (Rate 10)

則 User X 在 Problem A 的 Rate 為 Challenge 1 的 40 + 20 與 Challenge 2 的 30 + 10 總和為 100

#### ICPC
隊伍以解題數量多者排名較前，解題數量相同時，以總消耗時間少者排名較前。
答對的題目的消耗時間計算方式為比賽開始至解出題目所消耗的分鐘數。
如解出前有答錯，除編譯錯誤外，每一次需要另加 Penalty Time 分鐘。
總消耗時間為所有答對題目的消耗時間加總。
未答對的題目不計消耗時間。
如兩隊解題數與耗時相同，則以最後答對題目的 Challenge ID 較小者為勝。

### Registration Mode
- Invited
- Free Registration
- Registration Need Approval

### Contest User Status
- REJECTED
- REQUESTED
- APPROVED
- ADMIN

Contest Admin 就是 [Contest User Status](#contest-user-status) 為 ADMIN 的帳號
Contest User 就是 [Contest User Status](#contest-user-status) 為 APPROVED 的帳號

### System Test
類似 Codeforces 的系統測試
在賽中 Contest User Submit 的 Challenge 會受到 System Test 限制，對於有 `system-test` tag 的 [Subtask](#subtask) 與 [Testdata](#base-testdata)，其 [Subtask Result](#subtask-results) 與 [Testdata Result](#testdata-results) [State](#challenge-state) 會被標記為 Skipped，不會被 Judge 執行
Rejudge Contest User Challenge 同樣也是受到 System Test 限制
而 Contest Admin 的 Challenge 則會全部執行，不管是 Submit 還是 Rejudge

賽後執行 System Test 時
只會測試 PreTest [Total Result](#total-result) [State](#challenge-state) 為 AC 的 Challenge (NotImpl)
Contest Admin 的 Challenge 不受 System Test 影響