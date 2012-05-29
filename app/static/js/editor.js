function bindCKE() {
    // CKEditor
    for (id in CKEDITOR.instances) {
        var ed = CKEDITOR.instances[id]
        ed.destroy(true);
    }
    $('textarea.editor').ckeditor($.noop, {
        toolbarCanCollapse : false,
        forcePasteAsPlainText : true,
        height: 100,
        toolbar: [
            { name: 'styles', items : [ 'Bold','Italic','Link','Unlink'] },
        ]
    });
}

function bindHandlers() {
    formNotBusy();
    formClearMessages();
    resizePage();

    $('input[name="headline"]:visible').focus();
    $('form').each( function() {
        $(this).validate({
            submitHandler: function(form) {
                $("#edit-title").modal('hide');
                $(form).ajaxSubmit({
                    beforeSubmit: function() { formBusy(); }, 
                    error: function() { 
                        formNotBusy();
                        formError();
                    },
                    success: function() {
                        $('#update-form-wrapper').load(window.location.href + ' #update-form', function() {
                            if (status == 'error') {
                                formNotBusy();
                                formError();
                            } else {
                                window.frames[0].location.reload(true);
                                bindHandlers();
                            }
                        });
                    }
                });
            }   
        });
    });

    bindCKE();
    $('#cancel-update').on('click', function() {
        $('#update-form-wrapper').load(window.location.href + ' #update-form', bindHandlers);
        return false;
    });
    $("#cancel-update-topper").on('click', function() {
        $('#edit-meta').get(0).reset();
        $('#edit-title').modal('hide');
        bindCKE(); 
        return false;
    });
    
}

function formBusy() {
    formClearMessages();
    $('#update-form-wrapper').spin();
    $('#update-form-wrapper, #preview-frame').animate({'opacity' : 0.5 });
}

function formNotBusy() {
    $('#update-form-wrapper, #preview-frame').animate({'opacity' : 1 })
    $('#update-form-wrapper').spin(false);
}

function formClearMessages() {
    $('#messages').find('.message').not('.help').fadeOut('slow', function() { $(this).remove() });
}

function formError() {
    var errors = $('#form-error');
    if (errors.length == 0) {
        $('<div id="form-error" class="message error">There was an error editing your post. Please try again or reload this page. If the problem persists, please contact the News Apps team.</div>')
            .hide()
            .prependTo($('#messages'))
            .fadeIn('slow');
    }
}

function resizePage() {
    var toolHeight = $('#tools').outerHeight(true);

    var paneHeight = $(window).height() - toolHeight - 30;
    $('#preview-frame').height(paneHeight);

    $('#preview').height(paneHeight - $('#preview-frame h1').outerHeight());

    var columnHeight = $(window).height();
    var msgHeight = $('#messages').outerHeight(true);
    $('#update-form').height(paneHeight - msgHeight);
}

$(document).ready(function() {
    bindHandlers();
    $('#update-form-headline').focus();
    $('#preview').bind({
        'editlayercake': function(e, edit_id) {
            formBusy();
            $('#update-form-wrapper').load(window.location.href + '?edit_id=' + edit_id + ' #update-form', function(response, status, xhr) {
                if (status == 'error') {
                    formNotBusy();
                    formError();
                } else {
                    bindHandlers();
                }
            }); 
        }
    });
    $('a[data-toggle="tab"]').on('shown', function (e) {
        $('input[name="headline"]:visible').focus();
    })
    $(window).resize(resizePage);
});
