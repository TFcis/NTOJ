#!/bin/bash

find $1 -regex ".+\.in\|.+\.out" | xargs -i dos2unix {}
