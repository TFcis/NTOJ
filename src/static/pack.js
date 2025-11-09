'use strict';

var pack = new function() {
    var that = this;

    that.get_token = function() {
	    var defer = $.Deferred();

        let base_url = $('#indexjs').attr('base_url');
	    $.post(`${base_url}/be/manage/pack`, {
	        'reqtype':'gettoken'
	    }, function(res) {
            res = JSON.parse(res);
            if (res.status[0] == 'E') {
	    		defer.reject(res[0]);
            } else {
	    		defer.resolve(res.data);
            }
	    });

	    return defer.promise();
    };
    that.send = function(pack_token, file) {
        let ws_link = '';
        let base_url = $('#indexjs').attr('base_url');
        if (location.protocol !== 'https:') {
            ws_link = `ws://${location.host}${base_url}/be/pack`;
        } else {
            ws_link = `wss://${location.host}${base_url}/be/pack`;
        }
        var ws = new WebSocket(ws_link);
        var defer = $.Deferred();
        var off = 0;
        var remain = file.size;
        var lt = 0;

        ws.onopen = function(e) {
            var blobSlice = File.prototype.slice || File.prototype.mozSlice || File.prototype.webkitSlice,
                chunkSize = 2097152,                             // Read in chunks of 2MB
                chunks = Math.ceil(file.size / chunkSize),
                currentChunk = 0,
                spark = new SparkMD5.ArrayBuffer(),
                fileReader = new FileReader();

            fileReader.onload = function (e) {
                spark.append(e.target.result);                   // Append array buffer
                currentChunk++;

                if (currentChunk < chunks) {
                    loadNext();
                } else {
                    ws.send(JSON.stringify({
                        'pack_token' : pack_token,
                        'pack_size' : file.size,
                        'md5': spark.end(),
                    }));
                }
            };

            fileReader.onerror = function () {
                ws.close();
            }

            function loadNext() {
                var start = currentChunk * chunkSize,
                    end = ((start + chunkSize) >= file.size) ? file.size : start + chunkSize;

                fileReader.readAsArrayBuffer(blobSlice.call(file, start, end));
            }

            loadNext();
        };
        ws.onmessage = function(e) {
            var size;
            var ct;

            if (e.data[0] == 'E') {
                ws.close();
                defer.reject();
            } else if (remain > 0) {
                size = Math.min(remain, 65536);
                ws.send(file.slice(off, off + size));

                off += size;
                remain -= size;

                ct = new Date().getTime();
                if (ct - lt > 500) {
                    defer.notify(off / file.size);
                    lt = ct;
                }
            } else {
                defer.notify(1);
                defer.resolve();
            }
        };

        return defer.promise();
    };
};
