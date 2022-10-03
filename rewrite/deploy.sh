#!/bin/bash

# scp -C -r /home/tobiichi3227/github_use/TOJ/rewrite/* tobiichi3227@192.168.122.157:/home/tobiichi3227/oj/

sass ./src/scss/proset.scss ./src/proset.css
sass ./src/scss/pro.scss ./src/pro.css
sass ./src/scss/acct.scss ./src/acct.css
sass ./src/scss/challist.scss ./src/challist.css
sass ./src/scss/board.scss ./src/board.css

rsync -r /home/tobiichi3227/github_use/TOJ/rewrite/* tobiichi3227@192.168.122.157:/home/tobiichi3227/oj/
rsync -r /home/tobiichi3227/github_use/TOJ/rewrite/src/* tobiichi3227@192.168.122.157:/home/tobiichi3227/html/oj/
