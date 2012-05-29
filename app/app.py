from flask import Flask, request, redirect, flash, get_flashed_messages, render_template, session
from decorators import templated
import sys
import json
from lxml.html import fromstring,tostring
from lxml.cssselect import CSSSelector
from datetime import datetime
from time import time
import dateutil.tz
import requests
import os, os.path
import s3deploy
import re

from optparse import OptionParser

CURRENT_DIR = os.path.dirname(__file__)
LOCAL_CONTENT_DIR = os.path.join(CURRENT_DIR,'static/out')

def ap_formatted(dt):
    return dt.strftime("%l:%M %p").strip().replace('AM','a.m.').replace('PM','p.m.')

# From Django, via http://stackoverflow.com/questions/4970426/html-truncating-in-python
def truncate_html_words(s, num, ellipsis = ' ...'):
    """
    Truncates html to a certain number of words (not counting tags and comments).
    Closes opened tags if they were correctly closed in the given html.
    """
    length = int(num)
    if length <= 0:
        return ''
    html4_singlets = ('br', 'col', 'link', 'base', 'img', 'param', 'area', 'hr', 'input')
    # Set up regular expressions
    re_words = re.compile(r'&.*?;|<.*?>|([A-Za-z0-9][\w-]*)')
    re_tag = re.compile(r'<(/)?([^ ]+?)(?: (/)| .*?)?>')
    # Count non-HTML words and keep note of open tags
    pos = 0
    ellipsis_pos = 0
    words = 0
    open_tags = []
    while words <= length:
        m = re_words.search(s, pos)
        if not m:
            # Checked through whole string
            break
        pos = m.end(0)
        if m.group(1):
            # It's an actual non-HTML word
            words += 1
            if words == length:
                ellipsis_pos = pos
            continue
        # Check for tag
        tag = re_tag.match(m.group(0))
        if not tag or ellipsis_pos:
            # Don't worry about non tags or tags after our truncate point
            continue
        closing_tag, tagname, self_closing = tag.groups()
        tagname = tagname.lower()  # Element names are always case-insensitive
        if self_closing or tagname in html4_singlets:
            pass
        elif closing_tag:
            # Check for match in open tags list
            try:
                i = open_tags.index(tagname)
            except ValueError:
                pass
            else:
                # SGML: An end tag closes, back to the matching start tag, all unclosed intervening start tags with omitted end tags
                open_tags = open_tags[i+1:]
        else:
            # Add it to the start of the open tags list
            open_tags.insert(0, tagname)
    if words <= length:
        # Don't try to close tags if we don't need to truncate
        return s
    out = s[:ellipsis_pos] + ellipsis
    # Close any tags still open
    for tag in open_tags:
        out += '</%s>' % tag
    # Return string
    return out


class NotLayerCake(Exception):
    pass

class LayerCakeApp(Flask):
    """docstring for LayerCakeApp"""
    def __init__(self, module,config_class="Config"):
        super(LayerCakeApp, self).__init__(module)
        self.config.from_object('config.%s' % config_class)

    def http_headers(self, content_type=None):
        h = {
            'Authorization': 'Bearer %(P2P_AUTH_TOKEN)s' % self.config,
        }
        if content_type is not None:
            h['content-type'] = content_type
        return h

    def p2p_get(self,url):
        resp = requests.get(url,headers=self.http_headers())
        if not resp.ok: resp.raise_for_status()
        return json.loads(resp.content)

    def p2p_get_content_item(self,slug,related_items=False):
        url = "%s/content_items/%s.json" % (self.config['P2P_API_ROOT'],slug)
        if related_items:
            url += "?include[]=related_items"
        j = self.p2p_get(url)
        return j['content_item']

    def p2p_id_for_slug(self, slug):
        ci = self.p2p_get_content_item(slug)
        return ci['id']

    def p2p_update(self, slug, content,update_timestamp=True):
        if update_timestamp:
            content = dict(content)
            content['display_time'] = datetime.now(dateutil.tz.gettz('America/Chicago')).isoformat()
            
        d = { 'content_item': content}
        url = "%s/content_items/%s.json" % (self.config['P2P_API_ROOT'],slug)
        resp = requests.put(url,data=json.dumps(d),headers=self.http_headers('application/json'))
        if not resp.ok:
            resp.raise_for_status()
        return resp

    def p2p_create_content_item(self, headline, body='',content_item_type="htmlstory"):
        # slug seems to get ignored...
        data = {'content_item': {
                    "content_item_type_code": content_item_type,
                     "product_affiliate_code": "chinews",
                     "source_code": "chicagotribune",
                     "content_item_state_code": "live",
                     "title": headline,
                     "body": body,
        }}
        url = '%(P2P_API_ROOT)s/content_items.json' % self.config
        resp = requests.post(url,data=json.dumps(data),headers=self.http_headers('application/json'))
        if not resp.ok:
            resp.raise_for_status()
        j = json.loads(resp.content)
        return j['story']

    def p2p_junk(self, slug):
        self.p2p_update(slug, {'content_item_state_code': 'junk'} )

    def p2p_search(self,params):
        """This doesn't work!"""
        url = "%(P2P_API_ROOT)s/content_items/search.json" % self.config
        resp = requests.post(url,data=params,headers=self.http_headers())
        if not resp.ok: resp.raise_for_status()
        j = json.loads(resp.content)
        return j['content_items']

    def p2p_fetch_gallery(self, gallery_slug):
        """For photo AND story galleries, retrieve the root content item and full records for all related items"""
        item = self.p2p_get_content_item(gallery_slug,related_items=True)
        items = self.fetch_multiple_items(live_related_item_ids(item['related_items']))
        return {'gallery': item, 'related': items }

    def fetch_multiple_items(self, ids):                
        ids = list(ids)
        if len(ids) > 25:
            agg = []
            id_groups = segment_list(ids, 25)
            for group in id_groups:
                agg.extend(self.fetch_multiple_items(group))
            return agg

        url = "%(P2P_API_ROOT)s/content_items/multi.json" % self.config
        items = [{'id': id} for id in ids]
        data = json.dumps({ "content_items": items })
        h = dict(self.http_headers('application/json'))
        resp = requests.post(url,data=data,headers=h)
        if not resp.ok: resp.raise_for_status()
        j = json.loads(resp.content)
        return [x['body']['content_item'] for x in j]


    def update_meta_markup(self,slug,topper=None, story_url=None):
        content_item = self.p2p_get_content_item(slug)
        current_content = content_item['body']
        parsed = fromstring(current_content)
        if parsed.attrib.get('id','') == 'layercake':
            wrapper = parsed
        else:    
            wrapper = parsed.find('.//div[@id="layercake"]')
        if wrapper is None:
            raise NotLayerCake
        if story_url:
            wrapper.attrib['data-url'] = story_url
        if topper:
            topper_elem = wrapper.find('.//div[@id="layercake-topper"]')
            if topper_elem is None:
                raise NotLayerCake

            # support markup in topper without requiring it be submitted wrapped in an element
            new_topper = fromstring("<div id='layercake-topper'>%s</div>" % topper)
            topper_elem.addnext(new_topper)
            topper_elem.getparent().remove(topper_elem)

        return tostring(parsed)

    def prepare_updated_content(self,slug,rendered_content):
        """Given a slug, get its current content. Either insert the HTML string 'rendered_content' as the first child
        of the current content for the slug, or, if an existing element with the same tag and id exists, replace that
        element. Return the title and current content as a tuple of strings."""
        content_item = self.p2p_get_content_item(slug)
        current_content = content_item['body']
        title = content_item['title']
        parsed = fromstring(current_content)
        container = parsed.find('.//div[@id="layercake-items"]')
        if container is None:
            container = parsed.makeelement('div',{'id': 'layercake-items'})
            made_container = True
        else:
            made_container = False
        new_parsed = fromstring(rendered_content)
        try:
            existing = container.find("%s[@id='%s']" % (new_parsed.tag,new_parsed.attrib['id']))
        except KeyError:
            existing = None

        if existing is not None:
            existing.addnext(new_parsed)
            container.remove(existing)
        else:
            container.insert(0,new_parsed)

        # TODO: consider timestamping the CSS URL
        if made_container:
            new_content = tostring(container)
            return title,current_content + new_content

        return title,tostring(parsed)

    def delete_update(self, slug, edit_id):
        content_item = self.p2p_get_content_item(slug)
        current_content = content_item['body']
        parsed = fromstring(current_content)

        existing = parsed.find( ".//div[@id='%s']" % (edit_id,) )
        existing.getparent().remove(existing)

        return content_item['title'], tostring(parsed)

app = LayerCakeApp(__name__)
app.secret_key = 'MAKE_THIS_UNIQUE_AND_SECRET'

from flaskext.embedly import Embedly
e = Embedly(app)

@app.route('/')
@templated()
def index():
    return {}

@app.route('/create',methods=['post','get']) # remove 'get' when we have a real form
def create():
    """Given a headline (and any other strictly required values), create a new HTML Story content item prepped
    with basic layercake formatting.
    """
    d = {
        'css_url': app.config['CSS_URL'],
        'topper': request.values.get('topper',''),
    }
    body = render_template('_new_cake.html',**d)
    created = app.p2p_create_content_item(request.values.get('headline'),body=body)
    created.update(app.config)
    session['brand_new'] = True
    return redirect('/edit/%s' % (created['slug'],))

@app.route('/edit/<slug>',methods=['get'])
@templated()
def edit(slug):
    context = { 'headline': '', 'update': '', 'topper': '', 'title': '', 'source': '', 'brand_new': session.pop('brand_new', False) }
    context['slug'] = slug
    context['active_tab'] = 'update'
    context['edit_id'] = request.values.get('edit_id','')
    context['timestamp'] = ''
    context['edit_title'] = ''

    if context['slug']:
        content_item = app.p2p_get_content_item(context['slug'])
        current_content = content_item['body']
        context['title'] = content_item['title']
        context['id'] = content_item['id']
        populate_context_with_meta(current_content, context)

        if context['edit_id']:
            existing = extract_item(current_content, context['edit_id'])
            try:
                if existing is not None:
                    data_type = existing.attrib.get('data-type')
                    context['active_tab'] = data_type
                    CONTENT_HANDLERS[data_type].populate_form_context(context,existing)
            except KeyError:
                pass
    else:
        # TODO Redirect to create form when it exits
        flash("This form must be loaded with a slug.","error")

    return context

@app.route('/preview/<slug>',methods=['get'])
@templated()
def preview(slug):
    context = {}
    if slug:
        context['content'] = app.p2p_get_content_item(slug)
        return context

def extract_item(layercake,edit_id):
    """Given the body of a layercake content item, return the specific edit id requested as a parsed lxml element"""
    parsed = fromstring(layercake)
    return parsed.find(".//div[@id='%s']" % (edit_id,))

def populate_context_with_meta(content, context):
    parsed = fromstring(content)
    if parsed.attrib.get('id','') == 'layercake':
        wrapper = parsed
    else:    
        wrapper = parsed.find('.//div[@id="layercake"]')
    if wrapper is None:
        raise NotLayerCake
    context['story_url'] = wrapper.attrib.get('data-url','')
    topper = parsed.find('.//div[@id="layercake-topper"]')
    if topper is None:
        context['topper'] = ''
    else:    
        parts = [topper.text]
        for kid in topper.iterchildren():
            parts.append(tostring(kid))
        context['topper'] = ''.join(filter(None,parts))

def extract_text(elem_list):
    parts = []
    for x in elem_list:
        parts.extend(x.xpath('./text()'))
    return ' '.join(parts).strip()

def extract_markup(elem_list):
    parts = []
    for el in elem_list:
        parts.extend(''.join([tostring(child) for child in el.iterchildren()]))
    return ''.join(parts).strip()

@app.route('/bookmarklet')
@templated()
def bookmarklet():
    return { 'host' : request.environ['HTTP_HOST'], }

@app.route('/update',methods=['post'])
def update():
    try:
        if request.json:
            values = request.json
        else:
            values = request.form
        slug = values['slug']
        if values['template'] == 'meta':
            title = values['title']
            new_content = app.update_meta_markup(slug,topper=values.get('topper',None),story_url=values.get('story_url',None))
            app.p2p_update(slug, {'title': title, 'body': new_content })
        else:
            if values.has_key('intention') and values['intention'].lower().startswith('delete'):
                edit_id = values.get('edit_id')
                title, new_content = app.delete_update(slug, edit_id)
            else:
                handler = CONTENT_HANDLERS[values['template']]
                context = handler.prepare_render_context(slug, request, values)
                rendered_content = handler.render(context)
                title, new_content = app.prepare_updated_content(slug,rendered_content)
            app.p2p_update(slug, {'body': new_content })
        update_blurb(slug, title, new_content)
        flash("updated!")
    except NotLayerCake:
        flash("This is not a layercake story.", 'error')
    return redirect('/edit/%s' % (slug,))


class ContentItemHandler(object):
    """All content handlers should have a template name. Most will not change the 'render' method
    but will update process_context"""
    text_extract_classes = ['headline', 'timestamp']
    markup_extract_classes = []

    def prepare_render_context(self, slug, request, values):
        context = {'content_type': self.content_type}
        for k in ['headline', 'timestamp', 'edit_id']:
            context[k] = values.get(k,'')
        if not (context.has_key('edit_id') and context['edit_id']):
            context['edit_id'] = "%s_%s" % (slug,time())
        if not context['timestamp'] or context['timestamp'] == 'auto':
            context['timestamp'] = ap_formatted(datetime.now(dateutil.tz.gettz('America/Chicago')))
        return context

    def render(self, context):
        "Context should come from 'prepare_render_context' to be sure everything is set up, esp. edit_id"
        return render_template(self.template_name,**context)

    def populate_form_context(self, context, existing_elem):
        for k in self.text_extract_classes:
            context[k] = extract_text(existing_elem.xpath(CSSSelector('.%s' % k).path))
        for k in self.markup_extract_classes:
            context[k] = extract_markup(existing_elem.xpath(CSSSelector('.%s' % k).path))
        context['edit_title'] = 'Editing <em>%s</em>' % context['headline']
        context['edit_id'] = existing_elem.attrib.get('id','')
        context['content_type'] = existing_elem.attrib.get('data-type','')

    def render_blurb(self, existing_elem):
        context = {}
        self.populate_form_context(context, existing_elem)
        
        # @TODO maybe this is a weird location, should be in different handler?
        if 'update' in context:
            context['update'] = truncate_html_words(context['update'], 20)

        try:
            return render_template(self.blurb_template_name,**context)
        except:
            return ''

    @property
    def blurb_template_name(self):
        return self.template_name.replace("_","_blurb_",1)

class UpdateHandler(ContentItemHandler):
    """Handle basic updates"""
    content_type = 'update'
    template_name = '_update.html'
    text_extract_classes = ['headline', 'timestamp', 'source']
    markup_extract_classes = ['update', 'caption']
    def prepare_render_context(self, slug, request, values):
        context = super(UpdateHandler, self).prepare_render_context(slug, request, values)
        for k in ['body', 'source', 'caption',]:
            context[k] = values.get(k,'')

        try:
            upload = request.files['photo']
            if upload.filename:
                key_name = 'layercake/uploads/%s/%s' % (slug, upload.filename)
                context['photo_url'] = s3deploy.s3_upload_flo(upload.stream, app.config['S3_BUCKET'], key_name, upload.mimetype)
            else:
                context['photo_url'] = values['photo_url']
        except KeyError, e:
            context['photo_url'] = values['photo_url']

        return context

    def populate_form_context(self, context, existing_elem):
        super(UpdateHandler, self).populate_form_context(context, existing_elem)
        img = existing_elem.find('.//img[@class="photo"]')
        if img is not None:
            context['photo_url'] = img.attrib['src']

class VideoHandler(ContentItemHandler):
    """Handle video updates"""
    content_type = 'video'
    template_name = '_video.html'
    text_extract_classes = ['headline', 'timestamp', 'source']
    markup_extract_classes = ['update',]
    def prepare_render_context(self, slug, request, values):
        context = super(VideoHandler, self).prepare_render_context(slug, request, values)
        for k in ['body', 'source', ]:
            context[k] = values.get(k,'')

        video_id = values.get('video_id','')
        context['video'] = app.p2p_get_content_item(video_id)
        return context

    def populate_form_context(self, context, existing_elem):
        super(VideoHandler, self).populate_form_context(context, existing_elem)
        vid = existing_elem.find('.//div[@class="video"]')
        if vid is not None:
            context['video_id'] = vid.attrib['data-video-id']

class TweetHandler(ContentItemHandler):
    content_type = 'tweet'
    template_name = '_tweet.html'
    text_extract_classes = ['headline', 'timestamp',]
    markup_extract_classes = ['update',]
    def prepare_render_context(self, slug, request, values):
        context = super(TweetHandler, self).prepare_render_context(slug, request, values)
        for k in ['body', ]:
            context[k] = values.get(k,'')
        try:
            twitter_response = get_twitter_embed(values['tweet_url'])
            context['embed'] = twitter_response['html']
            context['tweet_url'] = twitter_response['url']
        except Exception, e:
            app.logger.error("Error fetching tweet")
            app.logger.error(e)
            context['embed'] = 'Error!'
            context['tweet_url'] = values.get('tweet_url','')
        return context

    def populate_form_context(self, context, existing_elem):
        super(TweetHandler, self).populate_form_context(context, existing_elem)
        wrapper = existing_elem.find('.//div[@class="tweet"]')
        if wrapper is not None:
            context['tweet_url'] = wrapper.attrib['data-url']
            context['embed'] = extract_markup(wrapper) # this seems to miss the outer blockquote...
            

class OEmbedHandler(ContentItemHandler):
    content_type = 'oembed'
    template_name = '_oembed.html'
    text_extract_classes = ['headline', 'timestamp',]
    markup_extract_classes = ['update',]
    def prepare_render_context(self, slug, request, values):
        context = super(OEmbedHandler, self).prepare_render_context(slug, request, values)
        for k in ['body', 'oembed_url']:
            context[k] = values.get(k,'')

        return context

    def populate_form_context(self, context, existing_elem):
        super(OEmbedHandler, self).populate_form_context(context, existing_elem)
        wrapper = existing_elem.find('.//div[@class="oembed"]')
        if wrapper is not None:
            context['oembed_url'] = wrapper.attrib['data-url']


CONTENT_HANDLERS = {
    'update': UpdateHandler(),
    'video': VideoHandler(),
    'tweet': TweetHandler(),
    'oembed': OEmbedHandler(),
}
    
def get_twitter_embed(url_or_id):
    if url_or_id.find('/') != -1:
        id = url_or_id.split('/')[-1]
    else:
        id = url_or_id
    resp = requests.get('https://api.twitter.com/1/statuses/oembed.json?id=%s' % id)
    j = json.loads(resp.content)
    if 'error' in j:
        raise Exception(j['error'])
    else:
        return j

def update_blurb(slug, title, new_content):
    context = { 'title': title, 'blurbs': [] }
    populate_context_with_meta(new_content, context)
    
    for item in fromstring(new_content).xpath('.//div[@class="layercake-item"]')[:5]:
        handler = CONTENT_HANDLERS[item.attrib['data-type']]
        context['blurbs'].append(handler.render_blurb(item))
    from StringIO import StringIO
    key_name = 'layercake/uploads/%s/blurb.html' % (slug, )
    blurb_url = s3deploy.s3_upload_flo(StringIO(render_template("_blurb.html", **context).encode('utf-8')), app.config['S3_BUCKET'], key_name, "text/html")
    
def parse_args():
    parser = OptionParser()
    parser.add_option("-o", "--host", dest="host", default='localhost',
                      help="override the 'host' value so that one can access the local server from other machines.")
    parser.add_option("-t", "--deployment-target",
                      action="store", dest="target",
                      help="If specified, use the config settings for the given deployment target.")
    (options, args) = parser.parse_args()
    return options

def segment_list(l,max_len):
    segments = []
    for x in range(0,(len(l) // max_len)):
        segments.append(l[x*max_len:(x*max_len)+max_len])
    segments.append(l[(x+1)*max_len:])
    return segments


def live_related_item_ids(item_dicts):
    """Only return the ids for live items, and not the one which is not a real photo (which doesn't apply to story galleries...)"""
    ids = []
    for ri in item_dicts:
        if ri.get('slug') != 'chi-end-photo' and ri.get(u'content_item_state_code') == 'live':
            ids.append(ri['relatedcontentitem_id'])
    return ids


if __name__ == '__main__':
    opts = parse_args()
    if opts.target:
        app.config.from_object('config.%s' % opts.target)

    kwargs = { 'debug': True, 'host': opts.host }

    app.run(**kwargs)
