# Development Environment Setup
## Docker
### Install
1. `git clone https://github.com/TFcis/NTOJ`
2. `docker compose -f docker-compose.dev.yml up --watch`
3. 新開一個 Terminal
5. `docker compose -f docker-compose.dev.yml exec -it backend bash` 進到 container 裡面
6. `./scripts/runserver.sh`
7. 開啟瀏覽器進入 http://localhost:5500，就可以看到 TOJ 了

### Dev
可以在 Container 裡面修改檔案，如果要裝 Vim 的話，按照下面步驟
```sh linenums="1"
apt update -y
apt install vim -y
```

也可直接在本機修改檔案，內容會同步到 Container 裡面，是否要重起 Server 取決於修改的檔案是什麼
```sh linenums="1"
# Ctrl+C 會關閉 Server
./scripts/runserver.sh # 重起 Server
```

如果要刪掉 Container 與 Volume 重新執行

1. `docker compose -f docker-compose.dev.yml down -v`
2. `docker compose -f docker-compose.dev.yml up --watch`

如果連 Image 也要刪掉

1. `docker compose -f docker-compose.dev.yml down -v --rmi all`
2. `docker compose -f docker-compose.dev.yml up --watch`

重新 Build Image

1. `docker compose -f docker-compose.dev.yml up --build --watch`

進到 Database 裡面

1. `cat config.py` 確認 Database 帳號密碼 (預設是帳號 ntoj 密碼 ntoj)
2. `psql -d ntoj -U ntoj -h db`

清除所有 Redis Cache
```sh linenums="1"
poetry run python3 -c "import redis,config;r=redis.Redis(host=config.REDIS_HOST,port=6379,db=config.REDIS_DB);r.flushall();r.close();"
```

執行 Unit Test
```sh linenums="1"
./rununittest.sh
```

執行 Integration Test
```sh linenums="1"
./runintegratedtest.sh
```

### Note For Windows
一定要用 WSL

1. WSL 要開 cgroup2, 請參考 https://stackoverflow.com/questions/73021599/how-to-enable-cgroup-v2-in-wsl2
2. `git clone` 的位置要在 WSL 的 Folder，不能在 Windows 的 Folder，否則檔案無法同步到 Container 裡面
3. git CRLF 請參考[這篇設定](https://darkcode.top/post/git_lf_crlf/)，不然會遇到很多 CRLF 的問題

## VM (Installation Script)
### NOTE: 這東西可以不用看了
### Deploy
#### Pre
1. 去 ubuntu 24.04 或 debian 12 的 VM 或 WSL (TOJ 特別爛，只能在這個上面跑)
2. sudo apt install git tmux python3 python3-pip
3. echo echo "set -g mouse on" > $HOME/.tmux.conf
4. sudo mkdir /srv (理論上 ubuntu 跟 debian 都有)

#### Deploy Judge
1. cd $HOME
2. git clone https://github.com/tobiichi3227/NTOJ-Judge-Rewrite
3. cd NTOJ-Judge-Rewrite
4. sudo tmux
5. pip3 install tornado cffi --break-system-packages
6. cd src
7. cd default-checker
8. make
9. cd ..

#### Deploy Backend
1. cd $HOME
2. git clone https://github.com/TFcis/NTOJ
3. cd NTOJ
4. cd scripts
5. cp .env.example .env
6. ./install.sh
7. 跑就對了
8. cd /srv/ntoj
9. 改 config.py
10. JUDGE_SERVER_LIST 改成
```py
JUDGE_SERVER_LIST = [
{'name': '隨便你打', 'url': 'ws://127.0.0.1:2502/judge', 'problems_path': '/srv/ntoj/problem', 'codes_path': '/srv/ntoj/code'}
]
```
11. 記得存檔

### Run Judge
1. cd $HOME/NTOJ-Judge-Rewrite/src
2. tmux
3. python3 server.py

### Run Backend
1. cd /srv/ntoj
2. tmux
3. ./runserver.sh
4. Ctrl+B D 暫時離開 tmux 或是繼續留在 tmux

judge 的路徑會在 $HOME/NTOJ-Judge-Rewrite
backend 的路徑會在 /srv/ntoj

### Dev
改 /srv/ntoj 跟原本 git 的 Code
然後重啟 Backend 即可
TOJ 就很爛，如果要看 backend 要改 /srv/ntoj，看跑 test 要改原本 git 的地方

### 跑 Test
去你原本 Git 的地方
$HOME/.local/bin/poetry install 
$HOME/.local/bin/poetry add coverage requests bs4 playwright
$HOME/.local/bin/poetry run playwright install
cd src
./rununittest.sh
./runintegratedtest.sh
./rune2etest.sh

### Tmux 教學
Ctrl+B D 是先按住 Ctrl+B，然後放掉，再按 D，這樣會暫時離開 tmux，裡面的東西會繼續執行
tmux attach -t 0 可以回到第 0 個 tmux
tmux attach -t 1 以此類推