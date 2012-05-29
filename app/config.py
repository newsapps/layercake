class Config(object):
    DEBUG = True
    P2P_API_ROOT = 'http://content-api.p2p.tribuneinteractive.com.stage.tribdev.com'
    P2P_ROOT = 'http://content.p2p.tribuneinteractive.com.stage.tribdev.com'
    P2P_AUTH_TOKEN = 'GET_THIS_FROM_TRIBTECH'
    CSS_URL = 'http://localhost:5000/static/css/layercake.css'
    S3_BUCKET = 'media-beta.tribapps.com'

class StagingConfig(Config):
    CSS_URL = 'http://media-beta.tribapps.com/layercake/css/layercake.css'
    # staging p2p is just busted...
    P2P_API_ROOT = 'https://content-api.p2p.tribuneinteractive.com'
    P2P_ROOT = 'http://content.p2p.tila.trb'
    P2P_AUTH_TOKEN = 'GET_THIS_FROM_TRIBTECH'

class ProductionConfig(Config):
    DEBUG = False
    P2P_API_ROOT = 'https://content-api.p2p.tribuneinteractive.com'
    P2P_ROOT = 'http://content.p2p.tila.trb'
    P2P_AUTH_TOKEN = 'GET_THIS_FROM_TRIBTECH'
    CSS_URL = 'http://media.apps.chicagotribune.com/layercake/css/layercake.css'
    S3_BUCKET = 'media.apps.chicagotribune.com'

class LocalProdConfig(ProductionConfig):
    CSS_URL = 'http://localhost:5000/static/css/layercake.css'
