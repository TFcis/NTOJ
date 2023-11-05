'use strict';

var index = new function() {
    var that = this;
    var curr_url = null;

    that.acct_id = null;
    that.prev_url = null;

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
        if (parts[4] == '') {
            page = 'info';
            req = '/info';

        } else {
            page = parts[4];
            req = '';
            for (i = 4 ; i < parts.length - 1; i++) {
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

        if (typeof(destroy) == 'function') {
            destroy();
        }

        cont_defer.done(function(res) {
            j_cont.html(res).ready(function() {
                var defer;

                if (typeof(init) == 'function') {
                    init();
                }

                defer = Array();
                j_cont.find('link').each(function(i, e) {
                    defer[i] = $.Deferred();

                    $(e).on('load', function() {
                        defer[i].resolve();
                    });
                });

                $.when.apply($, defer).done(function() {
                    j_cont.stop().fadeIn(100);
                });
            });

            _scroll();
        });

        $(window).scrollTop(0);
        $.get('/oj/be' + req, args, function(res) {
            cont_defer.resolve(res);
        });
    }

    that.init = function() {
        var s_viewpoint = document.createElement("style");
        var j_navlist = $('#index-navlist');
        var acct_id;

        $(document).on('click', 'a', function(e) {
            window.history.pushState(null, document.title, $(this).attr('href'));
            update(false);

            return false;
        });

        $(document).on('keypress', 'input', function(e) {
            var idx;
            var j_next;

            if (e.which == 13) {
                if (!isNaN(idx = parseInt($(this).attr('tabindex')))) {
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

        j_navlist.find('li.leave').on('click', function(e) {
            $.post('/oj/be/sign', {
                'reqtype': 'signout',
            }, function(res) {
                location.href = '/oj/sign/';
            });
        });

        acct_id = $('#indexjs').attr('acct_id');
        if (acct_id != '') {
            that.acct_id = parseInt(acct_id);
            j_navlist.find('li.leave').show();
        } else {
            j_navlist.find('li.sign').show();
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

    $.fn.print = function(msg, succ) {
        var j_e = this;

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

    that.get_ws = function(wsname) {
        let ws_link = '';
        if (location.protocol !== 'https:') {
            ws_link = `ws://${location.host}/oj/be/${wsname}`;
        } else {
            ws_link = `wss://${location.host}/oj/be/${wsname}`;
        }
	    return new WebSocket(ws_link);
    };
};

