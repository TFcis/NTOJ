# Changelog

## NTOJ

### 2.1.2 <small>Nov 12, 2023</small>

- Feat(rank): Add colors to topcoders
- Feat(problemset): Add filter and sort option
- Chore(devlog): Refactor devlog
- Chore: Remove unused files
- Fix: Cannot register bug

### 2.1.1 <small>Nov 7, 2023</small>

- Feat(problemset): Link to ranklist
- Feat(info): Update new judge in footer
- Impr(challenges): Use const variables
- Impr(about): Remove collapse in about page
- Refactor(info): Refactor all info page and decrease brightness of verdict table
- Fix(manage): Fix rechallenge not working
- Fix: Fix typos
- Fix: Upload problem bug

### 2.1.0 <small>Nov 5, 2023</small>

- Feat(judge): New judge from go-judge
- Chore: Remove unused css files
- Chore: Rename all .templ files to .html
- Style: Format files
- Fix(manage): Cannot open manage page bug

### 2.0.6 <small>Nov 1, 2023</small>

- Refactor(dev-info): Refactor and update devlog
- Fix: Fix mis-delete bug

### 2.0.5 <small>Oct 31, 2023</small>

- Feat(info): Add RE(SIG) explanation
- Feat(info): Add IE and PE to verdicts table
- Feat(about): Add new developer
- Refactor(about): Refactor the whole page
- Refactor(dev-info): Reverse devlog order and refactor a part of releases
- Fix(info): Challenges guide layout bug
- Fix(info): Adjust font-size of verdict table

### 2.0.4 <small>Oct 30, 2023</small>

- Feat(info): Add verdict table and verdicts explanation
- Refactor(info): Refactor info page
- Fix: Fix filter explanation layout bug
- Fix: Text color bug

### 2.0.3 <small>Oct 28, 2023</small>

- Fix(account): Cannot update profile
- Fix: Package not found
- Fix: Install script syntax error

### 2.0.2 <small>Oct 26, 2023</small>

- Feat: Add install script
- Feat: Add fix file with no eol script
- Feat: Add README.md
- Impr: Use class instead of using dictionary to store account
- Impr: Use function to check whether server is online
- Fix(board): Wrong time zone
- Fix(account): Format errors

### 2.0.1 <small>Oct 6, 2023</small>

- Feat(challenges): Prevent users to search hidden problems
- Refactor: Refactor some functions to normal function
- Fix(challenges): Compiler type filter error
- Fix: Fix typos

### 2.0.0 <small>Oct 2, 2023</small>

- Feat(challenges): Add compiler type filter
- Feat(challenges): Add copy code button
- Feat(problem): Add problem AC user ratio and AC submission ratio
- Feat(bulletin): Sort by pinned and changed time
- Impr(UI): Use bootstrap 5 to rewrite user interface
- Chore: Migrate data from redis to database
- Chore: Update jquery to v3.7.1
- Fix(challenges): Update challenge status bug
- Fix(problem): Upload problems bug
- Fix(UI): display error
- Fix: bootstrap loading error

### 1.4.0 <small>Aug 4, 2023</small>

- Feat(question): Add ask notify count
- Impr(permission): Use decorator method to check permission
- Impr: separate services and handlers from the same file
- Style: Format all python files
- Fix: Remove unnecessary checks
- Fix: Remove unused files

### 1.3.1 <small>Jul 19, 2023</small>

- Impr: Change time zone to UTC+08:00

### 1.3.0 <small>May 16, 2023</small>

- Feat(language): Add Python3 and Rust support

### 1.2.13 <small>Apr 21, 2023</small>

- Feat(navbar): Add Dev Info
- Impr(challenges): Compiler error UI

### 1.2.12 <small>Mar 2, 2023</small>

- Feat: Add API function
- Fix: list_pro() bug

### 1.2.11 <small>Feb 17, 2023</small>

- Feat(judge): Offline announcement
- Impr(judge): Optimize judge heartbeat detection
- Fix: Endless loop bug

### 1.2.10 <small>Feb 8, 2023</small>

- Impr(challenges): Prevent user using incorrect searching format
- Impr(problemset): Prevent user using incorrect searching format

### 1.2.9 <small>Feb 7, 2023</small>

- Impr(problems): Reinitialize the problems
- Impr: JSON online editor on problem update page

### 1.2.8 <small>Jan 30, 2023</small>

- Fix: loglist page bug
- Fix: Cannot change password bug

### 1.2.7 <small>Jan 13, 2023</small>

- Feat(challenges): Display CE reason board will now record last scroll position, and scroll smoothly past it.

### 1.2.6 <small>Nov 12, 2022</small>

- Fix: Websocket connection error
- Fix: Cannot rechallenge
- Fix: Cannot save problem files
- Fix: Upload problem bug #1


### 1.2.5 <small>Nov 7, 2022</small>

- Fix: Fix missing file bug

### 1.2.4 <small>Oct 31, 2022</small>

- Impr: Change manage-judge log record message
- Impr: Remove some unnecessary redis cache
- Impr: Unload some unnecessary js code
- Fix(question): Cannot sumbit bug
- Fix: Manage-judge bug

### 1.2.3 <small>Oct 26, 2022</small>

- Impr(problemset): Optimize tags
- Impr: Record group operation to log
- Fix(problem): Showing tags before AC
- Fix: Not showing tags in admin accounts
- Fix: Get user AC ratio bug

### 1.2.2 <small>Oct 22, 2022</small>

- Impr: AC ratio query
- Impr: Judge service optimization

### 1.2.1 <small>Oct 19, 2022</small>

- Impr: Add log type in log record
- Impr: Using the log type to make classification
- Fix: Change arrow function back to the previous version

### 1.2.0 <small>Oct 17, 2022</small>

- Feat(challenges): Show information
- Impr(judge): Rewrite judge pulse monitor
- Impr(judge): Implement judge cluster
- Impr: Update manage-judge interface
- Impr: Optimize list_pro SQL query
- Impr: Completely close a part of redis, websocket, postgresql connection

### 1.1.1 <small>Oct 15, 2022</small>

- Feat(problemset): User AC ratio
- Feat: Customize inform test color
- Feat: JS code lint
- Impr(challenges): Use Websocket to prevent screen flashing

### 1.1.0 <small>Oct 14, 2022</small>

- Feat: Implement chalsub and informsub
- Impr(SQL): Replace by connection pool
- Impr(Redis): Replace by aioredis using async/await

### 1.0.0 <small>Oct 5, 2022</small>

- Feat(challenges): Copy code button
- Feat(tags): Only show after AC
- Feat: Jump back to the page you last visited after logging in again
- Feat: Reconnect judge from website
- Feat: Announcement on the home page when judge is offline and the submit page will be invisible
- Impr(framework): Refactor with tornado 6.2
- Impr(database): Refactor with asyncpg
- Impr: Optimize a part of SQL queries and functions
