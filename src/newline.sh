#!/bin/bash

find $1 -regex ".+\.in\|.+\.out" | xargs -i dos2unix {}
find $1 -regex ".+\.in\|.+\.out" | xargs -i ./fixnoeol.sh {}
