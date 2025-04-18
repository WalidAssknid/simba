class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.GET.get('lang')
        if lang in ['en', 'fr', 'es']:
            request.session['lang'] = lang
        elif 'lang' not in request.session:
            request.session['lang'] = 'fr'
        
        response = self.get_response(request)
        return response
