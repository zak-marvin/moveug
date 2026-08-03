from django.views.generic import TemplateView


class ConsoleView(TemplateView):
    template_name = 'testconsole/console.html'
