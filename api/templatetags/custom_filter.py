from django import template

register = template.Library()

@register.simple_tag
def counter_add(value1, value2):
    return value1 + value2