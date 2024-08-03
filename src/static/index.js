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
        var j_navlist = $('#index-navlist');
        var acct_id;
        var contest_id;

        $(document).on('click', 'a', function(e) {
            let cur_href = location.href;
            let href = $(this).attr('href');
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

        j_navlist.find('li.leave').on('click', function(e) {
            $.post('/oj/be/sign', {
                'reqtype': 'signout',
            }, function(res) {
                location.href = '/oj/sign/';
            });
        });

        acct_id = $('#indexjs').attr('acct_id');
        contest_id = $('#indexjs').attr('contest_id');
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

        progressbar.querySelector('.modal-header').textContent = title;
    }

    that.remove_progress_bar = function () {
        let progressbar = document.getElementById('indexProgressBarDialog');
        if (progressbar == null) {
            console.error('progress bar is null');
            return;
        }

        let progressbar_modal = bootstrap.Modal.getInstance(progressbar);
        progressbar_modal.hide();
    };

    that.DIALOG_TYPE = newEnum({
        error: 'error',
        warning: 'warning',
        success: 'success',
        info: 'info',
    });

    that.show_notify_dialog = function(msg, dialog_type) {
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
        document.body.insertAdjacentHTML('afterbegin', dialog_html);
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

    that.get_ws = function(ws_url) {
        let ws_link = '';
        if (location.protocol !== 'https:') {
            ws_link = `ws://${location.host}/oj/be/${ws_url}`;
        } else {
            ws_link = `wss://${location.host}/oj/be/${ws_url}`;
        }
	    return new WebSocket(ws_link);
    };
};

