from django import template
from django.template.defaultfilters import stringfilter
import os


register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'): # بررسی می‌کند که آیا ورودی اول یک دیکشنری یا شیء شبه‌دیکشنری است
        return dictionary.get(key)
    return None # یا مقدار پیش‌فرض دیگر در صورت نیاز



@register.filter
def get_score_type(user_scores_dict, score_type):
    """
    Gets the score value for a specific score_type from a user's scores dictionary.
    user_scores_dict is expected to be {score_type: value}
    """
    try:
        # Ensure score_type is treated as the correct type (e.g., int)
        score_type_int = int(score_type)
        # Return the value, or 0 if the score_type is not in the dictionary
        if isinstance(user_scores_dict, dict):
             return user_scores_dict.get(score_type_int, 0)
        else:
             return 0 # Return 0 if user_scores_dict is not a dictionary
    except (AttributeError, ValueError):
        # Handle case where score_type is not convertible to int or user_scores_dict is not as expected
        return 0


@register.filter(name='get_dict_value')
def get_dict_value(dictionary, key):
    """Gets a value from a dictionary by key."""
    # Ensure dictionary is a dictionary before using .get()
    if isinstance(dictionary, dict):
        # Attempt to get the value using the original key type
        value = dictionary.get(key)
        if value is not None:
            return value
        # If not found, try converting key to int in case dictionary keys are ints
        try:
            key_int = int(key)
            return dictionary.get(key_int)
        except (ValueError, TypeError):
             pass # Key cannot be converted to int

    return None # Return None if not a dict or key not found


@register.simple_tag
def get_score(score_dict, user_id, score_type):
    """
    Retrieves a score value from the score_dict.
    (This tag is likely used in dashboard.html, not directly involved in the current error)
    """
    try:
        user_id = int(user_id)
        score_type = int(score_type)
        return int(score_dict.get((user_id, score_type), 0))
    except (ValueError, TypeError):
        return 0 # Return a default value or handle the error as needed


@register.filter
def in_list(value, arg):
    items = [int(x.strip()) for x in arg.split(',')]
    return value in items


@register.filter
def in_list_str(value, arg):
    items = [str(x.strip()) for x in arg.split(',')]
    return value in items


@register.filter(name='get_attribute')
def get_attribute(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    # You could also try to get an attribute if it's an object
    # return getattr(obj, key, None)
    return None



@register.filter
@stringfilter
def get_basename(value):
    return os.path.basename(value)


@register.filter
@stringfilter
def truncate_name(value, length=15):
    if len(value) > length:
        return value[0:length] + "..."
    return value