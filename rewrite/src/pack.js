'use strict';

var pack = new function(){
    var that = this;

    that.get_token = function(){
	    var defer = $.Deferred();

	    $.post('/oj/be/manage/pack',{
	        'reqtype':'gettoken'
	    },function(res){
	        if(res[0] == 'E'){
	    		defer.reject(res[0]);
	        }else{
	    		defer.resolve(JSON.parse(res));
	        }
	    });

	    return defer.promise();
    };
    that.send = function(pack_token, file){
	var ws = new WebSocket('ws://192.168.122.157/oj/be/pack');
	var defer = $.Deferred();
	var off = 0;
	var remain = file.size;
	var lt = 0;

	ws.onopen = function(e){
	    ws.send(JSON.stringify({
		    'pack_token':pack_token,
		    'pack_size':file.size
	    }));
	};
	ws.onmessage = function(e){
	    var size;
	    var ct;

	    if(e.data[0] == 'E'){
		    ws.close();
		    defer.reject();
	    } else if (remain > 0){
		    size = Math.min(remain, 65536);
		    ws.send(file.slice(off, off + size));

		    off += size;
		    remain -= size;

		    ct = new Date().getTime();
			if(ct - lt > 500) {
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
