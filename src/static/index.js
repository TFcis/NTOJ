'use strict';

// from https://medium.com/enjoy-life-enjoy-coding/typescript-%E5%96%84%E7%94%A8-enum-%E6%8F%90%E9%AB%98%E7%A8%8B%E5%BC%8F%E7%9A%84%E5%8F%AF%E8%AE%80%E6%80%A7-%E5%9F%BA%E6%9C%AC%E7%94%A8%E6%B3%95-feat-javascript-b20d6bbbfe00
const newEnum = (descriptions) => {
    const result = {};
    Object.keys(descriptions).forEach((description) => {
        result[(result[description] = descriptions[description])] = description;
    });
    return Object.freeze(result);
};

var index = new function() {
    var that = this;
    var curr_url = null;
    that.cont_destroy = null;
    that.containerLoadDone = false;

    /**
     * @var {number|null} that.acct_id - current account id, null if not logged in
     */
    that.acct_id = null;
    that.base_url = null;
    that.prev_url = null;

    /**
     * @var {WebSocket|null} that.ws - current WebSocket connection, null if none, if contest_id set, it will connect to contest ws, otherwise normal ws
     */
    that.ws = null;

    /**
     * @var {Map<string, function>} that.ws_callback_map - map of websocket message type to callback function
     */
    that.ws_callback_map = new Map();

    /**
     * @var {Array<string>} that.ws_pending_registers - pending register types waiting for WebSocket to open
     */
    that.ws_pending_registers = [];
    /**
     * @var {Array<{type: string, data: any}>} that.ws_pending_messages - pending messages waiting for WebSocket to open
     */
    that.ws_pending_messages = [];

    /*
        Reload new page
    */
    function update(force) {
        var i;

        var parts;
        var page;
        var req;
        var args;
        var j_navlist = $('#index-navlist');
        var j_cont = $('#index-cont');
        var cont_defer = $.Deferred();

        /*
            Adjust the scroll to right position
        */
        function _scroll() {
            var j_e;

            j_e = $(location.hash);
            if (j_e.length == 1) {
                $(window).scrollTop(j_e.offset().top - 32); //distance to top
            }
        }

        parts = location.href.split('#');
        if (curr_url == parts[0] && force == false) {
            _scroll();
            return;
        }

        index.prev_url = curr_url;
        curr_url = parts[0];

        parts = curr_url.split('/');
        let skip_count = 3 + that.base_url_slash_count;
        // ["http:", "", "localhost:8080"].length == 3
        if (parts[skip_count] == '') {
            page = 'info';
            req = '/info';

        } else {
            page = parts[skip_count];
            if (parts[parts.length - 1] !== "") {
                let t = parts[parts.length - 1].match(/(.*)\?([^#]+)/);
                let flag = false;
                if (t === null) {
                    flag = true;
                    parts.push("");
                } else {
                    if (t[1] !== "") {
                        flag = true;
                        parts[parts.length - 1] = t[1];
                        page = t[1];
                        parts.push(`?${t[2]}`);
                    }
                }

                if (flag) {
                    window.history.pushState(null, document.title, parts.join("/"));
                    update(false);
                    return;
                }
            }

            req = '';

            for (i = skip_count; i < parts.length - 1; i++) {
                req += '/' + parts[i];
            }

            parts = parts[parts.length - 1].match(/\?([^#]+)/);

            /*
            Prevent from using cache
            */
            if (parts == null) {
                args = 'ca=' + new Date().getTime();
            } else {
                args = parts[1] + '&ca=' + new Date().getTime();
            }
        }

        if (page == 'index') {
            req = '/none';
            page = 'none';
        }

        j_navlist.find('li').removeClass('active');
        j_navlist.find('li.' + page).addClass('active');

        if (typeof(destroy) == 'function' && that.cont_destroy === destroy) {
            destroy();
        }

        cont_defer.done(function(res) {
            that.containerLoadDone = false;
            var tmp = $('<div>').html(res);

            var externalScripts = [];
            var inlineScripts = [];
            tmp.find('script').each(function() {
                var src = $(this).attr('src');
                if (src) {
                    externalScripts.push({
                        src: src,
                        attrs: (function(e){
                            var at = {};
                            $.each(e.attributes, function(i,a){ if (a.specified) at[a.name]=a.value; });
                            return at;
                        })(this)
                    });
                } else {
                    inlineScripts.push($(this).html());
                }
            });

            var links = [];
            tmp.find('link[rel=stylesheet][href]').each(function() {
                links.push($(this).attr('href'));
            });

            tmp.find('script[src], link[rel=stylesheet][href]').remove();
            j_cont.html(tmp.html());

            var promises = [];

            links.forEach(function(href) {
                var d = $.Deferred();
                var link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = href;
                link.onload = function(){ console.log('CSS loaded', href); d.resolve(); };
                link.onerror = function(){ console.warn('CSS failed', href); d.resolve(); };
                document.head.appendChild(link);
                promises.push(d.promise());
            });

            externalScripts.forEach(function(s) {
                var d = $.Deferred();
                var sc = document.createElement('script');
                sc.src = s.src;
                if (s.attrs) {
                    if (s.attrs.type) sc.type = s.attrs.type;
                    if (s.attrs.async) sc.async = s.attrs.async;
                    if (s.attrs.defer) sc.defer = s.attrs.defer;
                }
                sc.onload = function(){ console.log('script loaded', s.src); d.resolve(); };
                sc.onerror = function(){ console.warn('script load error', s.src); d.resolve(); };
                document.body.appendChild(sc);
                promises.push(d.promise());
            });

            var executeInline = function() {
                inlineScripts.forEach(function(code) {
                    try {
                        $.globalEval(code); // safe-ish; globalEval，new Function(code)()
                    } catch (e) {
                        console.error('inline script error', e);
                    }
                });
            };

            $.when.apply($, promises.length ? promises : [$.Deferred().resolve()]).done(function() {
                console.log('all external resources loaded');
                executeInline();
                if (typeof init === 'function') {
                    try { init(); console.log('init executed'); }
                    catch (e) { console.error('init error', e); }
                } else {
                    console.log('no init function');
                }
                if (typeof destroy === 'function' && that.cont_destroy !== destroy) {
                    that.cont_destroy = destroy;
                } else {
                    that.cont_destroy = null;
                }
                that.containerLoadDone = true;
            });

            _scroll();
        });

        $(window).scrollTop(0);
        $.ajax({
            url: `${that.base_url}/be${req}`,
            data: args,
            method: "GET",
            headers: {
                'req-by-frontend': 'true'
            },
            success: function(res) { cont_defer.resolve(res); },
        });
    }

    that.init = function() {
        var j_navlist = $('#index-navlist');
        var acct_id;
        var contest_id;

        $(document).on('click', 'a', function(e) {
            let cur_href = location.href;

            let href = $(this).attr('href');
            let target = $(this).attr('target');
            if (href == undefined || href.length == 0) return;
            if (target) return

            window.history.pushState(null, document.title, $(this).attr('href'));

            if (href.startsWith('?')) {
                update(false);

            } else if ((!cur_href.match(/contests\/\d+\//) && href.match(/contests\/\d+\//))
                || (cur_href.match(/contests\/\d+\//) && !href.match(/contests\/\d+\//))) {

                location.href = href;
            } else {
                update(false);
            }

            return false;
        });

        $(document).on('keypress', 'input', function(e) {
            let idx;
            let j_next;

            if (e.which == 13) {
                idx = parseInt($(this).attr('tabindex'));
                if (!isNaN(idx)) {
                    j_next = $('[tabindex="' + (idx + 1) + '"]');

                    if (j_next.attr('submit') != undefined) {
                        j_next.click();
                    } else {
                        j_next.focus();
                    }
                }
                return false;
            }
        });

        $(window).on('popstate', function(a) {
            update(false);
        });

        acct_id = $('#indexjs').attr('acct_id');
        contest_id = $('#indexjs').attr('contest_id');
        that.base_url = $('#indexjs').attr('base_url');
        that.base_url_slash_count = that.base_url.split('/').length - 1;

        j_navlist.find('li.leave').on('click', function(e) {
            $.post(`${that.base_url}/be/sign`, {
                'reqtype': 'signout',
            }, function(res) {
                location.href = `${that.base_url}/sign/`;
            });
        });

        that.ws = that.ws_init('ws');

        if (acct_id != '0') {
            that.acct_id = parseInt(acct_id);
            j_navlist.find('li.leave').show();
            j_navlist.find('a.account').show();
        } else {
            j_navlist.find('li.sign').show();
            j_navlist.find('a.account').hide();
        }

        update(false);
    };

    that.go = function(url) {
        window.history.pushState(null, document.title, url);
        update(false);
    };

    that.reload = function() {
        update(true);
    };

    that.create_progress_bar = function(title) {
        let progressbar_html = `
        <div class="modal fade" id="indexProgressBarDialog" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                </div>
                <div class="modal-body">
                    <p class="text-center">${title}</p>
                    <div class="progress">
                        <div
                            class="progress-bar"
                            role="progressbar"
                            style="width: 0%"
                            aria-valuenow="0"
                            aria-valuemin="0"
                            aria-valuemax="100"
                        ></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
        </div>
        `;
        document.body.insertAdjacentHTML('afterbegin', progressbar_html);
        let progressbar = document.getElementById('indexProgressBarDialog');

        // show modal
        let progressbar_modal = new bootstrap.Modal(progressbar);
        progressbar_modal.show();

        // add a cleanup callback function when modal closed
        progressbar.addEventListener('hidden.bs.modal', () => {
            progressbar_modal.dispose();
            progressbar.remove();
        });
    };

    that.update_progress_bar_progress = function(prog) {
        if (isNaN(parseInt(prog))) {
            return;
        }

        if (parseInt(prog) < 0) {
            return;
        }
        let progressbar = document.getElementById('indexProgressBarDialog');
        if (progressbar == null) {
            console.error('progress bar is null');
            return;
        }

        progressbar.querySelector('.progress-bar').style.width = `${prog}%`;
    }

    that.update_progress_bar_title = function(title) {
        let progressbar = document.getElementById('indexProgressBarDialog');
        if (progressbar == null) {
            console.error('progress bar is null');
            return;
        }

        progressbar.querySelector('.text-center').textContent = title;
    }

    that.remove_progress_bar = function () {
        let progressbar = document.getElementById('indexProgressBarDialog');
        if (progressbar == null) {
            console.error('progress bar is null');
            return;
        }

        let progressbar_modal = bootstrap.Modal.getInstance(progressbar);
        progressbar_modal.dispose();
        progressbar.remove();
    };

    that.DIALOG_TYPE = newEnum({
        error: 'error',
        warning: 'warning',
        success: 'success',
        info: 'info',
    });

    that.show_notify_dialog = function(msg, dialog_type, custom_title=null) {
        let title = '';
        switch (dialog_type) {
            case this.DIALOG_TYPE.error:
                title = 'Error!!!';
                break;
            case this.DIALOG_TYPE.warning:
                title = 'Warning!';
                break;
            case this.DIALOG_TYPE.success:
                title = 'Success';
                break;
            case this.DIALOG_TYPE.info:
                title = 'Info';
                break;
        }

        if (custom_title) {
            title = custom_title;
        }

        // inject html to <body>
        let dialog_html = `
        <div class="modal fade" id="indexNotifyDialog" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">${title}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
            ${msg}
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
            </div>
        </div>
        </div>
        `;
        document.body.insertAdjacentHTML('afterbegin', DOMPurify.sanitize(dialog_html));
        let dialog = document.getElementById('indexNotifyDialog');

        // show modal
        let dialog_modal = new bootstrap.Modal(dialog);
        dialog_modal.show();

        // add a cleanup callback function when modal closed
        dialog.addEventListener('hidden.bs.modal', () => {
            dialog_modal.dispose();
            dialog.remove();
        });
    };

    $.fn.print = function(msg, succ) {
        let j_e = this;

        j_e.text(msg);

        if (j_e.attr('timer') != null) {
            clearTimeout(j_e.attr('timer'));
        }

        if (succ == true) {
            j_e.removeClass('print-fail');
            j_e.addClass('print-succ');
        } else {
            j_e.removeClass('print-succ');
            j_e.addClass('print-fail');
        }
        j_e.css('opacity', '1');

        j_e.attr('timer', setTimeout(function() {
            j_e.attr('timer', null);
            j_e.css('opacity', '0');
        }, 3000));
    };

    that.ws_init = function(ws_url) {
        let ws_link = '';
        if (location.protocol !== 'https:') {
            ws_link = `ws://${location.host}${that.base_url}/be/${ws_url}`;
        } else {
            ws_link = `wss://${location.host}${that.base_url}/be/${ws_url}`;
        }
        let ws = new WebSocket(ws_link);

        ws.onopen = function() {
            console.log('WebSocket connected');
            // Send all pending register messages
            for (let type of that.ws_pending_registers) {
                console.log(`Registering pending callback: ${type}`);
                ws.send(JSON.stringify({'type': 'register', 'data': type}));
            }
            that.ws_pending_registers = [];
            // Send all pending messages
            for (let msg of that.ws_pending_messages) {
                try {
                    ws.send(JSON.stringify(msg));
                } catch (e) {
                    console.error('Failed to send pending ws message', e);
                }
            }
            that.ws_pending_messages = [];
        };

        ws.onmessage = function(event) {
            let data = JSON.parse(event.data);
            if (data.type == "ping") {
                ws.send(JSON.stringify({'type': 'pong', 'data': ''}));
            } else if (that.ws_callback_map.has(data.type)) {
                that.ws_callback_map.get(data.type)(data.data);
            } else {
                console.warn(`no callback registered for ws message type ${data.type}`);
            }
        };

        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
        };

        ws.onclose = function() {
            console.log('WebSocket closed');
        };

        return ws;
    }

    /**
     *
     * @param {string} type
     * @param {Function} callback
     */
    that.register_ws_callback = function(type, callback) {
        if (that.ws == null) {
            console.error('ws is null, cannot register callback');
            return;
        }
        if (that.ws_callback_map.has(type)) {
            console.warn(`ws callback for type ${type} already registered, overwriting`);
        }
        that.ws_callback_map.set(type, callback);

        // If WebSocket is already open, send register immediately
        if (that.ws.readyState === WebSocket.OPEN) {
            that.ws.send(JSON.stringify({'type': 'register', 'data': type}));
        } else {
            // Otherwise, add to pending list
            console.log(`WebSocket not ready, queuing register for: ${type}`);
            that.ws_pending_registers.push(type);
        }
    }

    /**
     *
     * @param {string} type
     * @param {object} data
     */
    that.ws_send = function(type, data) {
        if (that.ws == null) {
            // Socket not initialized yet: queue message
            that.ws_pending_messages.push({'type': type, 'data': data});
            return;
        }
        if (that.ws.readyState === WebSocket.OPEN) {
            that.ws.send(JSON.stringify({'type': type, 'data': data}));
        } else {
            // WebSocket not open (yet or reconnecting); queue the message
            that.ws_pending_messages.push({'type': type, 'data': data});
        }
    }

    that.unescape_html = function(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        return doc.documentElement.textContent;
    };
};
