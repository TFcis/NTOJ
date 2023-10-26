#!/bin/bash
# fix file no eol

file=$1
if diff /dev/null ${file} | tail -1 | grep '^\\ No newline' >/dev/null; then
	echo >>${file}
fi
