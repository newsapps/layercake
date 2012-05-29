var iframe = document.getElementById('layercake-editor'), 
    start = document.location.href.lastIndexOf('/') + 1,
    end = document.location.href.indexOf(','),
    slug = (start > 0 && end > start) ? document.location.href.slice(start, end) : '',
    baseURL = window.layercake.baseURL;

if (!iframe) {
    // Load CSS
    var link = document.createElement('link');
    link.setAttribute('type', 'text/css');
    link.setAttribute('href', window.layercake.baseURL + '/static/bookmarklet/iframe.css');
    link.setAttribute('rel', 'stylesheet');
    link.setAttribute('media', 'screen');
    document.body.appendChild(link);

    var iframe = document.createElement('iframe');
    iframe.setAttribute('id', 'layercake-editor');
    iframe.setAttribute('allowTransparency', true);
    iframe.setAttribute('frameBorder', 0);
    iframe.setAttribute('data-open', 0);
    iframe.setAttribute('src', baseURL + '/form?slug=' + encodeURIComponent(slug) );
    document.body.appendChild(iframe);

    add_edit_links();
}

function add_edit_links() {
    var layercake = document.getElementById('layercake-items');

    var items = document.getElementsByClassName('layercake-item');
    for (i = 0; i < items.length; i++) {
        var item = items[i];
        
        var edit_link = document.createElement("a");
        edit_link.setAttribute('data-item-id', item.id);
        edit_link.setAttribute('class', 'item-edit');
       
        var edit_text = document.createTextNode("Edit update");

        edit_link.appendChild(edit_text);
        
        layercake.insertBefore(edit_link, item);
        
        edit_link.onclick = update_iframe;
        edit_link.onkeydown = update_iframe;
    }
}

function update_iframe() {
    var id = this.getAttribute('data-item-id');
    iframe.setAttribute('src', baseURL + '/form?slug=' + encodeURIComponent(slug) + '&edit_id=' + id);
    return false;
};


function toggle_iframe() {
    var iframe = document.getElementById('layercake-editor');
    if (iframe.getAttribute('data-open') == 0) {
        iframe.style.display = 'block';
        iframe.setAttribute('data-open', 1);
    } 
    else {
        iframe.style.display = 'none';
        iframe.setAttribute('data-open', 0);
    }
}

// Create reload button which doesn't work on IE
jQuery('<a id="reload-layercake">Reload story</a>')
.attr('href', window.location.href + '?' + new Date().getTime())
.insertBefore('#layercake');

/*.click(function() {
    jQuery('#layercake').load(window.location.href + ' #layercake', function() {
        add_edit_links();
    });
    return false;
});*/

// Remove?
/*if (window.addEventListener && window.postMessage) {
    window.addEventListener("message", reloadContentItem, false);
    function reloadContentItem(event) {
        if (event.origin == baseURL && event.data == 'reload') {
            jQuery('#story-body').load(window.location.href + ' #story-body', function() {
                add_edit_links();
            });
        }
    }    
} else {

}*/
